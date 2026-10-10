import { screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeEach, describe, expect, it, vi } from 'vitest'

vi.mock('@/lib/api/client', () => ({ api: { GET: vi.fn(), POST: vi.fn(), PATCH: vi.fn(), DELETE: vi.fn() } }))
import { api } from '@/lib/api/client'
import { mockApi, renderPage } from '@/test/utils'
import InvoicePage from './InvoicePage'
import Payables from './Payables'
import Receivables from './Receivables'

const BUYER = { id: 1, name: 'Sharma Fabrics' }
const RECEIVABLES = [
  { invoice_no: 'INV-0007', buyer: BUYER, issued_at: '2026-10-09T10:00:00Z', total: 39600, paid: 20000, balance: 19600 },
  { invoice_no: 'INV-0005', buyer: { id: 2, name: 'Lotus Apparel' }, issued_at: '2026-10-01T10:00:00Z', total: 10000, paid: 10000, balance: 0 },
  { invoice_no: 'INV-0009', buyer: BUYER, issued_at: '2026-10-10T10:00:00Z', total: 5000, paid: 0, balance: 5000 },
]
const SUPPLIER = { id: 1, name: 'Vardhman Yarns' }
const PAYABLES = [
  { bill_id: 17, bill_no: 'CH-5521', supplier: SUPPLIER, lot_code: 'L-0017', bill_date: '2026-10-10', due_date: '2026-11-09', amount: 200000, paid: 0, balance: 200000, overdue: false },
  { bill_id: 12, bill_no: 'CH-5400', supplier: SUPPLIER, lot_code: 'L-0012', bill_date: '2026-08-01', due_date: '2026-09-01', amount: 80000, paid: 30000, balance: 50000, overdue: true },
]
const INVOICE = {
  invoice_no: 'INV-0007', buyer: BUYER, dispatch_code: 'DSP-0004', vehicle_no: 'MH12AB1234', issued_at: '2026-10-09T10:00:00Z',
  total_amount: 39600, paid_amount: 20000, balance: 19600,
  lines: [{ order_code: 'ORD-0012', fabric: 'Poplin 58in', colour: 'navy', metres: 330, rate: 120, amount: 39600, roll_codes: ['R-0101', 'R-0102'] }],
}

const post = vi.mocked(api.POST)
beforeEach(() => vi.clearAllMocks())
const today = () => new Date().toISOString().slice(0, 10)

