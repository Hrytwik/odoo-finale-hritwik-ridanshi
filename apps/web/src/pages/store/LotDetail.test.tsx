import { screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeEach, describe, expect, it, vi } from 'vitest'

vi.mock('@/lib/api/client', () => ({ api: { GET: vi.fn(), POST: vi.fn(), PATCH: vi.fn(), DELETE: vi.fn() } }))
import { api } from '@/lib/api/client'
import { mockApi, renderPage } from '@/test/utils'
import LotDetail from './LotDetail'

const COTTON = { id: 1, code: '30S-COT-RAW', name: '30s cotton', colour: 'raw white' }
const LOT = {
  id: 17, lot_code: 'L-0017', yarn_type: COTTON, supplier: { id: 1, name: 'Vardhman Yarns' }, qty_received_kg: 800, on_hand_kg: 212.5, cost_per_kg: 250,
  challan_no: 'CH-5521', challan_photo_url: null, intended_order_code: 'ORD-0012', received_at: '2026-10-10T09:30:00Z', is_blocked: false, blocked_reason: null,
  movements: [
    { id: 101, lot_code: 'L-0017', kind: 'receipt', qty_kg: 800, run_id: null, order_code: null, machine_code: null, at: '2026-10-10T09:30:00Z', by: 'store', note: null },
    { id: 102, lot_code: 'L-0017', kind: 'issue', qty_kg: -587.5, run_id: 41, order_code: 'ORD-0012', machine_code: 'SPIN-01', at: '2026-10-10T11:30:00Z', by: 'supervisor', note: null },
  ],
}
const BLOCKED = { ...LOT, is_blocked: true, blocked_reason: 'Moisture too high' }
const roll = (code: string, status: string, dispatch: string | null = null) => ({ roll_code: code, order_code: 'ORD-0012', buyer_name: 'Sharma Fabrics', metres: 110, status, dispatch_code: dispatch })
const RECALL = {
  lot_code: 'L-0017', is_blocked: true,
  on_floor: [roll('R-0150', 'dyeing')],
  in_store: [roll('R-0142', 'in_store'), roll('R-0143', 'in_store')],
  loading: [],
  dispatched: [roll('R-0131', 'dispatched', 'DSP-0007')],
  buyers: [{ buyer_id: 1, buyer_name: 'Sharma Fabrics', roll_count: 4, dispatched_roll_count: 1, dispatch_codes: ['DSP-0007'] }],
}
const me = (role: string) => ({ id: 1, username: role, role, display_name: role, worker_id: null, buyer_id: null })

function setup(role = 'store', lot: unknown = LOT, extra: Parameters<typeof mockApi>[0] = {}) {
  mockApi({
    GET: { '/api/auth/me': me(role), '/api/lots/{lot_code}': lot, '/api/lots/{lot_code}/recall': RECALL, ...extra.GET },
    POST: { '/api/lots/{lot_code}/block': BLOCKED, ...extra.POST },
  })
  return renderPage(<LotDetail />, { path: '/store/lots/:code', route: '/store/lots/L-0017' })
}

beforeEach(() => {
  vi.clearAllMocks()
})

