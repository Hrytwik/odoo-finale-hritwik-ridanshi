import { fireEvent, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeEach, describe, expect, it, vi } from 'vitest'

vi.mock('@/lib/api/client', () => ({ api: { GET: vi.fn(), POST: vi.fn(), PATCH: vi.fn(), DELETE: vi.fn() } }))
import { api } from '@/lib/api/client'
import { mockApi, renderPage } from '@/test/utils'
import ReceiveYarn from './ReceiveYarn'

const YARN_TYPES = [{ id: 1, code: '30S-COT-RAW', name: '30s cotton', colour: 'raw white', reorder_level_kg: 300 }]
const SUPPLIERS = [{ id: 1, name: 'Vardhman Yarns', phone: null, lead_time_days: 7 }]
const ORDERS = [{ code: 'ORD-0012', state: 'confirmed', buyer: { id: 1, name: 'Sharma Fabrics' } }]
const LOT = { lot_code: 'L-0017', qty_received_kg: 800, yarn_type: YARN_TYPES[0], supplier: SUPPLIERS[0] }

function standardApi(extra: Parameters<typeof mockApi>[0] = {}) {
  mockApi({
    GET: { '/api/yarn-types': YARN_TYPES, '/api/suppliers': SUPPLIERS, '/api/orders': ORDERS, ...extra.GET },
    POST: { '/api/lots': LOT, ...extra.POST },
  })
}

async function fillValid() {
  await userEvent.selectOptions(await screen.findByLabelText(/yarn type/i), '1')
  await userEvent.selectOptions(screen.getByLabelText(/supplier/i), '1')
  await userEvent.type(screen.getByLabelText(/quantity/i), '800')
  await userEvent.type(screen.getByLabelText(/cost per kg/i), '250')
  await userEvent.type(screen.getByLabelText(/challan number/i), 'CH-5521')
}

beforeEach(() => {
  vi.clearAllMocks()
})

describe('ReceiveYarn', () => {
  it('offers the yarn types, suppliers and open orders from the server', async () => {
    standardApi()
    renderPage(<ReceiveYarn />)
    expect(await screen.findByRole('option', { name: /30s cotton/i })).toBeInTheDocument()
    expect(screen.getByRole('option', { name: 'Vardhman Yarns' })).toBeInTheDocument()
    expect(screen.getByRole('option', { name: /ORD-0012/ })).toBeInTheDocument()
  })

  it('tells the clerk what is missing and sends nothing', async () => {
    standardApi()
    renderPage(<ReceiveYarn />)
    await screen.findByRole('option', { name: /30s cotton/i })
    await userEvent.click(screen.getByRole('button', { name: /receive lot/i }))
    expect(await screen.findByText('Choose a yarn type')).toBeInTheDocument()
    expect(screen.getByText('Choose a supplier')).toBeInTheDocument()
    expect(screen.getByText('Enter the quantity in kg')).toBeInTheDocument()
    expect(screen.getByText('Enter the cost per kg')).toBeInTheDocument()
    expect(screen.getByText('Enter the challan number')).toBeInTheDocument()
    expect(api.POST).not.toHaveBeenCalled()
  })

  it('rejects zero and negative quantities', async () => {
    standardApi()
    renderPage(<ReceiveYarn />)
    await fillValid()
    const qty = screen.getByLabelText(/quantity/i)
    await userEvent.clear(qty)
    await userEvent.type(qty, '-5')
    await userEvent.click(screen.getByRole('button', { name: /receive lot/i }))
    expect(await screen.findByText('Must be more than 0')).toBeInTheDocument()
    expect(api.POST).not.toHaveBeenCalled()
  })

  it('records the lot with real numbers and confirms it', async () => {
    standardApi()
    renderPage(<ReceiveYarn />)
    await fillValid()
    await userEvent.click(screen.getByRole('button', { name: /receive lot/i }))
    await waitFor(() => expect(api.POST).toHaveBeenCalledTimes(1))
    expect(api.POST).toHaveBeenCalledWith('/api/lots', {
      body: { yarn_type_id: 1, supplier_id: 1, qty_kg: 800, cost_per_kg: 250, challan_no: 'CH-5521' },
    })
    expect(await screen.findByText(/L-0017/)).toBeInTheDocument()
    expect(screen.getByRole('link', { name: /view lot/i })).toHaveAttribute('href', '/store/lots/L-0017')
    // the form is cleared, ready for the next delivery
    expect(screen.getByLabelText(/challan number/i)).toHaveValue('')
  })

  it('includes the order the yarn is for, when chosen', async () => {
    standardApi()
    renderPage(<ReceiveYarn />)
    await fillValid()
    await userEvent.selectOptions(screen.getByLabelText(/for order/i), 'ORD-0012')
    await userEvent.click(screen.getByRole('button', { name: /receive lot/i }))
    await waitFor(() => expect(api.POST).toHaveBeenCalled())
    expect(vi.mocked(api.POST).mock.calls[0][1]).toMatchObject({ body: { intended_order_code: 'ORD-0012' } })
  })

  it('shows a duplicate delivery under the challan number field', async () => {
    standardApi({
      POST: {
        '/api/lots': {
          status: 409,
          error: { code: 'DUPLICATE_CHALLAN', message: 'This challan was already entered for this supplier and yarn type', field: 'challan_no', fields: null },
        },
      },
    })
    renderPage(<ReceiveYarn />)
    await fillValid()
    await userEvent.click(screen.getByRole('button', { name: /receive lot/i }))
    expect(await screen.findByText(/already entered/i)).toBeInTheDocument()
    expect(screen.getByLabelText(/challan number/i)).toHaveAttribute('aria-invalid', 'true')
    // what the clerk typed is still there
    expect(screen.getByLabelText(/challan number/i)).toHaveValue('CH-5521')
  })

  it('sends one request when Receive lot is pressed twice quickly', async () => {
    standardApi({ POST: { '/api/lots': () => new Promise(() => {}) as never } })
    vi.mocked(api.POST).mockReturnValue(new Promise(() => {}) as never)
    renderPage(<ReceiveYarn />)
    await fillValid()
    const form = screen.getByRole('button', { name: /receive lot/i }).closest('form')!
    fireEvent.submit(form)
    fireEvent.submit(form)
    await waitFor(() => expect(api.POST).toHaveBeenCalledTimes(1))
  })

  it('uploads the challan photo first and sends its path with the lot', async () => {
    standardApi({ POST: { '/api/uploads': { path: 'uploads/abc.jpg', url: '/api/uploads/abc.jpg' } } })
    renderPage(<ReceiveYarn />)
    await fillValid()
    const file = new File(['x'], 'challan.jpg', { type: 'image/jpeg' })
    await userEvent.upload(screen.getByLabelText(/challan photo/i), file)
    await userEvent.click(screen.getByRole('button', { name: /receive lot/i }))
    await waitFor(() => expect(vi.mocked(api.POST).mock.calls.map((c) => c[0])).toEqual(['/api/uploads', '/api/lots']))
    expect(vi.mocked(api.POST).mock.calls[1][1]).toMatchObject({ body: { challan_photo_path: 'uploads/abc.jpg' } })
  })

  it('shows a Retry state when the lists cannot be loaded', async () => {
    mockApi({ GET: { '/api/yarn-types': { status: 500, error: 'boom' }, '/api/suppliers': SUPPLIERS, '/api/orders': ORDERS } })
    renderPage(<ReceiveYarn />)
    expect(await screen.findByRole('alert')).toHaveTextContent(/something went wrong/i)
    expect(screen.getByRole('button', { name: /retry/i })).toBeInTheDocument()
  })
})
