import { fireEvent, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeEach, describe, expect, it, vi } from 'vitest'

vi.mock('@/lib/api/client', () => ({ api: { GET: vi.fn(), POST: vi.fn(), PATCH: vi.fn(), DELETE: vi.fn() } }))
import { api } from '@/lib/api/client'
import { mockApi, renderPage } from '@/test/utils'
import OrderDetail from './OrderDetail'

const COTTON = { id: 1, code: '30S-COT-RAW', name: '30s cotton', colour: 'raw white' }
const ORDER = {
  id: 12, code: 'ORD-0012', buyer: { id: 1, name: 'Sharma Fabrics' }, fabric_type: { id: 1, name: 'Poplin 58in' }, colour: 'navy',
  qty_metres: 5000, price_per_metre: 120, deadline: '2026-10-20', state: 'confirmed', stage: 'weaving',
  created_at: '2026-10-01T10:00:00Z', confirmed_at: '2026-10-01T11:00:00Z',
  progress: { need_kg: 630, spun_kg: 587.5, woven_m: 2310, dyed_m: 1540, passed_m: 1210, rejected_m: 110, dispatched_m: 330 },
  yarn_status: 'short', short_kg: 230, delivery_date: '2026-10-22', days_late: 2,
}
const DRAFT = { ...ORDER, code: 'ORD-0015', id: 15, state: 'draft', stage: 'draft', confirmed_at: null, delivery_date: null, days_late: null }
const ETA = {
  order_code: 'ORD-0012', buyer_name: 'Sharma Fabrics', deadline: '2026-10-20', delivery_date: '2026-10-22', days_late: 2, bottleneck_stage: 'weaving',
  stages: [{ stage: 'spinning', finish_date: '2026-10-12' }, { stage: 'weaving', finish_date: '2026-10-19' }, { stage: 'dyeing', finish_date: '2026-10-20' }],
  what_ifs: [
    { kind: 'add_shift', label: 'Add a third shift on weaving', delivery_date: '2026-10-20', days_late: 0 },
    { kind: 'move_to_front', label: 'Move ORD-0012 to the front of every queue', delivery_date: '2026-10-21', days_late: 1 },
  ],
}
const YARN_CHECK = {
  order_code: 'ORD-0012', can_start: false,
  lines: [{ yarn_type: COTTON, need_kg: 630, issued_kg: 0, outstanding_kg: 630, available_kg: 400, short_kg: 230 }],
}
const COST = {
  order_code: 'ORD-0012', parts: { yarn: 146875, machine: 52300, labour: 28800, rework: 18400 }, reject_cost: 13600, total: 246375,
  good_metres: 1210, rejected_metres: 110, cost_per_good_metre: 203.6, revenue: 145200, profit: -101175, unabsorbed: 0, provisional: true, warnings: ['Run 52 has no attendance for its operator'],
}
const me = (role: string) => ({ id: 1, username: role, role, display_name: role, worker_id: null, buyer_id: null })

function setup(role = 'owner', order: unknown = ORDER, extra: Parameters<typeof mockApi>[0] = {}) {
  const code = (order as { code: string }).code
  mockApi({
    GET: {
      '/api/auth/me': me(role), '/api/orders/{order_code}': order, '/api/orders/{order_code}/eta': ETA,
      '/api/orders/{order_code}/yarn-check': YARN_CHECK, '/api/costing/orders/{order_code}': COST, '/api/dispatches': [], ...extra.GET,
    },
    POST: { '/api/orders/{order_code}/confirm': { ...ORDER, state: 'confirmed' }, '/api/orders/{order_code}/cancel': { ...ORDER, state: 'cancelled', stage: 'cancelled' }, ...extra.POST },
    PATCH: { '/api/orders/{order_code}': { ...ORDER, deadline: '2026-10-25' }, ...extra.PATCH },
  })
  return renderPage(<OrderDetail />, { path: '/orders/:code', route: `/orders/${code}` })
}

beforeEach(() => {
  vi.clearAllMocks()
})

