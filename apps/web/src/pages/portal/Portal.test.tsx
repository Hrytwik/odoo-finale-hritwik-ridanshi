import { screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeEach, describe, expect, it, vi } from 'vitest'

vi.mock('@/lib/api/client', () => ({ api: { GET: vi.fn(), POST: vi.fn(), PATCH: vi.fn(), DELETE: vi.fn() } }))
import { api } from '@/lib/api/client'
import { mockApi, renderPage } from '@/test/utils'
import PortalHome from './PortalHome'
import PortalOrder from './PortalOrder'

const ORDER = { code: 'ORD-0001', fabric: 'Poplin 58in', colour: 'navy', qty_metres: 5000, stage: 'dyeing', progress_pct: 23.1, deadline: '2026-10-20', delivery_date: null }
const DETAIL = {
  ...ORDER,
  timeline: [
    { at: '2026-10-01T10:00:00Z', label: 'Order confirmed' },
    { at: '2026-10-09T10:00:00Z', label: '330 m dispatched (DSP-0007)' },
  ],
  dispatches: [{ code: 'DSP-0007', dispatched_at: '2026-10-09T10:00:00Z', metres: 330, invoice_no: 'INV-0007' }],
}
const CHAT = { answer: 'Your order is in dyeing.', model: 'm', provider: 'p', sources: [{ tool: 'get_my_orders', input: {}, summary: 'ORD-0001 dyeing' }] }
const post = vi.mocked(api.POST)
beforeEach(() => vi.clearAllMocks())

describe('buyer portal home', () => {
  it('lists each order with its stage, size and promised date', async () => {
    mockApi({ GET: { '/api/portal/orders': [ORDER] } })
    renderPage(<PortalHome />)
    const card = await screen.findByRole('link', { name: 'Order ORD-0001' })
    expect(card).toHaveAttribute('href', '/portal/orders/ORD-0001')
    expect(card).toHaveTextContent('Poplin 58in')
    expect(card).toHaveTextContent('5,000')
    expect(card).toHaveTextContent('Promised for')
    expect(card).toHaveTextContent('20 Oct 2026')
  })

  it('shows the expected date once the mill has one', async () => {
    mockApi({ GET: { '/api/portal/orders': [{ ...ORDER, delivery_date: '2026-10-22' }] } })
    renderPage(<PortalHome />)
    expect(await screen.findByText(/Expected/)).toHaveTextContent('22 Oct 2026')
  })

  it('says so when there are no orders', async () => {
    mockApi({ GET: { '/api/portal/orders': [] } })
    renderPage(<PortalHome />)
    expect(await screen.findByText('No orders yet')).toBeInTheDocument()
  })

  it('answers a question from the buyer assistant and shows its sources', async () => {
    mockApi({ GET: { '/api/portal/orders': [ORDER] }, POST: { '/api/ai/buyer-assistant': CHAT } })
    renderPage(<PortalHome />)
    await userEvent.click(await screen.findByRole('button', { name: 'Will my order make its deadline?' }))
    expect(await screen.findByText('Your order is in dyeing.')).toBeInTheDocument()
    expect(post).toHaveBeenCalledWith('/api/ai/buyer-assistant', { body: { question: 'Will my order make its deadline?', history: [] } })
    expect(screen.getByText('ORD-0001 dyeing')).toBeInTheDocument()
  })
})

describe('buyer portal order', () => {
  const open = () => renderPage(<PortalOrder />, { route: '/portal/orders/ORD-0001', path: '/portal/orders/:code' })

  it('shows what has happened and each truck with a link to its invoice', async () => {
    mockApi({ GET: { '/api/portal/orders/{order_code}': DETAIL } })
    open()
    const history = await screen.findByRole('region', { name: 'What has happened' })
    expect(within(history).getByText('Order confirmed')).toBeInTheDocument()
    expect(within(history).getByText('330 m dispatched (DSP-0007)')).toBeInTheDocument()
    const trucks = screen.getByRole('region', { name: 'Dispatches' })
    expect(within(trucks).getByRole('link', { name: 'INV-0007' })).toHaveAttribute('href', '/invoices/INV-0007')
    expect(trucks).toHaveTextContent('330')
  })

  it('says nothing has been sent when nothing has', async () => {
    mockApi({ GET: { '/api/portal/orders/{order_code}': { ...DETAIL, dispatches: [] } } })
    open()
    expect(await screen.findByText('Nothing has been sent yet.')).toBeInTheDocument()
  })

  it('shows a plain message for an order that is not theirs or does not exist', async () => {
    mockApi({ GET: { '/api/portal/orders/{order_code}': { status: 404, error: { code: 'NOT_FOUND', message: 'Order not found', field: null, fields: null } } } })
    open()
    expect(await screen.findByText('We could not find that order')).toBeInTheDocument()
    expect(screen.getByRole('link', { name: /my orders/i })).toHaveAttribute('href', '/portal')
  })
})