describe('LotDetail', () => {
  it('identifies the lot, its supplier and its challan', async () => {
    setup()
    expect(await screen.findByRole('heading', { level: 1, name: 'L-0017' })).toBeInTheDocument()
    expect(screen.getByText(/30s cotton/)).toBeInTheDocument()
    expect(screen.getByText(/Vardhman Yarns/)).toBeInTheDocument()
    expect(screen.getByText(/CH-5521/)).toBeInTheDocument()
    expect(screen.getByText('OK to use')).toBeInTheDocument()
  })

  it('shows received, on hand and the value still on the shelf', async () => {
    setup()
    await screen.findByRole('heading', { level: 1, name: 'L-0017' })
    expect(screen.getByText('Received').closest('.kpi')).toHaveTextContent('800 kg')
    expect(screen.getByText('On hand').closest('.kpi')).toHaveTextContent('212.5 kg')
    expect(screen.getByText('Value on hand').closest('.kpi')).toHaveTextContent('₹53,125')
  })

  it('lists every stock movement, with where issued yarn went', async () => {
    setup()
    const table = await screen.findByRole('table')
    const issue = within(table).getByRole('row', { name: /issue/i })
    expect(issue).toHaveTextContent('-587.5 kg')
    expect(issue).toHaveTextContent('ORD-0012')
    expect(issue).toHaveTextContent('SPIN-01')
    expect(within(table).getByRole('row', { name: /receipt/i })).toHaveTextContent('800 kg')
  })

  it('blocks a lot only with a reason, then shows who is exposed', async () => {
    setup('store')
    await userEvent.click(await screen.findByRole('button', { name: /block this lot/i }))
    const dialog = await screen.findByRole('dialog')
    await userEvent.click(within(dialog).getByRole('button', { name: /^block lot/i }))
    expect(await within(dialog).findByText('Say why the lot is being blocked')).toBeInTheDocument()
    expect(api.POST).not.toHaveBeenCalled()
    await userEvent.type(within(dialog).getByLabelText(/reason/i), 'Moisture too high')
    await userEvent.click(within(dialog).getByRole('button', { name: /^block lot/i }))
    await waitFor(() =>
      expect(api.POST).toHaveBeenCalledWith('/api/lots/{lot_code}/block', { params: { path: { lot_code: 'L-0017' } }, body: { reason: 'Moisture too high' } }),
    )
  })

  it('shows a blocked lot with its reason and the full recall exposure', async () => {
    setup('owner', BLOCKED)
    expect(await screen.findByText('Blocked')).toBeInTheDocument()
    expect(screen.getByText(/Moisture too high/)).toBeInTheDocument()
    const recall = (await screen.findByText(/on the floor/i)).closest('section')!
    expect(recall).toHaveTextContent('R-0150')
    expect(recall).toHaveTextContent('R-0142')
    expect(recall).toHaveTextContent('R-0131')
    expect(within(recall).getByText('DSP-0007', { selector: 'td, span' })).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: /block this lot/i })).not.toBeInTheDocument()
  })

  it('summarises the buyers who already received yarn from this lot', async () => {
    setup('owner', BLOCKED)
    const buyers = (await screen.findByText(/buyers to contact/i)).closest('section')!
    expect(buyers).toHaveTextContent('Sharma Fabrics')
    expect(buyers).toHaveTextContent('1 of 4')
  })

  it('does not load the exposure until asked, for a lot that is still usable', async () => {
    setup('owner', LOT)
    await screen.findByRole('heading', { level: 1, name: 'L-0017' })
    expect(vi.mocked(api.GET).mock.calls.map((c) => c[0])).not.toContain('/api/lots/{lot_code}/recall')
    await userEvent.click(screen.getByRole('button', { name: /see what this lot touched/i }))
    expect(await screen.findByText(/on the floor/i)).toBeInTheDocument()
  })

  it('links each affected roll to its passport', async () => {
    setup('owner', BLOCKED)
    const link = await screen.findByRole('link', { name: 'R-0150' })
    expect(link).toHaveAttribute('href', '/r/R-0150')
  })

  it('shows the server message when blocking fails', async () => {
    setup('store', LOT, {
      POST: { '/api/lots/{lot_code}/block': { status: 409, error: { code: 'FORBIDDEN', message: 'You do not have access to this', field: null, fields: null } } },
    })
    await userEvent.click(await screen.findByRole('button', { name: /block this lot/i }))
    const dialog = await screen.findByRole('dialog')
    await userEvent.type(within(dialog).getByLabelText(/reason/i), 'Dirty')
    await userEvent.click(within(dialog).getByRole('button', { name: /^block lot/i }))
    expect(await within(dialog).findByRole('alert')).toHaveTextContent(/do not have access/i)
  })

  it('says so plainly when the lot does not exist', async () => {
    setup('store', LOT, { GET: { '/api/lots/{lot_code}': { status: 404, error: { code: 'NOT_FOUND', message: 'Lot not found', field: null, fields: null } } } })
    expect(await screen.findByRole('alert')).toHaveTextContent('Lot not found')
  })
})
