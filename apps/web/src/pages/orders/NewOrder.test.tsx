import { fireEvent, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeEach, describe, expect, it, vi } from 'vitest'

vi.mock('@/lib/api/client', () => ({ api: { GET: vi.fn(), POST: vi.fn(), PATCH: vi.fn(), DELETE: vi.fn() } }))
import { api } from '@/lib/api/client'
import { mockApi, renderPage } from '@/test/utils'
import NewOrder from './NewOrder'

const BUYERS = [{ id: 1, name: 'Sharma Fabrics', contact_name: null, phone: null, email: null }]
const FABRICS = [{ id: 1, name: 'Poplin 58in', width_in: 58, wastage_pct: 5, recipe: [] }]
const CREATED = { code: 'ORD-0016' }

const tomorrow = () => {
  const d = new Date()
  d.setDate(d.getDate() + 1)
  return d.toISOString().slice(0, 10)
}
const yesterday = () => {
  const d = new Date()
  d.setDate(d.getDate() - 1)
  return d.toISOString().slice(0, 10)
}

function setup(extra: Parameters<typeof mockApi>[0] = {}) {
  mockApi({
    GET: { '/api/buyers': BUYERS, '/api/fabric-types': FABRICS, ...extra.GET },
    POST: { '/api/orders': CREATED, ...extra.POST },
  })
  return renderPage(<NewOrder />, { extra: [{ path: '/orders/:code', element: <p>order detail page</p> }] })
}

async function fillValid() {
  await userEvent.selectOptions(await screen.findByLabelText(/buyer/i), '1')
  await userEvent.selectOptions(screen.getByLabelText(/fabric/i), '1')
  await userEvent.type(screen.getByLabelText(/colour/i), 'navy')
  await userEvent.type(screen.getByLabelText(/quantity/i), '5000')
  await userEvent.type(screen.getByLabelText(/price per metre/i), '120')
  fireEvent.change(screen.getByLabelText(/deadline/i), { target: { value: tomorrow() } })
}

beforeEach(() => {
  vi.clearAllMocks()
})

describe('NewOrder', () => {
  it('offers the buyers and fabric types from the server', async () => {
    setup()
    expect(await screen.findByRole('option', { name: 'Sharma Fabrics' })).toBeInTheDocument()
    expect(screen.getByRole('option', { name: /Poplin 58in/ })).toBeInTheDocument()
  })

  it('names every missing field and sends nothing', async () => {
    setup()
    await screen.findByRole('option', { name: 'Sharma Fabrics' })
    await userEvent.click(screen.getByRole('button', { name: /create order/i }))
    expect(await screen.findByText('Choose a buyer')).toBeInTheDocument()
    expect(screen.getByText('Choose a fabric')).toBeInTheDocument()
    expect(screen.getByText('Enter the colour')).toBeInTheDocument()
    expect(screen.getByText('Enter the quantity in metres')).toBeInTheDocument()
    expect(screen.getByText('Enter the price per metre')).toBeInTheDocument()
    expect(screen.getByText('Choose a deadline')).toBeInTheDocument()
    expect(api.POST).not.toHaveBeenCalled()
  })

  it('rejects a deadline in the past', async () => {
    setup()
    await fillValid()
    fireEvent.change(screen.getByLabelText(/deadline/i), { target: { value: yesterday() } })
    await userEvent.click(screen.getByRole('button', { name: /create order/i }))
    expect(await screen.findByText('The deadline cannot be in the past')).toBeInTheDocument()
    expect(api.POST).not.toHaveBeenCalled()
  })

  it('rejects a zero quantity and a negative price', async () => {
    setup()
    await fillValid()
    const qty = screen.getByLabelText(/quantity/i)
    await userEvent.clear(qty)
    await userEvent.type(qty, '0')
    const price = screen.getByLabelText(/price per metre/i)
    await userEvent.clear(price)
    await userEvent.type(price, '-3')
    await userEvent.click(screen.getByRole('button', { name: /create order/i }))
    expect(await screen.findAllByText('Must be more than 0')).toHaveLength(2)
    expect(api.POST).not.toHaveBeenCalled()
  })

  it('creates the draft with real numbers and opens it', async () => {
    setup()
    await fillValid()
    await userEvent.click(screen.getByRole('button', { name: /create order/i }))
    await waitFor(() => expect(api.POST).toHaveBeenCalledTimes(1))
    expect(api.POST).toHaveBeenCalledWith('/api/orders', {
      body: { buyer_id: 1, fabric_type_id: 1, colour: 'navy', qty_metres: 5000, price_per_metre: 120, deadline: tomorrow() },
    })
    expect(await screen.findByText('order detail page')).toBeInTheDocument()
  })

  it('shows a server field error under that field', async () => {
    setup({
      POST: { '/api/orders': { status: 422, error: { code: 'VALIDATION_ERROR', message: 'Deadline is too soon', field: 'deadline', fields: { deadline: 'Deadline is too soon' } } } },
    })
    await fillValid()
    await userEvent.click(screen.getByRole('button', { name: /create order/i }))
    expect(await screen.findByText('Deadline is too soon')).toBeInTheDocument()
    expect(screen.getByLabelText(/deadline/i)).toHaveAttribute('aria-invalid', 'true')
    expect(screen.getByLabelText(/colour/i)).toHaveValue('navy')
  })

  it('sends one request when Create order is pressed twice quickly', async () => {
    setup()
    await fillValid()
    vi.mocked(api.POST).mockReturnValue(new Promise(() => {}) as never)
    const form = screen.getByRole('button', { name: /create order/i }).closest('form')!
    fireEvent.submit(form)
    fireEvent.submit(form)
    await waitFor(() => expect(api.POST).toHaveBeenCalledTimes(1))
  })

  it('shows a Retry state when the buyers cannot be loaded', async () => {
    setup({ GET: { '/api/buyers': { status: 500, error: 'boom' } } })
    expect(await screen.findByRole('alert')).toHaveTextContent(/something went wrong/i)
    expect(screen.getByRole('button', { name: /retry/i })).toBeInTheDocument()
  })
})
