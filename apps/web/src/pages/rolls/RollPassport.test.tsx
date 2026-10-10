import { screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeEach, describe, expect, it, vi } from 'vitest'

vi.mock('@/lib/api/client', () => ({ api: { GET: vi.fn(), POST: vi.fn(), PATCH: vi.fn(), DELETE: vi.fn() } }))
import { mockApi, renderPage } from '@/test/utils'
import RollPassport from './RollPassport'

const ROLL = { id: 142, code: 'R-0142', order_code: 'ORD-0012', buyer_name: 'Sharma Fabrics', fabric: 'Poplin 58in', colour: 'navy', metres: 110, status: 'in_store', created_at: '2026-10-10T10:00:00Z' }
const PASSPORT = {
  roll: ROLL, order_code: 'ORD-0012', buyer_name: 'Sharma Fabrics', deadline: '2026-10-20',
  yarn_lots: [{ lot_code: 'L-0017', yarn_type: '30s cotton', supplier: 'Vardhman Yarns', is_blocked: false }],
  runs: [
    { id: 45, stage: 'weaving', machine_code: 'LOOM-04', machine_name: 'Loom 4', operator: 'Ravi Kumar', started_at: '2026-10-08T08:00:00Z', ended_at: null },
    { id: 41, stage: 'spinning', machine_code: 'SPIN-01', machine_name: 'Ring frame 1', operator: 'Ravi Kumar', started_at: '2026-10-07T08:00:00Z', ended_at: '2026-10-07T20:00:00Z' },
  ],
  inspections: [
    {
      id: 301, roll_code: 'R-0142', inspector: { id: 2, name: 'Meena Devi' }, inspected_at: '2026-10-09T12:00:00Z', verdict: 'rework', overrode_ai: true,
      defects: [{ defect_type: 'hole', count: 2, ai_detected: true }], photo_url: null, ai_suggestion: null, notes: 'Hole near the selvedge',
    },
  ],
  cost: { roll_code: 'R-0142', parts: { yarn: 3465, machine: 1210, labour: 640, rework: 380 }, reject_share: 260, total: 5955, per_metre: 54.14, provisional: true },
  dispatch: null,
}
const DISPATCHED = { ...PASSPORT, roll: { ...ROLL, status: 'dispatched' }, dispatch: { code: 'DSP-0007', dispatched_at: '2026-10-09T15:00:00Z', vehicle_no: 'KA01AB1234', invoice_no: 'INV-0007' } }
const me = (role: string) => ({ id: 1, username: role, role, display_name: role, worker_id: null, buyer_id: null })

function setup(role = 'owner', passport: unknown = PASSPORT, extra: Parameters<typeof mockApi>[0] = {}) {
  mockApi({ GET: { '/api/auth/me': me(role), '/api/rolls/{roll_code}/passport': passport, ...extra.GET } })
  return renderPage(<RollPassport />, { path: '/r/:code', route: '/r/R-0142', extra: [{ path: '/r/:code', element: <p>x</p> }] })
}

beforeEach(() => {
  vi.clearAllMocks()
})

describe('RollPassport: the roll', () => {
  it('shows the roll, its status, order, buyer and length', async () => {
    setup()
    expect(await screen.findByRole('heading', { level: 1, name: 'R-0142' })).toBeInTheDocument()
    expect(screen.getByText('In store')).toBeInTheDocument()
    expect(screen.getByRole('link', { name: 'ORD-0012' })).toHaveAttribute('href', '/orders/ORD-0012')
    expect(screen.getAllByText(/Sharma Fabrics/).length).toBeGreaterThan(0)
    expect(screen.getByText(/110 m/)).toBeInTheDocument()
    expect(screen.getByText(/Poplin 58in/)).toBeInTheDocument()
  })

  it('has a QR tag that points to this roll, and a print button', async () => {
    setup()
    expect(await screen.findByRole('img', { name: 'QR code for roll R-0142' })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /print label/i })).toBeInTheDocument()
  })
})

