import { fireEvent, screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeEach, describe, expect, it, vi } from 'vitest'

vi.mock('@/lib/api/client', () => ({ api: { GET: vi.fn(), POST: vi.fn(), PATCH: vi.fn(), DELETE: vi.fn() } }))
import { api } from '@/lib/api/client'
import { mockApi, renderPage } from '@/test/utils'
import Attendance from './Attendance'
import Wages from './Wages'

const post = vi.mocked(api.POST)
const get = vi.mocked(api.GET)
const today = () => new Date().toISOString().slice(0, 10)

const SHIFTS = [
  { id: 1, name: 'A', start_time: '06:00:00', end_time: '14:00:00' },
  { id: 2, name: 'B', start_time: '14:00:00', end_time: '22:00:00' },
]
const row = (id: number, name: string, status: string | null) => ({ worker_id: id, worker_code: `W-0${id}`, worker_name: name, status })
const sheet = (rows: ReturnType<typeof row>[]) => ({ date: today(), shift: { id: 1, name: 'A' }, rows })
const UNMARKED = sheet([row(1, 'Asha Patel', null), row(2, 'Bhanu Singh', null), row(3, 'Chitra Rao', null)])

beforeEach(() => vi.clearAllMocks())

async function chooseShiftA(attendance = UNMARKED) {
  mockApi({ GET: { '/api/shifts': SHIFTS, '/api/attendance': attendance }, POST: { '/api/attendance': attendance } })
  renderPage(<Attendance />)
  await screen.findByRole('option', { name: /^A \(/ })
  await userEvent.selectOptions(screen.getByLabelText('Shift'), '1')
}
async function openShiftA(attendance = UNMARKED) {
  await chooseShiftA(attendance)
  return screen.findByRole('region', { name: /attendance for shift A/i })
}
const radio = (name: string, label: string) => within(screen.getByRole('group', { name: `Attendance for ${name}` })).getByRole('radio', { name: label })

describe('Attendance', () => {
  it('asks you to choose a shift first', async () => {
    mockApi({ GET: { '/api/shifts': SHIFTS } })
    renderPage(<Attendance />)
    expect(await screen.findByText(/choose a shift/i)).toBeInTheDocument()
    expect(get).not.toHaveBeenCalledWith('/api/attendance', expect.anything())
  })

  it('lists the shifts with their hours', async () => {
    mockApi({ GET: { '/api/shifts': SHIFTS } })
    renderPage(<Attendance />)
    expect(await screen.findByRole('option', { name: 'A (06:00 to 14:00)' })).toBeInTheDocument()
  })

  it("loads the chosen day and shift, starting on today's date", async () => {
    await openShiftA()
    expect(get).toHaveBeenCalledWith('/api/attendance', { params: { query: { date: today(), shift_id: 1 } } })
  })

  it('starts everyone as present, since that is the usual day', async () => {
    await openShiftA()
    for (const name of ['Asha Patel', 'Bhanu Singh', 'Chitra Rao']) expect(radio(name, 'Present')).toBeChecked()
    expect(screen.getByText('Not marked yet')).toBeInTheDocument()
    expect(screen.getByRole('status')).toHaveTextContent('3 present, 0 half day, 0 absent')
  })

  it('saves the whole sheet, with the ones who were not present changed', async () => {
    await openShiftA()
    await userEvent.click(radio('Bhanu Singh', 'Absent'))
    await userEvent.click(radio('Chitra Rao', 'Half day'))
    expect(screen.getByRole('status')).toHaveTextContent('1 present, 1 half day, 1 absent')
    await userEvent.click(screen.getByRole('button', { name: /save attendance/i }))
    await vi.waitFor(() => expect(post).toHaveBeenCalled())
    expect(post).toHaveBeenCalledWith('/api/attendance', {
      body: { date: today(), shift_id: 1, entries: [{ worker_id: 1, status: 'present' }, { worker_id: 2, status: 'absent' }, { worker_id: 3, status: 'half_day' }] },
    })
  })

  it('can save a day where everyone was present without touching anything', async () => {
    await openShiftA()
    const save = screen.getByRole('button', { name: /save attendance/i })
    expect(save).toBeEnabled()
    await userEvent.click(save)
    await vi.waitFor(() => expect(post).toHaveBeenCalled())
    expect(post.mock.calls[0][1]).toMatchObject({ body: { entries: [{ status: 'present' }, { status: 'present' }, { status: 'present' }] } })
  })

  it('shows what was already marked, and nothing to save until you change it', async () => {
    await openShiftA(sheet([row(1, 'Asha Patel', 'present'), row(2, 'Bhanu Singh', 'absent')]))
    expect(radio('Bhanu Singh', 'Absent')).toBeChecked()
    expect(screen.getByText('Saved')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /save attendance/i })).toBeDisabled()
    await userEvent.click(radio('Bhanu Singh', 'Present'))
    expect(screen.getByRole('button', { name: /save attendance/i })).toBeEnabled()
  })

  it('marks everyone present in one go', async () => {
    await openShiftA(sheet([row(1, 'Asha Patel', 'absent'), row(2, 'Bhanu Singh', 'half_day')]))
    await userEvent.click(screen.getByRole('button', { name: /mark everyone present/i }))
    expect(radio('Asha Patel', 'Present')).toBeChecked()
    expect(radio('Bhanu Singh', 'Present')).toBeChecked()
  })

  it("shows the server's reason when saving fails, and keeps your changes", async () => {
    mockApi({
      GET: { '/api/shifts': SHIFTS, '/api/attendance': UNMARKED },
      POST: { '/api/attendance': { status: 422, error: { code: 'FUTURE_DATE', message: 'Attendance cannot be marked for a future date', field: 'date', fields: null } } },
    })
    renderPage(<Attendance />)
    await screen.findByRole('option', { name: /^A \(/ })
    await userEvent.selectOptions(screen.getByLabelText('Shift'), '1')
    await screen.findByRole('region', { name: /attendance for shift A/i })
    await userEvent.click(radio('Asha Patel', 'Absent'))
    await userEvent.click(screen.getByRole('button', { name: /save attendance/i }))
    expect(await screen.findByRole('alert')).toHaveTextContent('Attendance cannot be marked for a future date')
    expect(radio('Asha Patel', 'Absent')).toBeChecked()
  })

  it('says so when there is nobody on the payroll', async () => {
    await chooseShiftA(sheet([]))
    expect(await screen.findByText(/no workers on the payroll/i)).toBeInTheDocument()
  })

  it('starts a fresh sheet when the date changes', async () => {
    await openShiftA()
    await userEvent.click(radio('Asha Patel', 'Absent'))
    fireEvent.change(screen.getByLabelText('Date'), { target: { value: '2026-09-01' } })
    await vi.waitFor(() => expect(get).toHaveBeenCalledWith('/api/attendance', { params: { query: { date: '2026-09-01', shift_id: 1 } } }))
    await screen.findByRole('group', { name: 'Attendance for Asha Patel' })
    expect(radio('Asha Patel', 'Present')).toBeChecked()
  })
})

