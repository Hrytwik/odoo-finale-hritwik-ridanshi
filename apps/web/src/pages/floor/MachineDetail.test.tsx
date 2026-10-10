import { screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeEach, describe, expect, it, vi } from 'vitest'

vi.mock('@/lib/api/client', () => ({ api: { GET: vi.fn(), POST: vi.fn(), PATCH: vi.fn(), DELETE: vi.fn() } }))
import { api } from '@/lib/api/client'
import { mockApi, renderPage } from '@/test/utils'
import MachineDetail from './MachineDetail'

const RAVI = { id: 1, name: 'Ravi Kumar' }
const RUN45 = { id: 45, order_code: 'ORD-0012', stage: 'weaving', operator: RAVI, started_at: '2026-10-10T08:00:00Z', order_progress_pct: 46.2 }
const recent = (over = {}) => ({
  id: 45, order_code: 'ORD-0012', machine_code: 'LOOM-04', stage: 'weaving', operator: RAVI, started_at: '2026-10-10T08:00:00Z', ended_at: null,
  output_kg: null, input_run_id: 41, roll_codes: ['R-0142', 'R-0143'], metres: 220, ...over,
})
const card = (over = {}) => ({ code: 'LOOM-04', name: 'Loom 4', stage: 'weaving', status: 'running', current_run: RUN45, downtime: null, output_today: 220, output_unit: 'm', recent_runs: [recent()], ...over })

const RUNNING_LOOM = card()
const IDLE_LOOM = card({ status: 'idle', current_run: null })
const DOWN_LOOM = card({ status: 'down', current_run: null, downtime: { reason: 'Warp beam broken', started_at: '2026-10-10T10:20:00Z' } })
const RUNNING_SPINNER = card({ code: 'SPIN-01', name: 'Ring frame 1', stage: 'spinning', current_run: { ...RUN45, id: 41, stage: 'spinning' }, recent_runs: [recent({ id: 41, stage: 'spinning', machine_code: 'SPIN-01', input_run_id: null, roll_codes: [], metres: 0 })] })
const RUNNING_DYER = card({ code: 'DYE-01', name: 'Jigger 1', stage: 'dyeing', current_run: { ...RUN45, id: 46, stage: 'dyeing' }, recent_runs: [recent({ id: 46, stage: 'dyeing', machine_code: 'DYE-01', input_run_id: null })] })

const BOARD = { running: 1, idle: 0, down: 0, generated_at: '2026-10-10T11:00:00Z', machines: [RUNNING_SPINNER] }
const WORKERS = [
  { id: 1, code: 'W-001', name: 'Ravi Kumar', role: 'operator', daily_wage: 800, active: true },
  { id: 6, code: 'W-006', name: 'Suresh', role: 'operator', daily_wage: 800, active: true },
  { id: 2, code: 'W-002', name: 'Meena Devi', role: 'inspector', daily_wage: 800, active: true },
  { id: 7, code: 'W-007', name: 'Retired Raju', role: 'operator', daily_wage: 800, active: false },
]
const ORDERS = [{ code: 'ORD-0012', state: 'confirmed', buyer: { id: 1, name: 'Sharma Fabrics' }, fabric_type: { id: 1, name: 'Poplin 58in' } }]
const LOTS = [
  { lot_code: 'L-0017', yarn_type: { name: '30s cotton' }, on_hand_kg: 212.5, is_blocked: false },
  { lot_code: 'L-0009', yarn_type: { name: '30s cotton' }, on_hand_kg: 50, is_blocked: true },
]
const me = (role: string) => ({ id: 1, username: role, role, display_name: role, worker_id: null, buyer_id: null })

function setup(machine: unknown, extra: Parameters<typeof mockApi>[0] = {}) {
  const code = (machine as { code: string }).code
  mockApi({
    GET: { '/api/auth/me': me('supervisor'), '/api/machines/{machine_code}': machine, '/api/workers': WORKERS, '/api/orders': ORDERS, '/api/floor': BOARD, '/api/lots': LOTS, ...extra.GET },
    POST: {
      '/api/runs': recent(), '/api/runs/{run_id}/end': recent(), '/api/runs/{run_id}/handover': recent(), '/api/runs/{run_id}/rolls': { code: 'R-0144', metres: 110 },
      '/api/runs/{run_id}/load-rolls': recent(), '/api/machines/{machine_code}/breakdown': DOWN_LOOM, '/api/machines/{machine_code}/repair': IDLE_LOOM,
      '/api/movements/issue': { id: 1 }, ...extra.POST,
    },
  })
  return renderPage(<MachineDetail />, { path: '/floor/machines/:code', route: `/floor/machines/${code}` })
}
const dialog = async () => await screen.findByRole('dialog')

beforeEach(() => {
  vi.clearAllMocks()
})

