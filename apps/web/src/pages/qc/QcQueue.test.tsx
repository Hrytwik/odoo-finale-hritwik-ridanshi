import { screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeEach, describe, expect, it, vi } from 'vitest'

vi.mock('@/lib/api/client', () => ({ api: { GET: vi.fn(), POST: vi.fn(), PATCH: vi.fn(), DELETE: vi.fn() } }))
import { api } from '@/lib/api/client'
import { mockApi, renderPage } from '@/test/utils'
import QcQueue from './QcQueue'

const roll = (code: string, status: string, metres = 110) => ({ id: 1, code, order_code: 'ORD-0012', buyer_name: 'Sharma Fabrics', fabric: 'Poplin 58in', colour: 'navy', metres, status, created_at: '2026-10-10T10:00:00Z' })
const QUEUE = {
  counts: { awaiting_qc: 4, awaiting_rework: 1, in_rework: 2, passed: 11, rejected: 1 },
  rolls: [roll('R-0142', 'awaiting_qc'), roll('R-0143', 'awaiting_rework', 90)],
}
const WORKERS = [
  { id: 1, code: 'W-001', name: 'Ravi Kumar', role: 'operator', daily_wage: 800, active: true },
  { id: 2, code: 'W-002', name: 'Meena Devi', role: 'inspector', daily_wage: 800, active: true },
]
const MACHINES = [
  { id: 1, code: 'DYE-01', name: 'Jigger 1', stage: 'dyeing', rated_output_per_hour: 20, running_cost_per_hour: 40, active: true },
  { id: 2, code: 'LOOM-04', name: 'Loom 4', stage: 'weaving', rated_output_per_hour: 20, running_cost_per_hour: 40, active: true },
]
const me = (role: string) => ({ id: 1, username: role, role, display_name: role, worker_id: 2, buyer_id: null })

function setup(queue: unknown = QUEUE, role = 'qc', extra: Parameters<typeof mockApi>[0] = {}) {
  mockApi({
    GET: { '/api/auth/me': me(role), '/api/qc/queue': queue, '/api/workers': WORKERS, '/api/machines': MACHINES, ...extra.GET },
    POST: { '/api/rework-runs': { id: 60 }, ...extra.POST },
  })
  return renderPage(<QcQueue />, { extra: [{ path: '/qc/:rollCode', element: <p>inspect page</p> }] })
}
const kpi = (label: string) => [...document.querySelectorAll('.kpi')].find((k) => k.querySelector('.kpi-label')?.textContent === label)

beforeEach(() => {
  vi.clearAllMocks()
})

