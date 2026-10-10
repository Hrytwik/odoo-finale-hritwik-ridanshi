import { screen, within } from '@testing-library/react'
import { beforeEach, describe, expect, it, vi } from 'vitest'

vi.mock('@/lib/api/client', () => ({ api: { GET: vi.fn(), POST: vi.fn(), PATCH: vi.fn(), DELETE: vi.fn() } }))
import { mockApi, renderPage } from '@/test/utils'
import YarnStock from './YarnStock'

const COTTON = { id: 1, code: '30S-COT-RAW', name: '30s cotton', colour: 'raw white' }
const POLY = { id: 2, code: '40S-PC-RAW', name: '40s poly-cotton', colour: 'raw white' }
const STOCK = [
  { yarn_type: COTTON, on_hand_kg: 212.5, outstanding_kg: 630, free_kg: -417.5, reorder_level_kg: 300, below_reorder: true },
  { yarn_type: POLY, on_hand_kg: 1450, outstanding_kg: 400, free_kg: 1050, reorder_level_kg: 250, below_reorder: false },
]
const SHORTAGES = [
  {
    yarn_type: COTTON,
    free_kg: -417.5,
    reorder_level_kg: 300,
    falls_below_on: '2026-10-10',
    supplier: { id: 1, name: 'Vardhman Yarns' },
    order_by: '2026-10-05',
    suggested_kg: 750,
    overdue_days: 5,
  },
]

beforeEach(() => {
  vi.clearAllMocks()
})

describe('YarnStock', () => {
  it('lists every yarn type with on hand, needed and free kg', async () => {
    mockApi({ GET: { '/api/stock': STOCK, '/api/insights/shortages': SHORTAGES } })
    renderPage(<YarnStock />)
    const table = await screen.findByRole('table')
    const cotton = within(table).getByRole('row', { name: /30s cotton/i })
    expect(cotton).toHaveTextContent('212.5 kg')
    expect(cotton).toHaveTextContent('630 kg')
    expect(cotton).toHaveTextContent('-417.5 kg')
    const poly = within(table).getByRole('row', { name: /40s poly-cotton/i })
    expect(poly).toHaveTextContent('1,450 kg')
    expect(poly).toHaveTextContent('1,050 kg')
  })

  it('flags a yarn that is below its reorder level and shows negative free stock in red', async () => {
    mockApi({ GET: { '/api/stock': STOCK, '/api/insights/shortages': [] } })
    renderPage(<YarnStock />)
    const table = await screen.findByRole('table')
    expect(within(within(table).getByRole('row', { name: /30s cotton/i })).getByText('Reorder now')).toBeInTheDocument()
    expect(within(within(table).getByRole('row', { name: /40s poly-cotton/i })).getByText('OK')).toBeInTheDocument()
    expect(screen.getByText('-417.5 kg')).toHaveClass('text-danger')
  })

  it('summarises how many yarn types need ordering', async () => {
    mockApi({ GET: { '/api/stock': STOCK, '/api/insights/shortages': SHORTAGES } })
    renderPage(<YarnStock />)
    await screen.findByRole('table')
    expect(screen.getByText('Need reordering').closest('.kpi')).toHaveTextContent('1')
    expect(screen.getByText('Yarn types').closest('.kpi')).toHaveTextContent('2')
  })

  it('says what to order, from whom, by when, and how late it is', async () => {
    mockApi({ GET: { '/api/stock': STOCK, '/api/insights/shortages': SHORTAGES } })
    renderPage(<YarnStock />)
    const card = (await screen.findByText(/order 750 kg/i)).closest('.shortage')!
    expect(card).toHaveTextContent('30s cotton')
    expect(card).toHaveTextContent('Vardhman Yarns')
    expect(card).toHaveTextContent('5 Oct')
    expect(card).toHaveTextContent('5 days late')
  })

  it('shows a calm message when nothing needs ordering', async () => {
    mockApi({ GET: { '/api/stock': STOCK, '/api/insights/shortages': [] } })
    renderPage(<YarnStock />)
    expect(await screen.findByText(/nothing needs ordering/i)).toBeInTheDocument()
  })

  it('shows an empty state when there is no yarn yet', async () => {
    mockApi({ GET: { '/api/stock': [], '/api/insights/shortages': [] } })
    renderPage(<YarnStock />)
    expect(await screen.findByText(/no yarn types yet/i)).toBeInTheDocument()
  })

  it('shows a Retry state when stock cannot be loaded', async () => {
    mockApi({ GET: { '/api/stock': { status: 500, error: 'boom' }, '/api/insights/shortages': [] } })
    renderPage(<YarnStock />)
    expect(await screen.findByRole('alert')).toHaveTextContent(/something went wrong/i)
    expect(screen.getByRole('button', { name: /retry/i })).toBeInTheDocument()
  })

  it('keeps the stock table when only the reorder suggestions fail', async () => {
    mockApi({ GET: { '/api/stock': STOCK, '/api/insights/shortages': { status: 500, error: 'boom' } } })
    renderPage(<YarnStock />)
    expect(await screen.findByRole('table')).toBeInTheDocument()
    expect(await screen.findByText(/could not load the reorder suggestions/i)).toBeInTheDocument()
  })
})
