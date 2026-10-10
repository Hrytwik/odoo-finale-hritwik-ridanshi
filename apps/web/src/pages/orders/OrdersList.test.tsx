import { screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeEach, describe, expect, it, vi } from 'vitest'

vi.mock('@/lib/api/client', () => ({ api: { GET: vi.fn(), POST: vi.fn(), PATCH: vi.fn(), DELETE: vi.fn() } }))
import { mockApi, renderPage } from '@/test/utils'
import OrdersList from './OrdersList'

const progress = { need_kg: 630, spun_kg: 587.5, woven_m: 2310, dyed_m: 1540, passed_m: 1210, rejected_m: 110, dispatched_m: 330 }
const base = {
  buyer: { id: 1, name: 'Sharma Fabrics' },
  fabric_type: { id: 1, name: 'Poplin 58in' },
  colour: 'navy',
  price_per_metre: 120,
  created_at: '2026-10-01T10:00:00Z',
  progress,
}
const LATE = {
  ...base,
  id: 12, code: 'ORD-0012', qty_metres: 5000, deadline: '2026-10-20', state: 'confirmed', stage: 'weaving',
  confirmed_at: '2026-10-01T11:00:00Z', yarn_status: 'short', short_kg: 230, delivery_date: '2026-10-22', days_late: 2,
}
const DRAFT = {
  ...base,
  id: 15, code: 'ORD-0015', qty_metres: 1200, deadline: '2026-10-30', state: 'draft', stage: 'draft', confirmed_at: null,
  progress: { ...progress, spun_kg: 0, woven_m: 0, dyed_m: 0, passed_m: 0, rejected_m: 0, dispatched_m: 0 },
  yarn_status: 'can_start', short_kg: 0, delivery_date: null, days_late: null,
}
const ON_TIME = { ...LATE, id: 13, code: 'ORD-0013', yarn_status: 'can_start', short_kg: 0, days_late: 0, delivery_date: '2026-10-19', buyer: { id: 2, name: 'Patel Textiles' } }

const me = (role: string) => ({ id: 1, username: role, role, display_name: role, worker_id: null, buyer_id: null })

function setup(role = 'owner', orders: unknown[] = [LATE, DRAFT, ON_TIME]) {
  mockApi({ GET: { '/api/orders': orders, '/api/auth/me': me(role) } })
  return renderPage(<OrdersList />)
}

beforeEach(() => {
  vi.clearAllMocks()
})

describe('OrdersList', () => {
  it('lists every order with buyer, fabric, quantity and stage', async () => {
    setup()
    const table = await screen.findByRole('table')
    const row = within(table).getByRole('row', { name: /ORD-0012/ })
    expect(row).toHaveTextContent('Sharma Fabrics')
    expect(row).toHaveTextContent('Poplin 58in')
    expect(row).toHaveTextContent('5,000 m')
    expect(row).toHaveTextContent('Weaving')
    expect(within(row).getByRole('link', { name: 'ORD-0012' })).toHaveAttribute('href', '/orders/ORD-0012')
  })

  it('shows how late an order will be, and says nothing for one on time', async () => {
    setup()
    const table = await screen.findByRole('table')
    expect(within(within(table).getByRole('row', { name: /ORD-0012/ })).getByText('2 days late')).toBeInTheDocument()
    expect(within(within(table).getByRole('row', { name: /ORD-0013/ })).queryByText(/late/i)).not.toBeInTheDocument()
  })

  it('shows whether there is enough yarn to start', async () => {
    setup()
    const table = await screen.findByRole('table')
    expect(within(within(table).getByRole('row', { name: /ORD-0012/ })).getByText('Short 230 kg')).toBeInTheDocument()
    expect(within(within(table).getByRole('row', { name: /ORD-0013/ })).getByText('Yarn ready')).toBeInTheDocument()
  })

  it('filters to late orders and back to all', async () => {
    setup()
    await screen.findByRole('table')
    await userEvent.click(screen.getByRole('button', { name: /^late/i }))
    expect(screen.getByRole('row', { name: /ORD-0012/ })).toBeInTheDocument()
    expect(screen.queryByRole('row', { name: /ORD-0013/ })).not.toBeInTheDocument()
    expect(screen.queryByRole('row', { name: /ORD-0015/ })).not.toBeInTheDocument()
    await userEvent.click(screen.getByRole('button', { name: /^all/i }))
    expect(screen.getByRole('row', { name: /ORD-0015/ })).toBeInTheDocument()
  })

  it('filters to drafts', async () => {
    setup()
    await screen.findByRole('table')
    await userEvent.click(screen.getByRole('button', { name: /^drafts/i }))
    expect(screen.getByRole('row', { name: /ORD-0015/ })).toBeInTheDocument()
    expect(screen.queryByRole('row', { name: /ORD-0012/ })).not.toBeInTheDocument()
  })

  it('offers New order to the owner and the accountant', async () => {
    setup('owner')
    expect(await screen.findByRole('link', { name: /new order/i })).toHaveAttribute('href', '/orders/new')
  })

  it('does not offer New order to the supervisor', async () => {
    setup('supervisor')
    await screen.findByRole('table')
    expect(screen.queryByRole('link', { name: /new order/i })).not.toBeInTheDocument()
  })

  it('invites the first order when there are none', async () => {
    setup('owner', [])
    expect(await screen.findByText(/no orders yet/i)).toBeInTheDocument()
  })

  it('shows a Retry state when orders cannot be loaded', async () => {
    mockApi({ GET: { '/api/orders': { status: 500, error: 'boom' }, '/api/auth/me': me('owner') } })
    renderPage(<OrdersList />)
    expect(await screen.findByRole('alert')).toHaveTextContent(/something went wrong/i)
    expect(screen.getByRole('button', { name: /retry/i })).toBeInTheDocument()
  })
})

describe('OrdersList search', () => {
  it('finds an order by its code, buyer or colour as you type', async () => {
    setup()
    const box = await screen.findByRole('searchbox', { name: 'Find an order' })
    await userEvent.type(box, 'patel')
    const table = await screen.findByRole('table')
    expect(within(table).getByRole('row', { name: /ORD-0013/ })).toBeInTheDocument()
    expect(within(table).queryByRole('row', { name: /ORD-0012/ })).not.toBeInTheDocument()
    await userEvent.clear(box)
    await userEvent.type(box, 'ORD-0015')
    expect(within(await screen.findByRole('table')).getAllByRole('row')).toHaveLength(2)
  })

  it('says so when nothing matches the search', async () => {
    setup()
    await userEvent.type(await screen.findByRole('searchbox', { name: 'Find an order' }), 'zzz')
    expect(await screen.findByText('No order matches your search')).toBeInTheDocument()
  })
})
