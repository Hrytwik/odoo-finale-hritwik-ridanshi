import { fireEvent, screen, within } from '@testing-library/react'
import { beforeEach, describe, expect, it, vi } from 'vitest'

vi.mock('@/lib/api/client', () => ({ api: { GET: vi.fn(), POST: vi.fn(), PATCH: vi.fn(), DELETE: vi.fn() } }))
import { api } from '@/lib/api/client'
import { mockApi, renderPage } from '@/test/utils'
import Insights from './Insights'
import OwnerDashboard from './OwnerDashboard'

const REPORT = {
  month: '2026-10',
  profit: { invoiced: 412000, yarn_issued: 198500, wages_earned: 96000, idle_labour: 14200, machine_running_cost: 61500, stock_writeoffs: 2500, profit: 53500 },
  cash: { received_from_buyers: 260000, paid_to_suppliers: 150000, paid_wages: 80000, net_cash: 30000, receivables_outstanding: 152000, payables_outstanding: 248500 },
  machines: [{ code: 'LOOM-04', name: 'Loom 4', stage: 'weaving', running_h: 180, idle_h: 31, down_h: 12, output: 3960, output_unit: 'm', lost_capacity: 946, lost_capacity_unit: 'm' }],
  orders: [
    { order_code: 'ORD-0012', buyer_name: 'Sharma Fabrics', revenue: 145200, cost: 246375, profit: -101175 },
    { order_code: 'ORD-0013', buyer_name: 'Lotus Apparel', revenue: 266800, cost: 150000, profit: 116800 },
  ],
  warnings: ['Run 52 (Loom 5, 2026-10-08) has no attendance for its operator'],
}

const get = vi.mocked(api.GET)
beforeEach(() => vi.clearAllMocks())
const kpi = (label: string) => [...document.querySelectorAll('.kpi')].find((k) => k.querySelector('.kpi-label')?.textContent === label)!

