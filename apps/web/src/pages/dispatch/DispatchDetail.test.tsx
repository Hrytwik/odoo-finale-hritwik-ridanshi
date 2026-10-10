import { fireEvent, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeEach, describe, expect, it, vi } from 'vitest'

vi.mock('@/lib/api/client', () => ({ api: { GET: vi.fn(), POST: vi.fn(), PATCH: vi.fn(), DELETE: vi.fn() } }))
import { api } from '@/lib/api/client'
import { mockApi, renderPage } from '@/test/utils'
import DispatchDetail from './DispatchDetail'

const roll = (code: string, metres = 110, status = 'loading') => ({ id: 1, code, order_code: 'ORD-0012', buyer_name: 'Sharma Fabrics', fabric: 'Poplin 58in', colour: 'navy', metres, status, created_at: '2026-10-10T10:00:00Z' })
const summary = (over = {}) => ({ order_code: 'ORD-0012', ordered_m: 5000, previously_dispatched_m: 330, loaded_m: 220, remaining_m: 4450, over_shipped: false, ...over })
const LOADING = {
  id: 8, code: 'DSP-0008', buyer: { id: 1, name: 'Sharma Fabrics' }, vehicle_no: 'KA01AB1234', driver_name: 'Manju', state: 'loading',
  created_at: '2026-10-10T10:00:00Z', dispatched_at: null, rolls: [roll('R-0140'), roll('R-0141')], orders: [summary()], total_metres: 220, invoice_no: null, warnings: [],
}
const EMPTY = { ...LOADING, rolls: [], orders: [], total_metres: 0 }
const SENT = { ...LOADING, state: 'dispatched', dispatched_at: '2026-10-10T15:00:00Z', invoice_no: 'INV-0008', rolls: [roll('R-0140', 110, 'dispatched'), roll('R-0141', 110, 'dispatched')] }
const refuse = (code: string, message: string, status = 409) => ({ status, error: { code, message, field: 'roll_code', fields: null } })

function setup(dispatch: unknown = LOADING, extra: Parameters<typeof mockApi>[0] = {}) {
  mockApi({
    GET: { '/api/dispatches/{dispatch_code}': dispatch, ...extra.GET },
    POST: {
      '/api/dispatches/{dispatch_code}/items': { ...LOADING, rolls: [...LOADING.rolls, roll('R-0150')], total_metres: 330 },
      '/api/dispatches/{dispatch_code}/confirm': SENT, ...extra.POST,
    },
    DELETE: { '/api/dispatches/{dispatch_code}/items/{roll_code}': { ...LOADING, rolls: [LOADING.rolls[1]], total_metres: 110 }, ...extra.DELETE },
  })
  return renderPage(<DispatchDetail />, { path: '/dispatch/:code', route: '/dispatch/DSP-0008', extra: [{ path: '/invoices/:no', element: <p>invoice page</p> }] })
}
const scanField = () => screen.findByLabelText(/roll code/i)
async function scan(text: string) {
  await userEvent.type(await scanField(), `${text}{Enter}`)
}

beforeEach(() => {
  vi.clearAllMocks()
})

