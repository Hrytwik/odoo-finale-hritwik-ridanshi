import { screen, within } from '@testing-library/react'
import { beforeEach, describe, expect, it, vi } from 'vitest'

vi.mock('@/lib/api/client', () => ({ api: { GET: vi.fn(), POST: vi.fn(), PATCH: vi.fn(), DELETE: vi.fn() } }))
import { mockApi, renderPage } from '@/test/utils'
import FloorBoard from './FloorBoard'

const RAVI = { id: 1, name: 'Ravi Kumar' }
const BOARD = {
  running: 2, idle: 1, down: 1, generated_at: '2026-10-10T11:00:00Z',
  machines: [
    { code: 'SPIN-01', name: 'Ring frame 1', stage: 'spinning', status: 'idle', current_run: null, downtime: null, output_today: 587.5, output_unit: 'kg' },
    {
      code: 'LOOM-04', name: 'Loom 4', stage: 'weaving', status: 'running', downtime: null, output_today: 220, output_unit: 'm',
      current_run: { id: 45, order_code: 'ORD-0012', stage: 'weaving', operator: RAVI, started_at: '2026-10-10T08:00:00Z', order_progress_pct: 46.2 },
    },
    { code: 'LOOM-05', name: 'Loom 5', stage: 'weaving', status: 'down', current_run: null, downtime: { reason: 'Warp beam broken', started_at: '2026-10-10T10:20:00Z' }, output_today: 90, output_unit: 'm' },
    {
      code: 'DYE-01', name: 'Jigger 1', stage: 'dyeing', status: 'running', downtime: null, output_today: 330, output_unit: 'm',
      current_run: { id: 46, order_code: 'ORD-0012', stage: 'dyeing', operator: { id: 6, name: 'Suresh' }, started_at: '2026-10-10T10:00:00Z', order_progress_pct: 30.8 },
    },
  ],
}

beforeEach(() => {
  vi.clearAllMocks()
})

describe('FloorBoard', () => {
  it('shows every machine with its code, name and status', async () => {
    mockApi({ GET: { '/api/floor': BOARD } })
    renderPage(<FloorBoard />)
    const loom4 = (await screen.findByRole('link', { name: /loom 4/i })).closest('article')!
    expect(loom4).toHaveTextContent('LOOM-04')
    expect(within(loom4).getByText('Running')).toBeInTheDocument()
    const loom5 = screen.getByRole('link', { name: /loom 5/i }).closest('article')!
    expect(within(loom5).getByText('Down')).toBeInTheDocument()
    const spin = screen.getByRole('link', { name: /ring frame 1/i }).closest('article')!
    expect(within(spin).getByText('Idle')).toBeInTheDocument()
  })

  it('says which order and operator a running machine has, and its progress', async () => {
    mockApi({ GET: { '/api/floor': BOARD } })
    renderPage(<FloorBoard />)
    const loom4 = (await screen.findByRole('link', { name: /loom 4/i })).closest('article')!
    expect(loom4).toHaveTextContent('ORD-0012')
    expect(loom4).toHaveTextContent('Ravi Kumar')
    expect(within(loom4).getByRole('progressbar', { name: /order progress/i })).toHaveAttribute('aria-valuenow', '46')
  })

  it('shows why a machine is down and since when', async () => {
    mockApi({ GET: { '/api/floor': BOARD } })
    renderPage(<FloorBoard />)
    const loom5 = (await screen.findByRole('link', { name: /loom 5/i })).closest('article')!
    expect(loom5).toHaveTextContent('Warp beam broken')
    expect(loom5).toHaveTextContent(/down since/i)
  })

  it("shows each machine's output today in its own unit", async () => {
    mockApi({ GET: { '/api/floor': BOARD } })
    renderPage(<FloorBoard />)
    const spin = (await screen.findByRole('link', { name: /ring frame 1/i })).closest('article')!
    expect(spin).toHaveTextContent('587.5 kg')
    expect(screen.getByRole('link', { name: /loom 4/i }).closest('article')).toHaveTextContent('220 m')
  })

  it('counts running, idle and down machines in the live strip', async () => {
    mockApi({ GET: { '/api/floor': BOARD } })
    renderPage(<FloorBoard />)
    await screen.findByRole('link', { name: /loom 4/i })
    const strip = document.querySelector('.live-strip') as HTMLElement
    expect(strip).toHaveTextContent('LIVE')
    expect(strip.querySelectorAll('.live-count')[0]).toHaveTextContent(/2\s*running/)
    expect(strip.querySelectorAll('.live-count')[1]).toHaveTextContent(/1\s*idle/)
    expect(strip.querySelectorAll('.live-count')[2]).toHaveTextContent(/1\s*down/)
  })

  it('shows a speed reading only on running machines', async () => {
    mockApi({ GET: { '/api/floor': BOARD } })
    renderPage(<FloorBoard />)
    const loom4 = (await screen.findByRole('link', { name: /loom 4/i })).closest('article')!
    expect(within(loom4).getByText('RPM').previousElementSibling).not.toHaveTextContent('—')
    const loom5 = screen.getByRole('link', { name: /loom 5/i }).closest('article')!
    expect(loom5.querySelector('.machine-speed strong')).toHaveTextContent('—')
  })

  it('groups machines by stage', async () => {
    mockApi({ GET: { '/api/floor': BOARD } })
    renderPage(<FloorBoard />)
    await screen.findByRole('link', { name: /loom 4/i })
    expect(screen.getByRole('heading', { name: /spinning/i })).toBeInTheDocument()
    expect(screen.getByRole('heading', { name: /weaving/i })).toBeInTheDocument()
    expect(screen.getByRole('heading', { name: /dyeing/i })).toBeInTheDocument()
  })

  it("opens a machine's own page", async () => {
    mockApi({ GET: { '/api/floor': BOARD } })
    renderPage(<FloorBoard />)
    expect(await screen.findByRole('link', { name: /loom 4/i })).toHaveAttribute('href', '/floor/machines/LOOM-04')
  })

  it('shows an empty state when no machines are set up', async () => {
    mockApi({ GET: { '/api/floor': { ...BOARD, machines: [], running: 0, idle: 0, down: 0 } } })
    renderPage(<FloorBoard />)
    expect(await screen.findByText(/no machines yet/i)).toBeInTheDocument()
  })

  it('shows a Retry state when the board cannot be loaded', async () => {
    mockApi({ GET: { '/api/floor': { status: 500, error: 'boom' } } })
    renderPage(<FloorBoard />)
    expect(await screen.findByRole('alert')).toHaveTextContent(/something went wrong/i)
    expect(screen.getByRole('button', { name: /retry/i })).toBeInTheDocument()
  })
})