describe('Owner dashboard', () => {
  it('shows the month name and asks the server for that month', async () => {
    mockApi({ GET: { '/api/reports/month': REPORT } })
    renderPage(<OwnerDashboard />)
    await screen.findByRole('region', { name: 'Where the money went' })
    const month = new Date().toISOString().slice(0, 7)
    expect(get).toHaveBeenCalledWith('/api/reports/month', { params: { query: { month } } })
    expect(screen.getByText(/^Owner · /)).toBeInTheDocument()
  })

  it('shows net profit, cash, machine use and idle labour', async () => {
    mockApi({ GET: { '/api/reports/month': REPORT } })
    renderPage(<OwnerDashboard />)
    await screen.findByRole('region', { name: 'Where the money went' })
    expect(kpi('Net profit')).toHaveTextContent('₹53,500')
    expect(kpi('Cash on hand')).toHaveTextContent('₹30,000')
    expect(kpi('Machine use')).toHaveTextContent('81%')
    expect(kpi('Idle labour')).toHaveTextContent('₹14,200')
  })

  it('shows a loss in red', async () => {
    mockApi({ GET: { '/api/reports/month': { ...REPORT, profit: { ...REPORT.profit, profit: -20000 } } } })
    renderPage(<OwnerDashboard />)
    await screen.findByRole('region', { name: 'Where the money went' })
    expect(kpi('Net profit').querySelector('.kpi-value')).toHaveClass('text-danger')
  })

  it('lays out where the money went, ending in net profit', async () => {
    mockApi({ GET: { '/api/reports/month': REPORT } })
    renderPage(<OwnerDashboard />)
    const panel = await screen.findByRole('region', { name: 'Where the money went' })
    expect(panel).toHaveTextContent(/Invoiced to buyers\s*₹4,12,000/)
    expect(panel).toHaveTextContent(/Yarn used\s*-₹1,98,500/)
    expect(panel).toHaveTextContent(/of which ₹14,200 was idle labour/)
    expect(panel).toHaveTextContent(/Net profit\s*₹53,500/)
  })

  it('shows cash received, paid out and what is still owed each way', async () => {
    mockApi({ GET: { '/api/reports/month': REPORT } })
    renderPage(<OwnerDashboard />)
    const panel = await screen.findByRole('region', { name: 'Cash' })
    expect(panel).toHaveTextContent(/Received from buyers\s*₹2,60,000/)
    expect(panel).toHaveTextContent(/Buyers still owe\s*₹1,52,000/)
    expect(panel).toHaveTextContent(/We still owe suppliers\s*₹2,48,500/)
  })

  it('draws revenue and cost side by side for each order, with the profit or loss written above', async () => {
    mockApi({ GET: { '/api/reports/month': REPORT } })
    renderPage(<OwnerDashboard />)
    const chart = await screen.findByRole('img', { name: /revenue and cost for 2 orders/i })
    expect(chart.querySelectorAll('.chart-bar.is-revenue')).toHaveLength(2)
    expect(chart.querySelectorAll('.chart-bar.is-cost')).toHaveLength(2)
    expect(within(chart as unknown as HTMLElement).getByText('Loss ₹1 L')).toHaveClass('is-loss')
    expect(within(chart as unknown as HTMLElement).getByText('Profit ₹1.2 L')).not.toHaveClass('is-loss')
  })

  it('gives the chart a table for screen readers', async () => {
    mockApi({ GET: { '/api/reports/month': REPORT } })
    renderPage(<OwnerDashboard />)
    const table = await screen.findByRole('table', { name: /revenue and cost for 2 orders/i })
    expect(within(table).getByText('ORD-0013')).toBeInTheDocument()
    expect(within(table).getByText('116800')).toBeInTheDocument()
  })

  it('warns about data problems before the numbers are relied on', async () => {
    mockApi({ GET: { '/api/reports/month': REPORT } })
    renderPage(<OwnerDashboard />)
    expect(await screen.findByText(/has no attendance for its operator/)).toBeInTheDocument()
  })

  it('lists each machine with its hours and lost capacity', async () => {
    mockApi({ GET: { '/api/reports/month': REPORT } })
    renderPage(<OwnerDashboard />)
    const row = (await screen.findByText('Loom 4')).closest('tr')!
    expect(row).toHaveTextContent('180 h')
    expect(row).toHaveTextContent('12 h')
    expect(row).toHaveTextContent('946 m')
  })

  it('asks for another month when the picker changes', async () => {
    mockApi({ GET: { '/api/reports/month': REPORT } })
    renderPage(<OwnerDashboard />)
    await screen.findByRole('region', { name: 'Where the money went' })
    const picker = screen.getByLabelText('Month')
    // a month input takes its whole value at once, so set it in one go rather than typing it
    fireEvent.change(picker, { target: { value: '2026-09' } })
    await vi.waitFor(() => expect(get).toHaveBeenCalledWith('/api/reports/month', { params: { query: { month: '2026-09' } } }))
  })

  it('says so when there are no orders this month', async () => {
    mockApi({ GET: { '/api/reports/month': { ...REPORT, orders: [], machines: [], warnings: [] } } })
    renderPage(<OwnerDashboard />)
    expect(await screen.findByText(/no orders this month/i)).toBeInTheDocument()
    expect(screen.getByText(/no machine hours this month/i)).toBeInTheDocument()
  })

  it('shows a Retry state when the report cannot be loaded', async () => {
    mockApi({ GET: { '/api/reports/month': { status: 500, error: 'boom' } } })
    renderPage(<OwnerDashboard />)
    expect(await screen.findByRole('alert')).toHaveTextContent(/something went wrong/i)
    expect(screen.getByRole('button', { name: /retry/i })).toBeInTheDocument()
  })
})

const ETA = {
  order_code: 'ORD-0012', buyer_name: 'Sharma Fabrics', deadline: '2026-10-20', delivery_date: '2026-10-22', days_late: 2, bottleneck_stage: 'weaving',
  stages: [
    { stage: 'spinning', finish_date: '2026-10-12' },
    { stage: 'weaving', finish_date: '2026-10-19' },
  ],
  what_ifs: [
    { kind: 'add_shift', label: 'Add a third shift on weaving', delivery_date: '2026-10-20', days_late: 0 },
    { kind: 'move_to_front', label: 'Move ORD-0012 to the front of every queue', delivery_date: '2026-10-21', days_late: 1 },
  ],
}
const SHORTAGE = {
  yarn_type: { id: 1, code: 'COT-30', name: 'Cotton 30s', colour: 'white' }, free_kg: -417.5, reorder_level_kg: 300, falls_below_on: '2026-10-10',
  supplier: { id: 1, name: 'Vardhman Yarns' }, order_by: '2026-10-05', suggested_kg: 750, overdue_days: 5,
}
const CAUSES = [
  { factor: 'weaving_machine', value: 'LOOM-05', defective: 3, inspected: 14, rate: 0.21, rest_rate: 0.09, p_value: 0.19, flagged: false },
  { factor: 'yarn_lot', value: 'L-0017', defective: 9, inspected: 20, rate: 0.45, rest_rate: 0.04, p_value: 0.00002, flagged: true },
]
const insightsApi = (over: Record<string, unknown> = {}) =>
  mockApi({ GET: { '/api/insights/late-orders': [ETA], '/api/insights/shortages': [SHORTAGE], '/api/insights/root-causes': CAUSES, ...over } })