describe('Receivables', () => {
  it('totals what was invoiced, received and is still owed', async () => {
    mockApi({ GET: { '/api/money/receivables': RECEIVABLES } })
    renderPage(<Receivables />)
    await screen.findByText('INV-0007')
    const kpi = (label: string) => [...document.querySelectorAll('.kpi')].find((k) => k.querySelector('.kpi-label')?.textContent === label)!
    expect(kpi('Invoiced')).toHaveTextContent('54,600')
    expect(kpi('Received')).toHaveTextContent('30,000')
    expect(kpi('Still to receive')).toHaveTextContent('24,600')
  })

  it('marks each invoice paid, part paid or unpaid and links it to its page', async () => {
    mockApi({ GET: { '/api/money/receivables': RECEIVABLES } })
    renderPage(<Receivables />)
    const row = (no: string) => screen.getByRole('link', { name: no }).closest('tr')!
    await screen.findByText('INV-0007')
    expect(within(row('INV-0007')).getByText('Part paid')).toBeInTheDocument()
    expect(within(row('INV-0005')).getByText('Paid')).toBeInTheDocument()
    expect(within(row('INV-0009')).getByText('Unpaid')).toBeInTheDocument()
    expect(screen.getByRole('link', { name: 'INV-0007' })).toHaveAttribute('href', '/invoices/INV-0007')
  })

  it('offers a payment only where something is still owed', async () => {
    mockApi({ GET: { '/api/money/receivables': RECEIVABLES } })
    renderPage(<Receivables />)
    await screen.findByText('INV-0007')
    expect(screen.getByRole('button', { name: /record payment for INV-0007/i })).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: /record payment for INV-0005/i })).not.toBeInTheDocument()
  })

  it('records a payment with the amount, date and reference', async () => {
    mockApi({ GET: { '/api/money/receivables': RECEIVABLES }, POST: { '/api/payments/buyer': RECEIVABLES[0] } })
    renderPage(<Receivables />)
    await userEvent.click(await screen.findByRole('button', { name: /record payment for INV-0007/i }))
    const amount = screen.getByLabelText(/amount/i)
    expect(amount).toHaveValue('19600')
    await userEvent.clear(amount)
    await userEvent.type(amount, '5000')
    await userEvent.type(screen.getByLabelText(/reference/i), 'UTR 99123')
    await userEvent.click(screen.getByRole('button', { name: 'Record payment' }))
    await vi.waitFor(() => expect(post).toHaveBeenCalled())
    expect(post).toHaveBeenCalledWith('/api/payments/buyer', { body: { invoice_no: 'INV-0007', amount: 5000, received_on: today(), reference: 'UTR 99123' } })
    await vi.waitFor(() => expect(screen.queryByRole('dialog')).not.toBeInTheDocument())
  })

  it('refuses an amount above the balance, and sends nothing', async () => {
    mockApi({ GET: { '/api/money/receivables': RECEIVABLES } })
    renderPage(<Receivables />)
    await userEvent.click(await screen.findByRole('button', { name: /record payment for INV-0007/i }))
    const amount = screen.getByLabelText(/amount/i)
    await userEvent.clear(amount)
    await userEvent.type(amount, '25000')
    await userEvent.click(screen.getByRole('button', { name: 'Record payment' }))
    expect(await screen.findByText(/cannot be more than the balance/i)).toBeInTheDocument()
    expect(post).not.toHaveBeenCalled()
  })

  it('refuses an empty or zero amount', async () => {
    mockApi({ GET: { '/api/money/receivables': RECEIVABLES } })
    renderPage(<Receivables />)
    await userEvent.click(await screen.findByRole('button', { name: /record payment for INV-0007/i }))
    await userEvent.clear(screen.getByLabelText(/amount/i))
    await userEvent.click(screen.getByRole('button', { name: 'Record payment' }))
    expect(await screen.findByText(/enter the amount/i)).toBeInTheDocument()
    await userEvent.type(screen.getByLabelText(/amount/i), '0')
    await userEvent.click(screen.getByRole('button', { name: 'Record payment' }))
    expect(await screen.findByText(/above zero/i)).toBeInTheDocument()
    expect(post).not.toHaveBeenCalled()
  })

  it("shows the server's reason in the dialog when the payment is refused", async () => {
    mockApi({
      GET: { '/api/money/receivables': RECEIVABLES },
      POST: { '/api/payments/buyer': { status: 409, error: { code: 'CONFLICT', message: 'That invoice is already paid.', field: null, fields: null } } },
    })
    renderPage(<Receivables />)
    await userEvent.click(await screen.findByRole('button', { name: /record payment for INV-0007/i }))
    await userEvent.click(screen.getByRole('button', { name: 'Record payment' }))
    expect(await screen.findByRole('alert')).toHaveTextContent('That invoice is already paid.')
    expect(screen.getByRole('dialog')).toBeInTheDocument()
  })

  it('shows an empty state when there are no invoices', async () => {
    mockApi({ GET: { '/api/money/receivables': [] } })
    renderPage(<Receivables />)
    expect(await screen.findByText(/no invoices yet/i)).toBeInTheDocument()
  })
})