describe('MachineDetail: what you see', () => {
  it('shows the machine, its status, the running job and recent runs', async () => {
    setup(RUNNING_LOOM)
    expect(await screen.findByRole('heading', { level: 1, name: 'Loom 4' })).toBeInTheDocument()
    expect(screen.getAllByText('Running').length).toBeGreaterThan(0)
    const running = screen.getByText('Running now').closest('section')!
    expect(running).toHaveTextContent('ORD-0012')
    expect(running).toHaveTextContent('Ravi Kumar')
    const table = screen.getByRole('table')
    const row = within(table).getByRole('row', { name: /#45/ })
    expect(row).toHaveTextContent('Ravi Kumar')
    expect(row).toHaveTextContent('220 m')
  })

  it('shows why a machine is down', async () => {
    setup(DOWN_LOOM)
    expect(await screen.findByText('Warp beam broken')).toBeInTheDocument()
  })

  it('offers only what makes sense: an idle machine can start a run, not end one', async () => {
    setup(IDLE_LOOM)
    expect(await screen.findByRole('button', { name: /start run/i })).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: /end run/i })).not.toBeInTheDocument()
    expect(screen.queryByRole('button', { name: /repair/i })).not.toBeInTheDocument()
  })

  it('offers repair, and no run actions, for a machine that is down', async () => {
    setup(DOWN_LOOM)
    expect(await screen.findByRole('button', { name: /mark repaired/i })).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: /start run/i })).not.toBeInTheDocument()
    expect(screen.queryByRole('button', { name: /report breakdown/i })).not.toBeInTheDocument()
  })

  it('offers roll off on a weaving machine but not load rolls', async () => {
    setup(RUNNING_LOOM)
    expect(await screen.findByRole('button', { name: /roll off/i })).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: /load rolls/i })).not.toBeInTheDocument()
    expect(screen.queryByRole('button', { name: /issue yarn/i })).not.toBeInTheDocument()
  })

  it('offers load rolls on a dyeing machine and issue yarn on a spinning machine', async () => {
    setup(RUNNING_DYER)
    expect(await screen.findByRole('button', { name: /load rolls/i })).toBeInTheDocument()
    setup(RUNNING_SPINNER)
    expect(await screen.findByRole('button', { name: /issue yarn/i })).toBeInTheDocument()
  })

  it('says so plainly when the machine does not exist', async () => {
    setup(RUNNING_LOOM, { GET: { '/api/machines/{machine_code}': { status: 404, error: { code: 'NOT_FOUND', message: 'Machine not found', field: null, fields: null } } } })
    expect(await screen.findByRole('alert')).toHaveTextContent('Machine not found')
  })
})