describe('OrderDetail', () => {
  it('shows the order, its buyer, stage and money', async () => {
    setup()
    expect(await screen.findByRole('heading', { level: 1, name: 'ORD-0012' })).toBeInTheDocument()
    expect(screen.getByText(/Sharma Fabrics/)).toBeInTheDocument()
    expect(screen.getAllByText('Weaving').length).toBeGreaterThan(0)
    expect(screen.getByText('5,000 m')).toBeInTheDocument()
    expect(screen.getByText('₹120')).toBeInTheDocument()
  })

  it('shows progress against the order quantity', async () => {
    setup()
    const spun = await screen.findByRole('progressbar', { name: /spun/i })
    expect(spun).toHaveAttribute('aria-valuenow', '588')
    expect(screen.getByRole('progressbar', { name: /passed quality check/i })).toHaveAttribute('aria-valuenow', '1210')
    expect(screen.getByRole('progressbar', { name: /rejected/i })).toHaveAttribute('aria-valuenow', '110')
  })

  it('explains the delivery date, how late it is, the bottleneck and the tested what-ifs', async () => {
    setup()
    const card = (await screen.findByText(/expected delivery/i)).closest('section')!
    expect(card).toHaveTextContent('22 Oct 2026')
    expect(card).toHaveTextContent('2 days late')
    expect(card).toHaveTextContent(/bottleneck/i)
    expect(card).toHaveTextContent('Add a third shift on weaving')
    expect(card).toHaveTextContent('on time')
    expect(card).toHaveTextContent('Move ORD-0012 to the front of every queue')
    expect(card).toHaveTextContent('1 day late')
  })

  it('shows whether there is enough yarn and by how much it falls short', async () => {
    setup()
    const card = (await screen.findByText(/short 230 kg/i)).closest('section')!
    expect(card).toHaveTextContent('Short 230 kg')
    expect(within(card).getByRole('row', { name: /30s cotton/i })).toHaveTextContent('400 kg')
  })

  it('shows cost, revenue and a loss in red to the owner, with its caveats', async () => {
    setup('owner')
    const card = (await screen.findByText('Total cost')).closest('section')!
    expect(card).toHaveTextContent('₹2,46,375')
    expect(card).toHaveTextContent('₹1,45,200')
    expect(within(card).getByText('-₹1,01,175').closest('.kpi-value')).toHaveClass('text-danger')
    expect(card).toHaveTextContent(/provisional/i)
    expect(card).toHaveTextContent('Run 52 has no attendance for its operator')
    expect(card).toHaveTextContent('₹1,46,875')
  })

  it('hides cost and profit from the supervisor and never asks for them', async () => {
    setup('supervisor')
    await screen.findByRole('heading', { level: 1, name: 'ORD-0012' })
    expect(screen.queryByText('Cost and profit')).not.toBeInTheDocument()
    expect(vi.mocked(api.GET).mock.calls.map((c) => c[0])).not.toContain('/api/costing/orders/{order_code}')
  })

  it('lets the owner confirm a draft, after asking', async () => {
    setup('owner', DRAFT)
    await userEvent.click(await screen.findByRole('button', { name: /confirm order/i }))
    const dialog = await screen.findByRole('dialog')
    await userEvent.click(within(dialog).getByRole('button', { name: /^confirm order/i }))
    await waitFor(() => expect(api.POST).toHaveBeenCalledWith('/api/orders/{order_code}/confirm', { params: { path: { order_code: 'ORD-0015' } } }))
  })

  it('does not offer confirm on an order that is already confirmed', async () => {
    setup('owner')
    await screen.findByRole('heading', { level: 1, name: 'ORD-0012' })
    expect(screen.queryByRole('button', { name: /confirm order/i })).not.toBeInTheDocument()
  })

  it('does not offer any action to the supervisor', async () => {
    setup('supervisor', DRAFT)
    await screen.findByRole('heading', { level: 1, name: 'ORD-0015' })
    expect(screen.queryByRole('button', { name: /confirm order/i })).not.toBeInTheDocument()
    expect(screen.queryByRole('button', { name: /cancel order/i })).not.toBeInTheDocument()
  })

  it('shows the server reason when an order cannot be cancelled', async () => {
    setup('owner', ORDER, {
      POST: { '/api/orders/{order_code}/cancel': { status: 409, error: { code: 'ORDER_HAS_RUNS', message: 'This order has production runs, so it cannot be cancelled', field: null, fields: null } } },
    })
    await userEvent.click(await screen.findByRole('button', { name: /cancel order/i }))
    const dialog = await screen.findByRole('dialog')
    await userEvent.click(within(dialog).getByRole('button', { name: /yes, cancel/i }))
    expect(await within(dialog).findByRole('alert')).toHaveTextContent(/production runs/i)
  })

  it('changes the deadline', async () => {
    setup('owner')
    await userEvent.click(await screen.findByRole('button', { name: /change deadline/i }))
    const dialog = await screen.findByRole('dialog')
    fireEvent.change(within(dialog).getByLabelText(/new deadline/i), { target: { value: '2099-10-25' } })
    await userEvent.click(within(dialog).getByRole('button', { name: /save deadline/i }))
    await waitFor(() =>
      expect(api.PATCH).toHaveBeenCalledWith('/api/orders/{order_code}', { params: { path: { order_code: 'ORD-0012' } }, body: { deadline: '2099-10-25' } }),
    )
  })

  it('says so plainly when the order does not exist', async () => {
    setup('owner', ORDER, { GET: { '/api/orders/{order_code}': { status: 404, error: { code: 'NOT_FOUND', message: 'Order not found', field: null, fields: null } } } })
    expect(await screen.findByRole('alert')).toHaveTextContent('Order not found')
  })
})