describe('DispatchDetail: loading a truck', () => {
  it('shows the truck, the buyer and the rolls already on it', async () => {
    setup()
    expect(await screen.findByRole('heading', { level: 1, name: 'DSP-0008' })).toBeInTheDocument()
    expect(screen.getByText(/Sharma Fabrics/)).toBeInTheDocument()
    expect(screen.getByText(/KA01AB1234/)).toBeInTheDocument()
    const table = screen.getByRole('table')
    expect(within(table).getByRole('row', { name: /R-0140/ })).toHaveTextContent('110 m')
    expect(within(table).getByRole('row', { name: /R-0141/ })).toBeInTheDocument()
  })

  it('loads a roll typed or scanned into the field, with Enter', async () => {
    setup()
    await scan('R-0150')
    await waitFor(() => expect(api.POST).toHaveBeenCalledWith('/api/dispatches/{dispatch_code}/items', { params: { path: { dispatch_code: 'DSP-0008' } }, body: { roll_code: 'R-0150' } }))
    expect(await screen.findByRole('row', { name: /R-0150/ })).toBeInTheDocument()
  })

  it('reads the address printed on a tag as well as the bare code', async () => {
    setup()
    await scan('https://192.168.1.23:8443/r/R-0150')
    await waitFor(() => expect(api.POST).toHaveBeenCalledWith('/api/dispatches/{dispatch_code}/items', expect.objectContaining({ body: { roll_code: 'R-0150' } })))
  })

  it('clears the field after a roll is loaded, ready for the next scan', async () => {
    setup()
    await scan('R-0150')
    await screen.findByRole('row', { name: /R-0150/ })
    expect(screen.getByLabelText(/roll code/i)).toHaveValue('')
  })

  it('confirms each load in a scan log', async () => {
    setup()
    await scan('R-0150')
    expect(await within(await screen.findByRole('log')).findByText(/R-0150 loaded/i)).toBeInTheDocument()
  })

  it('refuses something that is not a roll code without calling the server', async () => {
    setup()
    await scan('hello')
    expect(await screen.findByText(/not a roll code/i)).toBeInTheDocument()
    expect(api.POST).not.toHaveBeenCalled()
  })
})

describe('DispatchDetail: the wrong rolls are refused, loudly', () => {
  it('refuses a roll that has not passed quality check, and says why', async () => {
    setup(LOADING, { POST: { '/api/dispatches/{dispatch_code}/items': refuse('ROLL_NOT_PASSED', 'Roll R-0150 has not passed QC') } })
    await scan('R-0150')
    const log = await screen.findByRole('log')
    expect(await within(log).findByText(/R-0150 refused/i)).toHaveTextContent('Roll R-0150 has not passed QC')
    expect(screen.queryByRole('row', { name: /R-0150/ })).not.toBeInTheDocument()
  })

  it('refuses a roll that is already on another dispatch', async () => {
    setup(LOADING, { POST: { '/api/dispatches/{dispatch_code}/items': refuse('ALREADY_DISPATCHED', 'This roll is already on a dispatch') } })
    await scan('R-0131')
    expect(await within(await screen.findByRole('log')).findByText(/R-0131 refused/i)).toHaveTextContent('already on a dispatch')
  })

  it("refuses another buyer's roll", async () => {
    setup(LOADING, { POST: { '/api/dispatches/{dispatch_code}/items': refuse('WRONG_BUYER', 'This roll belongs to another buyer') } })
    await scan('R-0160')
    expect(await within(await screen.findByRole('log')).findByText(/R-0160 refused/i)).toHaveTextContent('another buyer')
  })

  it('keeps earlier scans in the log, newest first', async () => {
    setup()
    await scan('R-0150')
    await screen.findByRole('row', { name: /R-0150/ })
    mockApi({ GET: { '/api/dispatches/{dispatch_code}': LOADING }, POST: { '/api/dispatches/{dispatch_code}/items': refuse('ROLL_NOT_PASSED', 'Roll R-0151 has not passed QC') } })
    await scan('R-0151')
    const items = within(await screen.findByRole('log')).getAllByRole('listitem').map((li) => li.textContent ?? '')
    expect(items[0]).toContain('R-0151 refused')
    expect(items[1]).toContain('R-0150 loaded')
  })
})