describe('QcQueue', () => {
  it('counts what is waiting, in rework, passed and rejected', async () => {
    setup()
    await screen.findByRole('table')
    expect(kpi('Waiting for QC')).toHaveTextContent('4')
    expect(kpi('Needs rework')).toHaveTextContent('1')
    expect(kpi('In rework')).toHaveTextContent('2')
    expect(kpi('Passed')).toHaveTextContent('11')
    expect(kpi('Rejected')).toHaveTextContent('1')
  })

  it('lists the rolls that need attention with order, buyer, fabric and length', async () => {
    setup()
    const row = within(await screen.findByRole('table')).getByRole('row', { name: /R-0142/ })
    expect(row).toHaveTextContent('ORD-0012')
    expect(row).toHaveTextContent('Sharma Fabrics')
    expect(row).toHaveTextContent('Poplin 58in')
    expect(row).toHaveTextContent('110 m')
    expect(row).toHaveTextContent('Awaiting QC')
  })

  it('opens the inspection for a roll waiting for QC', async () => {
    setup()
    const row = within(await screen.findByRole('table')).getByRole('row', { name: /R-0142/ })
    expect(within(row).getByRole('link', { name: /inspect/i })).toHaveAttribute('href', '/qc/R-0142')
  })

  it('offers rework, not inspection, for a roll that needs rework', async () => {
    setup()
    const row = within(await screen.findByRole('table')).getByRole('row', { name: /R-0143/ })
    expect(within(row).queryByRole('link', { name: /inspect/i })).not.toBeInTheDocument()
    expect(within(row).getByRole('button', { name: /start rework/i })).toBeInTheDocument()
  })

  it('starts a rework run with an operator on a dyeing machine', async () => {
    setup()
    const row = within(await screen.findByRole('table')).getByRole('row', { name: /R-0143/ })
    await userEvent.click(within(row).getByRole('button', { name: /start rework/i }))
    const dialog = await screen.findByRole('dialog')
    await userEvent.selectOptions(await within(dialog).findByLabelText(/operator/i), '1')
    await userEvent.selectOptions(within(dialog).getByLabelText(/machine/i), 'DYE-01')
    await userEvent.click(within(dialog).getByRole('button', { name: /^start rework/i }))
    await waitFor(() => expect(api.POST).toHaveBeenCalledWith('/api/rework-runs', { body: { roll_code: 'R-0143', operator_worker_id: 1, machine_code: 'DYE-01' } }))
  })

  it('offers only dyeing machines, or no machine for mending by hand', async () => {
    setup()
    const row = within(await screen.findByRole('table')).getByRole('row', { name: /R-0143/ })
    await userEvent.click(within(row).getByRole('button', { name: /start rework/i }))
    const dialog = await screen.findByRole('dialog')
    const options = within(await within(dialog).findByLabelText(/machine/i)).getAllByRole('option').map((o) => o.textContent)
    expect(options.join(' ')).toContain('Jigger 1')
    expect(options.join(' ')).not.toContain('Loom 4')
    expect(options.join(' ')).toMatch(/by hand/i)
  })

  it('sends a rework run for mending by hand without a machine', async () => {
    setup()
    const row = within(await screen.findByRole('table')).getByRole('row', { name: /R-0143/ })
    await userEvent.click(within(row).getByRole('button', { name: /start rework/i }))
    const dialog = await screen.findByRole('dialog')
    await userEvent.selectOptions(await within(dialog).findByLabelText(/operator/i), '1')
    await userEvent.click(within(dialog).getByRole('button', { name: /^start rework/i }))
    await waitFor(() => expect(api.POST).toHaveBeenCalledWith('/api/rework-runs', { body: { roll_code: 'R-0143', operator_worker_id: 1 } }))
  })

  it('needs an operator for the rework', async () => {
    setup()
    const row = within(await screen.findByRole('table')).getByRole('row', { name: /R-0143/ })
    await userEvent.click(within(row).getByRole('button', { name: /start rework/i }))
    const dialog = await screen.findByRole('dialog')
    await userEvent.click(within(dialog).getByRole('button', { name: /^start rework/i }))
    expect(await within(dialog).findByText('Choose who does the rework')).toBeInTheDocument()
    expect(api.POST).not.toHaveBeenCalled()
  })

  it('shows the reason when rework cannot be started', async () => {
    setup(QUEUE, 'qc', { POST: { '/api/rework-runs': { status: 409, error: { code: 'ROLL_WRONG_STATUS', message: 'This roll is not waiting for rework', field: null, fields: null } } } })
    const row = within(await screen.findByRole('table')).getByRole('row', { name: /R-0143/ })
    await userEvent.click(within(row).getByRole('button', { name: /start rework/i }))
    const dialog = await screen.findByRole('dialog')
    await userEvent.selectOptions(await within(dialog).findByLabelText(/operator/i), '1')
    await userEvent.click(within(dialog).getByRole('button', { name: /^start rework/i }))
    expect(await within(dialog).findByRole('alert')).toHaveTextContent('This roll is not waiting for rework')
  })

  it('goes to the inspection of a scanned roll', async () => {
    setup()
    await userEvent.click(await screen.findByRole('button', { name: /scan a roll/i }))
    const dialog = await screen.findByRole('dialog')
    await userEvent.type(within(dialog).getByLabelText(/roll code/i), 'R-0150')
    await userEvent.click(within(dialog).getByRole('button', { name: /open roll/i }))
    expect(await screen.findByText('inspect page')).toBeInTheDocument()
  })

  it('shows a friendly empty state when nothing is waiting', async () => {
    setup({ counts: { ...QUEUE.counts, awaiting_qc: 0, awaiting_rework: 0 }, rolls: [] })
    expect(await screen.findByText(/nothing is waiting/i)).toBeInTheDocument()
  })

  it('shows a Retry state when the queue cannot be loaded', async () => {
    setup({ status: 500, error: 'boom' })
    expect(await screen.findByRole('alert')).toHaveTextContent(/something went wrong/i)
    expect(screen.getByRole('button', { name: /retry/i })).toBeInTheDocument()
  })
})