const WAGES = {
  month: new Date().toISOString().slice(0, 7),
  rows: [
    { worker_id: 1, worker_code: 'W-01', worker_name: 'Asha Patel', daily_wage: 800, present: 20, half_days: 2, absent: 1, earned: 16800, paid: 6800, owed: 10000 },
    { worker_id: 2, worker_code: 'W-02', worker_name: 'Bhanu Singh', daily_wage: 700, present: 10, half_days: 0, absent: 0, earned: 7000, paid: 7000, owed: 0 },
    { worker_id: 3, worker_code: 'W-03', worker_name: 'Chitra Rao', daily_wage: 600, present: 0, half_days: 0, absent: 0, earned: 0, paid: 0, owed: 0 },
  ],
  total_earned: 23800,
  total_paid: 13800,
  total_owed: 10000,
}
const kpi = (label: string) => [...document.querySelectorAll('.kpi')].find((k) => k.querySelector('.kpi-label')?.textContent === label)!

describe('Wages', () => {
  it('asks for this month and shows earned, paid and still owed', async () => {
    mockApi({ GET: { '/api/wages': WAGES } })
    renderPage(<Wages />)
    await screen.findByText('Asha Patel')
    expect(get).toHaveBeenCalledWith('/api/wages', { params: { query: { month: WAGES.month } } })
    expect(kpi('Earned')).toHaveTextContent('₹23,800')
    expect(kpi('Paid')).toHaveTextContent('₹13,800')
    expect(kpi('Still owed')).toHaveTextContent('₹10,000')
  })

  it('shows each worker with their days and money', async () => {
    mockApi({ GET: { '/api/wages': WAGES } })
    renderPage(<Wages />)
    const r = (await screen.findByText('Asha Patel')).closest('tr')!
    expect(r).toHaveTextContent('W-01')
    expect(r).toHaveTextContent('₹800')
    expect(r).toHaveTextContent('₹16,800')
    expect(r).toHaveTextContent('₹10,000')
  })

  it('offers payment only to workers who are owed something, and marks the settled ones paid', async () => {
    mockApi({ GET: { '/api/wages': WAGES } })
    renderPage(<Wages />)
    await screen.findByText('Asha Patel')
    expect(screen.getByRole('button', { name: /record payment for Asha Patel/i })).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: /record payment for Bhanu Singh/i })).not.toBeInTheDocument()
    expect(within(screen.getByText('Bhanu Singh').closest('tr')!).getByText('Paid')).toBeInTheDocument()
    expect(within(screen.getByText('Chitra Rao').closest('tr')!).queryByText('Paid')).not.toBeInTheDocument()
  })

  it('pays for the whole month, starting from what is owed', async () => {
    mockApi({ GET: { '/api/wages': WAGES }, POST: { '/api/payments/wages': WAGES.rows[0] } })
    renderPage(<Wages />)
    await userEvent.click(await screen.findByRole('button', { name: /record payment for Asha Patel/i }))
    expect(screen.getByLabelText(/amount/i)).toHaveValue('10000')
    const amount = screen.getByLabelText(/amount/i)
    await userEvent.clear(amount)
    await userEvent.type(amount, '4000')
    await userEvent.click(within(screen.getByRole('dialog')).getByRole('button', { name: 'Record payment' }))
    await vi.waitFor(() => expect(post).toHaveBeenCalled())
    const month = WAGES.month
    const [y, m] = month.split('-').map(Number)
    const last = String(new Date(y, m, 0).getDate()).padStart(2, '0')
    expect(post).toHaveBeenCalledWith('/api/payments/wages', { body: { worker_id: 1, period_start: `${month}-01`, period_end: `${month}-${last}`, amount: 4000, paid_at: today() } })
  })

  it('refuses more than is owed before sending', async () => {
    mockApi({ GET: { '/api/wages': WAGES } })
    renderPage(<Wages />)
    await userEvent.click(await screen.findByRole('button', { name: /record payment for Asha Patel/i }))
    const amount = screen.getByLabelText(/amount/i)
    await userEvent.clear(amount)
    await userEvent.type(amount, '10000.5')
    await userEvent.click(within(screen.getByRole('dialog')).getByRole('button', { name: 'Record payment' }))
    expect(await screen.findByText(/cannot be more than the balance/i)).toBeInTheDocument()
    expect(post).not.toHaveBeenCalled()
  })

  it("shows the server's refusal in the dialog", async () => {
    mockApi({
      GET: { '/api/wages': WAGES },
      POST: { '/api/payments/wages': { status: 409, error: { code: 'OVERPAYMENT', message: 'Asha Patel is owed only ₹9,000.00 for this period', field: 'amount', fields: null } } },
    })
    renderPage(<Wages />)
    await userEvent.click(await screen.findByRole('button', { name: /record payment for Asha Patel/i }))
    await userEvent.click(within(screen.getByRole('dialog')).getByRole('button', { name: 'Record payment' }))
    expect(await screen.findByText(/owed only ₹9,000.00/)).toBeInTheDocument()
  })

  it('asks for another month when the picker changes', async () => {
    mockApi({ GET: { '/api/wages': WAGES } })
    renderPage(<Wages />)
    await screen.findByText('Asha Patel')
    fireEvent.change(screen.getByLabelText('Month'), { target: { value: '2026-09' } })
    await vi.waitFor(() => expect(get).toHaveBeenCalledWith('/api/wages', { params: { query: { month: '2026-09' } } }))
  })

  it('says so when there is nobody on the payroll', async () => {
    mockApi({ GET: { '/api/wages': { ...WAGES, rows: [], total_earned: 0, total_paid: 0, total_owed: 0 } } })
    renderPage(<Wages />)
    expect(await screen.findByText(/no workers on the payroll/i)).toBeInTheDocument()
  })

  it('shows a Retry state when the wages cannot be loaded', async () => {
    mockApi({ GET: { '/api/wages': { status: 500, error: 'boom' } } })
    renderPage(<Wages />)
    expect(await screen.findByRole('alert')).toHaveTextContent(/something went wrong/i)
  })
})