describe('Insights', () => {
  it('says how late an order will be, against what was promised', async () => {
    insightsApi()
    renderPage(<Insights />)
    const card = (await screen.findByRole('link', { name: 'ORD-0012' })).closest('article')!
    expect(card).toHaveTextContent('2 days late')
    expect(card).toHaveTextContent('Sharma Fabrics')
    expect(card).toHaveTextContent(/weaving is what holds it up/)
  })

  it('offers what would fix it, with the new date for each', async () => {
    insightsApi()
    renderPage(<Insights />)
    const card = (await screen.findByRole('link', { name: 'ORD-0012' })).closest('article')!
    expect(card).toHaveTextContent(/Add a third shift on weaving: ready .* on time/)
    expect(card).toHaveTextContent(/front of every queue: ready .* 1 days late/)
  })

  it('shows each stage finish date and marks the bottleneck', async () => {
    insightsApi()
    renderPage(<Insights />)
    const steps = await screen.findByRole('list', { name: /finish date for each stage/i })
    const items = within(steps).getAllByRole('listitem')
    expect(items).toHaveLength(2)
    expect(items[1]).toHaveClass('is-bottleneck')
  })

  it('says every order is on time when none are late', async () => {
    insightsApi({ '/api/insights/late-orders': [] })
    renderPage(<Insights />)
    expect(await screen.findByText(/every order is on time/i)).toBeInTheDocument()
  })

  it('shows yarn to reorder, with how overdue it is and how much to buy', async () => {
    insightsApi()
    renderPage(<Insights />)
    const row = (await screen.findByText('COT-30')).closest('tr')!
    expect(row).toHaveTextContent('-417.5 kg')
    expect(row).toHaveTextContent('Vardhman Yarns')
    expect(row).toHaveTextContent('5 days overdue')
    expect(row).toHaveTextContent('750 kg')
  })

  it('says when a yarn has no supplier set', async () => {
    insightsApi({ '/api/insights/shortages': [{ ...SHORTAGE, supplier: null }] })
    renderPage(<Insights />)
    expect(await screen.findByText(/no supplier set/i)).toBeInTheDocument()
  })

  it('puts the flagged defect cause first and explains the rest could be chance', async () => {
    insightsApi()
    renderPage(<Insights />)
    await screen.findByText('L-0017')
    const order = [...document.querySelectorAll('tbody .code-text')].map((e) => e.textContent).filter((t) => t === 'L-0017' || t === 'LOOM-05')
    expect(order).toEqual(['L-0017', 'LOOM-05'])
    expect(screen.getByText('Likely cause')).toBeInTheDocument()
    expect(screen.getByText('Could be chance')).toBeInTheDocument()
    expect(screen.getByText('p < 0.001')).toBeInTheDocument()
  })

  it('shows the defect rate next to the rest of the mill', async () => {
    insightsApi()
    renderPage(<Insights />)
    const row = (await screen.findByText('L-0017')).closest('tr')!
    expect(row).toHaveTextContent('9 of 20')
    expect(row).toHaveTextContent('45%')
    expect(row).toHaveTextContent('4%')
  })

  it("keeps working when one of the three lists fails", async () => {
    insightsApi({ '/api/insights/shortages': { status: 500, error: 'boom' } })
    renderPage(<Insights />)
    expect(await screen.findByRole('link', { name: 'ORD-0012' })).toBeInTheDocument()
    expect(await screen.findByRole('alert')).toBeInTheDocument()
    expect(screen.getByText('L-0017')).toBeInTheDocument()
  })
})