describe('MachineDetail: what you can do', () => {
  it('reports a breakdown with a reason', async () => {
    setup(IDLE_LOOM)
    await userEvent.click(await screen.findByRole('button', { name: /report breakdown/i }))
    const d = await dialog()
    await userEvent.click(within(d).getByRole('button', { name: /^report breakdown/i }))
    expect(await within(d).findByText('Say what went wrong')).toBeInTheDocument()
    expect(api.POST).not.toHaveBeenCalled()
    await userEvent.type(within(d).getByLabelText(/what went wrong/i), 'Belt snapped')
    await userEvent.click(within(d).getByRole('button', { name: /^report breakdown/i }))
    await waitFor(() =>
      expect(api.POST).toHaveBeenCalledWith('/api/machines/{machine_code}/breakdown', { params: { path: { machine_code: 'LOOM-04' } }, body: { reason: 'Belt snapped' } }),
    )
  })

  it('marks a machine repaired', async () => {
    setup(DOWN_LOOM)
    await userEvent.click(await screen.findByRole('button', { name: /mark repaired/i }))
    await waitFor(() => expect(api.POST).toHaveBeenCalledWith('/api/machines/{machine_code}/repair', { params: { path: { machine_code: 'LOOM-04' } } }))
  })

  it('starts a weaving run with the order, operator and the spinning run that supplies the yarn', async () => {
    setup(IDLE_LOOM)
    await userEvent.click(await screen.findByRole('button', { name: /start run/i }))
    const d = await dialog()
    await userEvent.selectOptions(await within(d).findByLabelText(/^order/i), 'ORD-0012')
    await userEvent.selectOptions(within(d).getByLabelText(/operator/i), '1')
    // the open spinning run for that order is offered as a quick pick
    await userEvent.click(await within(d).findByRole('button', { name: /#41/ }))
    await userEvent.click(within(d).getByRole('button', { name: /^start run/i }))
    await waitFor(() =>
      expect(api.POST).toHaveBeenCalledWith('/api/runs', { body: { order_code: 'ORD-0012', machine_code: 'LOOM-04', operator_worker_id: 1, input_run_id: 41 } }),
    )
  })

  it('offers only active operators, not inspectors or people who have left', async () => {
    setup(IDLE_LOOM)
    await userEvent.click(await screen.findByRole('button', { name: /start run/i }))
    const d = await dialog()
    const options = within(await within(d).findByLabelText(/operator/i)).getAllByRole('option').map((o) => o.textContent)
    expect(options).toContain('Ravi Kumar')
    expect(options).toContain('Suresh')
    expect(options).not.toContain('Meena Devi')
    expect(options).not.toContain('Retired Raju')
  })

  it('hands the machine over to the next operator', async () => {
    setup(RUNNING_LOOM)
    await userEvent.click(await screen.findByRole('button', { name: /hand over/i }))
    const d = await dialog()
    await userEvent.selectOptions(await within(d).findByLabelText(/new operator/i), '6')
    await userEvent.click(within(d).getByRole('button', { name: /^hand over/i }))
    await waitFor(() => expect(api.POST).toHaveBeenCalledWith('/api/runs/{run_id}/handover', { params: { path: { run_id: 45 } }, body: { operator_worker_id: 6 } }))
  })

  it('rolls off a roll with real metres and tells the supervisor its code', async () => {
    setup(RUNNING_LOOM)
    await userEvent.click(await screen.findByRole('button', { name: /roll off/i }))
    const d = await dialog()
    await userEvent.type(within(d).getByLabelText(/metres/i), '110')
    await userEvent.click(within(d).getByRole('button', { name: /^roll off/i }))
    await waitFor(() => expect(api.POST).toHaveBeenCalledWith('/api/runs/{run_id}/rolls', { params: { path: { run_id: 45 } }, body: { metres: 110 } }))
  })

  it('refuses zero metres without calling the server', async () => {
    setup(RUNNING_LOOM)
    await userEvent.click(await screen.findByRole('button', { name: /roll off/i }))
    const d = await dialog()
    await userEvent.type(within(d).getByLabelText(/metres/i), '0')
    await userEvent.click(within(d).getByRole('button', { name: /^roll off/i }))
    expect(await within(d).findByText('Enter the metres, more than 0')).toBeInTheDocument()
    expect(api.POST).not.toHaveBeenCalled()
  })

  it('ends a spinning run only with the kilos it produced', async () => {
    setup(RUNNING_SPINNER)
    await userEvent.click(await screen.findByRole('button', { name: /end run/i }))
    const d = await dialog()
    await userEvent.click(within(d).getByRole('button', { name: /^end run/i }))
    expect(await within(d).findByText('Enter the kilos spun')).toBeInTheDocument()
    expect(api.POST).not.toHaveBeenCalled()
    await userEvent.type(within(d).getByLabelText(/kilos spun/i), '587.5')
    await userEvent.click(within(d).getByRole('button', { name: /^end run/i }))
    await waitFor(() => expect(api.POST).toHaveBeenCalledWith('/api/runs/{run_id}/end', { params: { path: { run_id: 41 } }, body: { output_kg: 587.5 } }))
  })

  it('ends a weaving run without asking for kilos', async () => {
    setup(RUNNING_LOOM)
    await userEvent.click(await screen.findByRole('button', { name: /end run/i }))
    const d = await dialog()
    expect(within(d).queryByLabelText(/kilos spun/i)).not.toBeInTheDocument()
    await userEvent.click(within(d).getByRole('button', { name: /^end run/i }))
    await waitFor(() => expect(api.POST).toHaveBeenCalledWith('/api/runs/{run_id}/end', { params: { path: { run_id: 45 } }, body: {} }))
  })

  it('issues yarn from a usable lot to the spinning run, and does not offer blocked lots', async () => {
    setup(RUNNING_SPINNER)
    await userEvent.click(await screen.findByRole('button', { name: /issue yarn/i }))
    const d = await dialog()
    const lots = within(await within(d).findByLabelText(/^lot/i)).getAllByRole('option').map((o) => o.textContent)
    expect(lots.join(' ')).toContain('L-0017')
    expect(lots.join(' ')).not.toContain('L-0009')
    await userEvent.selectOptions(within(d).getByLabelText(/^lot/i), 'L-0017')
    await userEvent.type(within(d).getByLabelText(/quantity/i), '100')
    await userEvent.click(within(d).getByRole('button', { name: /^issue yarn/i }))
    await waitFor(() => expect(api.POST).toHaveBeenCalledWith('/api/movements/issue', { body: { lot_code: 'L-0017', run_id: 41, qty_kg: 100 } }))
  })

  it('loads rolls into a dyeing run from a list of roll codes', async () => {
    setup(RUNNING_DYER)
    await userEvent.click(await screen.findByRole('button', { name: /load rolls/i }))
    const d = await dialog()
    await userEvent.type(within(d).getByLabelText(/roll codes/i), 'R-0142, R-0143 r-0144')
    await userEvent.click(within(d).getByRole('button', { name: /^load rolls/i }))
    await waitFor(() =>
      expect(api.POST).toHaveBeenCalledWith('/api/runs/{run_id}/load-rolls', { params: { path: { run_id: 46 } }, body: { roll_codes: ['R-0142', 'R-0143', 'R-0144'] } }),
    )
  })

  it("shows the server's reason when an action is refused", async () => {
    setup(RUNNING_LOOM, {
      POST: { '/api/runs/{run_id}/rolls': { status: 409, error: { code: 'RUN_NOT_OPEN', message: 'This run is not open', field: null, fields: null } } },
    })
    await userEvent.click(await screen.findByRole('button', { name: /roll off/i }))
    const d = await dialog()
    await userEvent.type(within(d).getByLabelText(/metres/i), '50')
    await userEvent.click(within(d).getByRole('button', { name: /^roll off/i }))
    expect(await within(d).findByRole('alert')).toHaveTextContent('This run is not open')
  })
})