describe('DispatchDetail: what is on the truck', () => {
  it('shows per order how much is loaded, already sent and still to go', async () => {
    setup()
    const card = (await screen.findByText('ORD-0012', { selector: 'strong' })).closest('.shortage, .load-order, section')!
    expect(card).toHaveTextContent('220 m')
    expect(card).toHaveTextContent('330 m')
    expect(card).toHaveTextContent('4,450 m')
  })

  it('warns when an order would be over-shipped', async () => {
    setup({ ...LOADING, orders: [summary({ over_shipped: true, remaining_m: -40 })], warnings: ['ORD-0012 would be over-shipped by 40 m'] })
    expect(await screen.findByText(/over-shipped by 40 m/i)).toBeInTheDocument()
    expect(screen.getAllByText(/over-shipping/i).length).toBeGreaterThan(0)
  })

  it('takes a roll off the truck while it is still loading', async () => {
    setup()
    const row = await screen.findByRole('row', { name: /R-0140/ })
    await userEvent.click(within(row).getByRole('button', { name: /remove r-0140/i }))
    await waitFor(() =>
      expect(api.DELETE).toHaveBeenCalledWith('/api/dispatches/{dispatch_code}/items/{roll_code}', { params: { path: { dispatch_code: 'DSP-0008', roll_code: 'R-0140' } } }),
    )
    await waitFor(() => expect(screen.queryByRole('row', { name: /R-0140/ })).not.toBeInTheDocument())
  })
})

describe('DispatchDetail: sending the truck', () => {
  it('cannot be confirmed with nothing on it', async () => {
    setup(EMPTY)
    expect(await screen.findByRole('button', { name: /confirm dispatch/i })).toBeDisabled()
  })

  it('confirms after asking, and then shows the invoice', async () => {
    setup()
    await userEvent.click(await screen.findByRole('button', { name: /confirm dispatch/i }))
    const d = await screen.findByRole('dialog')
    expect(d).toHaveTextContent('220 m')
    expect(d).toHaveTextContent(/invoice/i)
    await userEvent.click(within(d).getByRole('button', { name: /^confirm dispatch/i }))
    await waitFor(() => expect(api.POST).toHaveBeenCalledWith('/api/dispatches/{dispatch_code}/confirm', { params: { path: { dispatch_code: 'DSP-0008' } } }))
  })

  it('shows the server reason if confirming is refused', async () => {
    setup(LOADING, { POST: { '/api/dispatches/{dispatch_code}/confirm': refuse('EMPTY_DISPATCH', 'A dispatch needs at least one roll') } })
    await userEvent.click(await screen.findByRole('button', { name: /confirm dispatch/i }))
    const d = await screen.findByRole('dialog')
    await userEvent.click(within(d).getByRole('button', { name: /^confirm dispatch/i }))
    expect(await within(d).findByRole('alert')).toHaveTextContent('at least one roll')
  })

  it('sends one confirm request when pressed twice quickly', async () => {
    setup()
    await userEvent.click(await screen.findByRole('button', { name: /confirm dispatch/i }))
    const d = await screen.findByRole('dialog')
    vi.mocked(api.POST).mockReturnValue(new Promise(() => {}) as never)
    const form = within(d).getByRole('button', { name: /^confirm dispatch/i }).closest('form')!
    fireEvent.submit(form)
    fireEvent.submit(form)
    await waitFor(() => expect(api.POST).toHaveBeenCalledTimes(1))
  })

  it('is read-only once dispatched: no scanning, no removing, and the invoice is one click away', async () => {
    setup(SENT)
    expect(await screen.findByRole('link', { name: /INV-0008/ })).toHaveAttribute('href', '/invoices/INV-0008')
    expect(screen.queryByLabelText(/roll code/i)).not.toBeInTheDocument()
    expect(screen.queryByRole('button', { name: /confirm dispatch/i })).not.toBeInTheDocument()
    expect(screen.queryByRole('button', { name: /remove/i })).not.toBeInTheDocument()
  })

  it('says so plainly when the dispatch does not exist', async () => {
    setup(LOADING, { GET: { '/api/dispatches/{dispatch_code}': { status: 404, error: { code: 'NOT_FOUND', message: 'Dispatch not found', field: null, fields: null } } } })
    expect(await screen.findByRole('alert')).toHaveTextContent('Dispatch not found')
  })
})
