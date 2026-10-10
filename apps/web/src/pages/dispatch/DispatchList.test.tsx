import { screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeEach, describe, expect, it, vi } from 'vitest'

vi.mock('@/lib/api/client', () => ({ api: { GET: vi.fn(), POST: vi.fn(), PATCH: vi.fn(), DELETE: vi.fn() } }))
import { api } from '@/lib/api/client'
import { mockApi, renderPage } from '@/test/utils'
import DispatchList from './DispatchList'

const roll = (c: string) => ({ id: 1, code: c, order_code: 'ORD-0012', buyer_name: 'Sharma Fabrics', fabric: 'Poplin 58in', colour: 'navy', metres: 110, status: 'dispatched', created_at: '2026-10-10T10:00:00Z' })
const dispatch = (over = {}) => ({
  id: 7, code: 'DSP-0007', buyer: { id: 1, name: 'Sharma Fabrics' }, vehicle_no: 'KA01AB1234', driver_name: 'Manju', state: 'dispatched',
  created_at: '2026-10-09T10:00:00Z', dispatched_at: '2026-10-09T15:00:00Z', rolls: [roll('R-0131'), roll('R-0132'), roll('R-0133')], orders: [], total_metres: 330, invoice_no: 'INV-0007', warnings: [], ...over,
})
const LOADING = dispatch({ id: 8, code: 'DSP-0008', state: 'loading', dispatched_at: null, invoice_no: null, rolls: [roll('R-0140')], total_metres: 110, vehicle_no: 'KA05CD5678' })
const BUYERS = [{ id: 1, name: 'Sharma Fabrics', contact_name: null, phone: null, email: null }, { id: 2, name: 'Patel Textiles', contact_name: null, phone: null, email: null }]

function setup(list: unknown[] = [LOADING, dispatch()], extra: Parameters<typeof mockApi>[0] = {}) {
  mockApi({
    GET: { '/api/dispatches': list, '/api/buyers': BUYERS, ...extra.GET },
    POST: { '/api/dispatches': { ...LOADING, code: 'DSP-0009' }, ...extra.POST },
  })
  return renderPage(<DispatchList />, { extra: [{ path: '/dispatch/:code', element: <p>load truck page</p> }] })
}

beforeEach(() => {
  vi.clearAllMocks()
})

describe('DispatchList', () => {
  it('lists dispatches with buyer, vehicle, rolls, metres and state', async () => {
    setup()
    const table = await screen.findByRole('table')
    const row = within(table).getByRole('row', { name: /DSP-0007/ })
    expect(row).toHaveTextContent('Sharma Fabrics')
    expect(row).toHaveTextContent('KA01AB1234')
    expect(row).toHaveTextContent('3 rolls')
    expect(row).toHaveTextContent('330 m')
    expect(row).toHaveTextContent('Dispatched')
    expect(within(row).getByRole('link', { name: 'DSP-0007' })).toHaveAttribute('href', '/dispatch/DSP-0007')
  })

  it('links a sent dispatch to its invoice, and a truck still loading to nothing', async () => {
    setup()
    const table = await screen.findByRole('table')
    expect(within(within(table).getByRole('row', { name: /DSP-0007/ })).getByRole('link', { name: 'INV-0007' })).toHaveAttribute('href', '/invoices/INV-0007')
    expect(within(within(table).getByRole('row', { name: /DSP-0008/ })).getByText('Loading')).toBeInTheDocument()
  })

  it('shows trucks being loaded first', async () => {
    setup([dispatch(), LOADING])
    const table = await screen.findByRole('table')
    const rows = within(table).getAllByRole('row').slice(1)
    expect(rows[0]).toHaveTextContent('DSP-0008')
    expect(rows[1]).toHaveTextContent('DSP-0007')
  })

  it('creates a dispatch with buyer, vehicle and driver, and opens it', async () => {
    setup()
    await userEvent.click(await screen.findByRole('button', { name: /new dispatch/i }))
    const d = await screen.findByRole('dialog')
    await userEvent.selectOptions(await within(d).findByLabelText(/buyer/i), '2')
    await userEvent.type(within(d).getByLabelText(/vehicle/i), 'KA09XY0001')
    await userEvent.type(within(d).getByLabelText(/driver/i), 'Ramesh')
    await userEvent.click(within(d).getByRole('button', { name: /^create dispatch/i }))
    await waitFor(() => expect(api.POST).toHaveBeenCalledWith('/api/dispatches', { body: { buyer_id: 2, vehicle_no: 'KA09XY0001', driver_name: 'Ramesh' } }))
    expect(await screen.findByText('load truck page')).toBeInTheDocument()
  })

  it('needs a buyer and a vehicle number, and the driver is optional', async () => {
    setup()
    await userEvent.click(await screen.findByRole('button', { name: /new dispatch/i }))
    const d = await screen.findByRole('dialog')
    await userEvent.click(within(d).getByRole('button', { name: /^create dispatch/i }))
    expect(await within(d).findByText('Choose the buyer')).toBeInTheDocument()
    expect(within(d).getByText('Enter the vehicle number')).toBeInTheDocument()
    expect(api.POST).not.toHaveBeenCalled()
    await userEvent.selectOptions(within(d).getByLabelText(/buyer/i), '1')
    await userEvent.type(within(d).getByLabelText(/vehicle/i), 'KA01')
    await userEvent.click(within(d).getByRole('button', { name: /^create dispatch/i }))
    await waitFor(() => expect(api.POST).toHaveBeenCalledWith('/api/dispatches', { body: { buyer_id: 1, vehicle_no: 'KA01' } }))
  })

  it("shows the server's reason when the dispatch cannot be created", async () => {
    setup(undefined, { POST: { '/api/dispatches': { status: 422, error: { code: 'VALIDATION_ERROR', message: 'Vehicle number is invalid', field: 'vehicle_no', fields: { vehicle_no: 'Vehicle number is invalid' } } } } })
    await userEvent.click(await screen.findByRole('button', { name: /new dispatch/i }))
    const d = await screen.findByRole('dialog')
    await userEvent.selectOptions(await within(d).findByLabelText(/buyer/i), '1')
    await userEvent.type(within(d).getByLabelText(/vehicle/i), '??')
    await userEvent.click(within(d).getByRole('button', { name: /^create dispatch/i }))
    expect(await within(d).findByText('Vehicle number is invalid')).toBeInTheDocument()
  })

  it('invites the first dispatch when there are none', async () => {
    setup([])
    expect(await screen.findByText(/no dispatches yet/i)).toBeInTheDocument()
  })

  it('shows a Retry state when dispatches cannot be loaded', async () => {
    setup(undefined, { GET: { '/api/dispatches': { status: 500, error: 'boom' } } })
    expect(await screen.findByRole('alert')).toHaveTextContent(/something went wrong/i)
    expect(screen.getByRole('button', { name: /retry/i })).toBeInTheDocument()
  })
})
