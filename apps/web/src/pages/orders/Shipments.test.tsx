import { screen } from '@testing-library/react'
import { beforeEach, describe, expect, it, vi } from 'vitest'

vi.mock('@/lib/api/client', () => ({ api: { GET: vi.fn(), POST: vi.fn(), PATCH: vi.fn(), DELETE: vi.fn() } }))
import { mockApi, renderPage } from '@/test/utils'
import { ShipmentsCard } from './Shipments'

const order = (progress: Record<string, number>, qty = 5000) =>
  ({
    id: 1, code: 'ORD-0001', buyer: { id: 1, name: 'Sharma Fabrics' }, fabric_type: { id: 1, name: 'Poplin 58in' }, colour: 'navy',
    qty_metres: qty, price_per_metre: 120, deadline: '2026-10-24', state: 'confirmed', stage: 'partly_dispatched',
    created_at: '2026-10-01T10:00:00Z', confirmed_at: '2026-10-01T11:00:00Z',
    progress: { need_kg: 630, spun_kg: 630, woven_m: 5000, dyed_m: 5000, passed_m: 0, rejected_m: 0, dispatched_m: 0, ...progress },
    yarn_status: 'ok', short_kg: 0, delivery_date: '2026-10-15', days_late: 0,
  }) as never

const roll = (code: string, order_code: string, metres: number) => ({ code, order_code, metres, status: 'dispatched' })
const truck = (code: string, rolls: ReturnType<typeof roll>[], extra = {}) => ({
  id: 1, code, buyer: { id: 1, name: 'Sharma Fabrics' }, vehicle_no: 'KA01AB1234', driver_name: null, state: 'dispatched',
  created_at: '2026-10-10T08:00:00Z', dispatched_at: '2026-10-10T09:00:00Z', rolls, total_metres: rolls.reduce((s, r) => s + r.metres, 0),
  orders: [...new Set(rolls.map((r) => r.order_code))].map((c) => ({ order_code: c, ordered_m: 5000, previously_dispatched_m: 0, loaded_m: 0, remaining_m: 0, over_shipped: false })),
  invoice_no: 'INV-0001', warnings: [], ...extra,
})

beforeEach(() => vi.clearAllMocks())

describe('Shipments card', () => {
  it('shows the balance and only this order\u2019s share of each truck', async () => {
    mockApi({ GET: { '/api/dispatches': [truck('D-0001', [roll('R-1', 'ORD-0001', 2000), roll('R-2', 'ORD-0002', 900)])] } })
    renderPage(<ShipmentsCard order={order({ passed_m: 3000, dispatched_m: 2000 })} />)
    expect(await screen.findByText('D-0001')).toBeInTheDocument()
    expect(screen.getByText(/2,000 m of 5,000 m has been sent/)).toBeInTheDocument()
    expect(screen.getByText(/1,000 m is ready in store waiting for a truck/)).toBeInTheDocument()
    expect(screen.getByText(/2,000 m is still being made/)).toBeInTheDocument()
    expect(screen.queryByText('2,900 m')).not.toBeInTheDocument()
    expect(screen.getByRole('link', { name: 'INV-0001' })).toHaveAttribute('href', '/invoices/INV-0001')
    expect(screen.getByRole('button', { name: /Plan the next truck/ })).toBeInTheDocument()
  })

  it('says so when nothing more is coming and the order will fall short', async () => {
    mockApi({ GET: { '/api/dispatches': [truck('D-0001', [roll('R-1', 'ORD-0001', 4000)])] } })
    renderPage(<ShipmentsCard order={order({ passed_m: 4000, dispatched_m: 4000, rejected_m: 1000 })} />)
    expect(await screen.findByText(/fall short by 0 m|fall short by/)).toBeInTheDocument()
  })

  it('has nothing to plan once everything has been sent', async () => {
    mockApi({ GET: { '/api/dispatches': [truck('D-0001', [roll('R-1', 'ORD-0001', 5000)])] } })
    renderPage(<ShipmentsCard order={order({ passed_m: 5000, dispatched_m: 5000 })} />)
    expect(await screen.findByText(/All 5,000 m has been sent/)).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: /Plan the next truck/ })).not.toBeInTheDocument()
  })

  it('says nothing has left the mill when there are no trucks', async () => {
    mockApi({ GET: { '/api/dispatches': [] } })
    renderPage(<ShipmentsCard order={order({ passed_m: 0 })} />)
    expect(await screen.findByText('Nothing has left the mill yet.')).toBeInTheDocument()
  })
})