describe('Payables', () => {
  it('lists overdue bills first and flags them', async () => {
    mockApi({ GET: { '/api/money/payables': PAYABLES } })
    renderPage(<Payables />)
    await screen.findByText('CH-5521')
    const bills = [...document.querySelectorAll('tbody .code-text')].map((e) => e.textContent)
    expect(bills).toEqual(['CH-5400', 'CH-5521'])
    expect(screen.getByText('Overdue', { selector: '.badge' })).toBeInTheDocument()
  })

  it('totals what is owed and what is overdue', async () => {
    mockApi({ GET: { '/api/money/payables': PAYABLES } })
    renderPage(<Payables />)
    await screen.findByText('CH-5521')
    const kpi = (label: string) => [...document.querySelectorAll('.kpi')].find((k) => k.querySelector('.kpi-label')?.textContent === label)!
    expect(kpi('Still to pay')).toHaveTextContent('2,50,000')
    expect(kpi('Overdue')).toHaveTextContent('50,000')
  })

  it('links each bill to its yarn lot', async () => {
    mockApi({ GET: { '/api/money/payables': PAYABLES } })
    renderPage(<Payables />)
    expect(await screen.findByRole('link', { name: 'L-0017' })).toHaveAttribute('href', '/store/lots/L-0017')
  })

  it('records a supplier payment', async () => {
    mockApi({ GET: { '/api/money/payables': PAYABLES }, POST: { '/api/payments/supplier': PAYABLES[1] } })
    renderPage(<Payables />)
    await userEvent.click(await screen.findByRole('button', { name: /record payment for bill CH-5400/i }))
    await userEvent.click(screen.getByRole('button', { name: 'Record payment' }))
    await vi.waitFor(() => expect(post).toHaveBeenCalled())
    expect(post).toHaveBeenCalledWith('/api/payments/supplier', { body: { bill_id: 12, amount: 50000, paid_on: today() } })
  })

  it('refuses a payment above the balance', async () => {
    mockApi({ GET: { '/api/money/payables': PAYABLES } })
    renderPage(<Payables />)
    await userEvent.click(await screen.findByRole('button', { name: /record payment for bill CH-5400/i }))
    const amount = screen.getByLabelText(/amount/i)
    await userEvent.clear(amount)
    await userEvent.type(amount, '60000')
    await userEvent.click(screen.getByRole('button', { name: 'Record payment' }))
    expect(await screen.findByText(/cannot be more than the balance/i)).toBeInTheDocument()
    expect(post).not.toHaveBeenCalled()
  })
})

describe('InvoicePage', () => {
  const setup = () => {
    mockApi({ GET: { '/api/invoices/{invoice_no}': INVOICE, '/api/auth/me': { id: 1, username: 'accountant', role: 'accountant', display_name: 'Meena', worker_id: null, buyer_id: null } } })
    renderPage(<InvoicePage />, { route: '/invoices/INV-0007', path: '/invoices/:no' })
  }

  it('shows the buyer, dispatch and vehicle', async () => {
    setup()
    const inv = await screen.findByRole('article', { name: 'Invoice INV-0007' })
    expect(inv).toHaveTextContent('Sharma Fabrics')
    expect(inv).toHaveTextContent('MH12AB1234')
    expect(within(inv).getByRole('link', { name: 'DSP-0004' })).toHaveAttribute('href', '/dispatch/DSP-0004')
  })

  it('lists each line with its rolls, metres, rate and amount', async () => {
    setup()
    const inv = await screen.findByRole('article')
    expect(inv).toHaveTextContent('ORD-0012')
    expect(inv).toHaveTextContent('R-0101, R-0102')
    expect(inv).toHaveTextContent('330 m')
    expect(inv).toHaveTextContent('39,600')
  })

  it('shows the total, what was received and the balance due', async () => {
    setup()
    const inv = await screen.findByRole('article')
    expect(inv).toHaveTextContent(/Received\s*₹20,000/)
    expect(inv).toHaveTextContent(/Balance due\s*₹19,600/)
    expect(within(inv).getByText('Part paid')).toBeInTheDocument()
  })

  it('prints the page', async () => {
    const print = vi.spyOn(window, 'print').mockImplementation(() => undefined)
    setup()
    await userEvent.click(await screen.findByRole('button', { name: /print/i }))
    expect(print).toHaveBeenCalled()
  })

  it('says so when the invoice cannot be found', async () => {
    mockApi({ GET: { '/api/invoices/{invoice_no}': { status: 404, error: { code: 'NOT_FOUND', message: 'No such invoice', field: null, fields: null } }, '/api/auth/me': { id: 1, username: 'accountant', role: 'accountant', display_name: 'Meena', worker_id: null, buyer_id: null } } })
    renderPage(<InvoicePage />, { route: '/invoices/INV-9999', path: '/invoices/:no' })
    expect(await screen.findByRole('alert')).toHaveTextContent(/no such invoice|something went wrong/i)
  })
})