describe('RollPassport: its life', () => {
  it('lists the yarn lots, and flags a recalled one', async () => {
    setup('owner', { ...PASSPORT, yarn_lots: [{ ...PASSPORT.yarn_lots[0], is_blocked: true }] })
    const lot = await screen.findByRole('link', { name: 'L-0017' })
    expect(lot).toHaveAttribute('href', '/store/lots/L-0017')
    expect(screen.getByText('Recalled')).toBeInTheDocument()
  })

  it('lists the runs in the order they happened, oldest first', async () => {
    setup()
    const timeline = (await screen.findByRole('heading', { name: 'Machines' })).closest('section')!
    const items = within(timeline).getAllByRole('listitem').map((li) => li.textContent ?? '')
    expect(items[0]).toContain('Spinning')
    expect(items[0]).toContain('Ring frame 1')
    expect(items[1]).toContain('Weaving')
    expect(items[1]).toContain('Loom 4')
    expect(items[1]).toContain('Ravi Kumar')
  })

  it('shows each quality check with who did it, what was found and whether the AI was overruled', async () => {
    setup()
    const qc = (await screen.findByText('Quality checks')).closest('section')!
    expect(qc).toHaveTextContent('Meena Devi')
    expect(qc).toHaveTextContent('Rework')
    expect(qc).toHaveTextContent('2 holes')
    expect(qc).toHaveTextContent('Hole near the selvedge')
    expect(qc).toHaveTextContent(/overrode the AI/i)
  })

  it('says the roll has not been checked yet when there is no inspection', async () => {
    setup('owner', { ...PASSPORT, inspections: [] })
    expect(await screen.findByText(/not been checked yet/i)).toBeInTheDocument()
  })

  it('shows the dispatch, vehicle and a link to the invoice', async () => {
    setup('owner', DISPATCHED)
    const card = (await screen.findByText('Dispatch')).closest('section')!
    expect(card).toHaveTextContent('DSP-0007')
    expect(card).toHaveTextContent('KA01AB1234')
    expect(within(card).getByRole('link', { name: 'INV-0007' })).toHaveAttribute('href', '/invoices/INV-0007')
  })

  it('says the roll has not been dispatched when it has not', async () => {
    setup()
    expect(await screen.findByText(/not been dispatched/i)).toBeInTheDocument()
  })
})

describe('RollPassport: the true cost', () => {
  it('shows the cost per metre, labelled provisional while the order is not finished', async () => {
    setup('owner')
    const card = (await screen.findByText('True cost')).closest('section')!
    expect(card).toHaveTextContent('₹54')
    expect(card).toHaveTextContent(/provisional/i)
    expect(card).toHaveTextContent('₹5,955')
  })

  it('breaks the cost into yarn, machines, labour, rework and the share of rejected rolls', async () => {
    setup('accountant')
    const card = (await screen.findByText('True cost')).closest('section')!
    expect(card).toHaveTextContent('₹3,465')
    expect(card).toHaveTextContent('₹1,210')
    expect(card).toHaveTextContent('₹640')
    expect(card).toHaveTextContent('₹380')
    expect(card).toHaveTextContent('₹260')
  })

  it('labels the cost final once the order is complete', async () => {
    setup('owner', { ...PASSPORT, cost: { ...PASSPORT.cost, provisional: false } })
    const card = (await screen.findByText('True cost')).closest('section')!
    expect(card).toHaveTextContent(/final/i)
    expect(card).not.toHaveTextContent(/provisional/i)
  })

  it('never shows internal costs to the buyer', async () => {
    setup('buyer')
    await screen.findByRole('heading', { level: 1, name: 'R-0142' })
    expect(screen.queryByText('True cost')).not.toBeInTheDocument()
    expect(screen.queryByText(/₹54/)).not.toBeInTheDocument()
  })

  it('says costs are not available yet when the server has none', async () => {
    setup('owner', { ...PASSPORT, cost: null })
    expect(await screen.findByText(/cost is not available yet/i)).toBeInTheDocument()
  })
})

describe('RollPassport: scanning and errors', () => {
  it('opens the scanner and goes to the roll that was typed or scanned', async () => {
    setup()
    await userEvent.click(await screen.findByRole('button', { name: /scan a roll/i }))
    const dialog = await screen.findByRole('dialog')
    await userEvent.type(within(dialog).getByLabelText(/roll code/i), 'R-0150')
    await userEvent.click(within(dialog).getByRole('button', { name: /open roll/i }))
    expect(screen.queryByRole('dialog')).not.toBeInTheDocument()
  })

  it('says so plainly when the roll does not exist (or is not yours)', async () => {
    setup('buyer', PASSPORT, { GET: { '/api/rolls/{roll_code}/passport': { status: 404, error: { code: 'NOT_FOUND', message: 'Roll not found', field: null, fields: null } } } })
    expect(await screen.findByRole('alert')).toHaveTextContent('Roll not found')
  })
})
