import { fireEvent, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeEach, describe, expect, it, vi } from 'vitest'

vi.mock('@/lib/api/client', () => ({ api: { GET: vi.fn(), POST: vi.fn(), PATCH: vi.fn(), DELETE: vi.fn() } }))
import { api } from '@/lib/api/client'
import { mockApi, renderPage } from '@/test/utils'
import QcInspect from './QcInspect'

const ROLL = { id: 142, code: 'R-0142', order_code: 'ORD-0012', buyer_name: 'Sharma Fabrics', fabric: 'Poplin 58in', colour: 'navy', metres: 110, status: 'awaiting_qc', created_at: '2026-10-10T10:00:00Z' }
const PASSPORT = { roll: ROLL, order_code: 'ORD-0012', buyer_name: 'Sharma Fabrics', deadline: '2026-10-20', yarn_lots: [], runs: [], inspections: [], cost: null, dispatch: null }
const SUGGESTION = {
  model_version: 'yolo-v1', verdict: 'rework',
  boxes: [
    { x: 0.42, y: 0.31, w: 0.08, h: 0.07, defect_type: 'hole', confidence: 0.91 },
    { x: 0.1, y: 0.6, w: 0.1, h: 0.1, defect_type: 'hole', confidence: 0.8 },
    { x: 0.7, y: 0.2, w: 0.1, h: 0.1, defect_type: 'stain', confidence: 0.6 },
  ],
}
const ANALYZED = { available: true, message: null, suggestion: SUGGESTION }
const me = (role: string) => ({ id: 2, username: role, role, display_name: role, worker_id: 2, buyer_id: null })

function setup(extra: Parameters<typeof mockApi>[0] = {}, passport: unknown = PASSPORT) {
  mockApi({
    GET: { '/api/auth/me': me('qc'), '/api/rolls/{roll_code}/passport': passport, ...extra.GET },
    POST: {
      '/api/uploads': { path: 'uploads/abc.jpg', url: '/api/uploads/abc.jpg' }, '/api/qc/analyze': ANALYZED,
      '/api/qc/inspections': { id: 301, verdict: 'rework' }, ...extra.POST,
    },
  })
  return renderPage(<QcInspect />, { path: '/qc/:rollCode', route: '/qc/R-0142', extra: [{ path: '/qc', element: <p>queue page</p> }] })
}
const photo = () => new File(['x'], 'cloth.jpg', { type: 'image/jpeg' })
const posted = () => vi.mocked(api.POST).mock.calls.map((c) => c[0])

beforeEach(() => {
  vi.clearAllMocks()
  URL.createObjectURL = vi.fn(() => 'blob:cloth')
  URL.revokeObjectURL = vi.fn()
})

describe('QcInspect: a login with no linked inspector', () => {
  it('says why it cannot record a verdict, and does not offer to', async () => {
    setup({ GET: { '/api/auth/me': { ...me('owner'), worker_id: null } } })
    expect(await screen.findByText(/not linked to an inspector/i)).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /record verdict/i })).toBeDisabled()
  })
})

describe('QcInspect: manual checking works without any AI', () => {
  it('shows which roll is being checked', async () => {
    setup()
    expect(await screen.findByRole('heading', { level: 1, name: /R-0142/ })).toBeInTheDocument()
    expect(screen.getByText(/ORD-0012/)).toBeInTheDocument()
    expect(screen.getByText(/110 m/)).toBeInTheDocument()
  })

  it('passes a roll with no defects', async () => {
    setup()
    await userEvent.click(await screen.findByRole('radio', { name: /pass/i }))
    await userEvent.click(screen.getByRole('button', { name: /record verdict/i }))
    await waitFor(() => expect(api.POST).toHaveBeenCalledWith('/api/qc/inspections', { body: { roll_code: 'R-0142', verdict: 'pass', defects: [] } }))
    expect(await screen.findByText('queue page')).toBeInTheDocument()
  })

  it('needs a verdict before it will record anything', async () => {
    setup()
    await userEvent.click(await screen.findByRole('button', { name: /record verdict/i }))
    expect(await screen.findByText('Choose a verdict')).toBeInTheDocument()
    expect(api.POST).not.toHaveBeenCalled()
  })

  it('needs at least one defect for rework or reject', async () => {
    setup()
    await userEvent.click(await screen.findByRole('radio', { name: /rework/i }))
    await userEvent.click(screen.getByRole('button', { name: /record verdict/i }))
    expect(await screen.findByText(/add at least one defect/i)).toBeInTheDocument()
    expect(api.POST).not.toHaveBeenCalled()
  })

  it('records a rework with the defects the inspector entered', async () => {
    setup()
    await userEvent.click(await screen.findByRole('radio', { name: /rework/i }))
    await userEvent.click(screen.getByRole('button', { name: /add defect/i }))
    await userEvent.selectOptions(screen.getByLabelText(/defect type/i), 'hole')
    await userEvent.clear(screen.getByLabelText(/how many/i))
    await userEvent.type(screen.getByLabelText(/how many/i), '2')
    await userEvent.type(screen.getByLabelText(/remark/i), 'Near the selvedge')
    await userEvent.click(screen.getByRole('button', { name: /record verdict/i }))
    await waitFor(() =>
      expect(api.POST).toHaveBeenCalledWith('/api/qc/inspections', {
        body: { roll_code: 'R-0142', verdict: 'rework', defects: [{ defect_type: 'hole', count: 2, ai_detected: false }], notes: 'Near the selvedge' },
      }),
    )
  })

  it('rejects a defect count of zero', async () => {
    setup()
    await userEvent.click(await screen.findByRole('radio', { name: /reject/i }))
    await userEvent.click(screen.getByRole('button', { name: /add defect/i }))
    await userEvent.selectOptions(screen.getByLabelText(/defect type/i), 'stain')
    await userEvent.clear(screen.getByLabelText(/how many/i))
    await userEvent.type(screen.getByLabelText(/how many/i), '0')
    await userEvent.click(screen.getByRole('button', { name: /record verdict/i }))
    expect(await screen.findByText(/add at least one defect/i)).toBeInTheDocument()
    expect(api.POST).not.toHaveBeenCalled()
  })

  it('lets the inspector remove a defect row', async () => {
    setup()
    await userEvent.click(await screen.findByRole('button', { name: /add defect/i }))
    expect(screen.getAllByLabelText(/defect type/i)).toHaveLength(1)
    await userEvent.click(screen.getByRole('button', { name: /remove defect/i }))
    expect(screen.queryByLabelText(/defect type/i)).not.toBeInTheDocument()
  })

  it('sends one request when Record verdict is pressed twice quickly', async () => {
    setup()
    await userEvent.click(await screen.findByRole('radio', { name: /pass/i }))
    vi.mocked(api.POST).mockReturnValue(new Promise(() => {}) as never)
    const form = screen.getByRole('button', { name: /record verdict/i }).closest('form')!
    fireEvent.submit(form)
    fireEvent.submit(form)
    await waitFor(() => expect(api.POST).toHaveBeenCalledTimes(1))
  })

  it("shows the server's reason when the verdict is refused", async () => {
    setup({ POST: { '/api/qc/inspections': { status: 409, error: { code: 'ROLL_WRONG_STATUS', message: 'This roll is not waiting for QC', field: null, fields: null } } } })
    await userEvent.click(await screen.findByRole('radio', { name: /pass/i }))
    await userEvent.click(screen.getByRole('button', { name: /record verdict/i }))
    expect(await screen.findByRole('alert')).toHaveTextContent('This roll is not waiting for QC')
  })
})

describe('QcInspect: with the photo and the AI suggestion', () => {
  async function analyse() {
    // choosing the photo sends it to the model straight away
    await userEvent.upload(await screen.findByLabelText(/photo/i), photo())
  }

  it('uploads the photo, asks the model, and draws its boxes over the photo', async () => {
    setup()
    await analyse()
    expect(await screen.findByTestId('box-0')).toBeInTheDocument()
    expect(posted()).toEqual(['/api/uploads', '/api/qc/analyze'])
    expect(vi.mocked(api.POST).mock.calls[1][1]).toMatchObject({ body: { photo_path: 'uploads/abc.jpg' } })
    expect(screen.getAllByTestId(/^box-/)).toHaveLength(3)
  })

  it('shows what the model suggests, as a suggestion', async () => {
    setup()
    await analyse()
    expect((await screen.findByText(/ai suggests/i)).closest('p')).toHaveTextContent(/rework/i)
  })

  it('prefills the verdict and the defect counts from the suggestion, ready to be changed', async () => {
    setup()
    await analyse()
    await screen.findByTestId('box-0')
    expect(screen.getByText(/ai verdict: rework/i)).toBeInTheDocument()
    expect(screen.queryByRole('radio')).not.toBeInTheDocument()
    const types = screen.getAllByLabelText(/defect type/i).map((s) => (s as HTMLSelectElement).value)
    expect(types.sort()).toEqual(['hole', 'stain'])
    const holeRow = screen.getAllByLabelText(/defect type/i).find((s) => (s as HTMLSelectElement).value === 'hole')!.closest('.defect-row')!
    expect(within(holeRow as HTMLElement).getByLabelText(/how many/i)).toHaveValue(2)
  })

  it('drafts the remark from what the model found, and keeps it editable', async () => {
    setup()
    await analyse()
    await screen.findByTestId('box-0')
    expect((screen.getByLabelText(/remark/i) as HTMLTextAreaElement).value).toMatch(/model found 3 defects.*suggests rework/i)
  })

  it('sends the photo, the model output and which defects the model found', async () => {
    setup()
    await analyse()
    await screen.findByTestId('box-0')
    await userEvent.click(screen.getByRole('button', { name: /record verdict/i }))
    await waitFor(() => expect(posted()).toContain('/api/qc/inspections'))
    const call = vi.mocked(api.POST).mock.calls.find((c) => c[0] === '/api/qc/inspections')!
    expect(call[1]).toMatchObject({
      body: {
        roll_code: 'R-0142', verdict: 'rework', photo_path: 'uploads/abc.jpg', ai_suggestion: SUGGESTION,
        defects: expect.arrayContaining([{ defect_type: 'hole', count: 2, ai_detected: true }, { defect_type: 'stain', count: 1, ai_detected: true }]),
      },
    })
  })

  it('says plainly when the inspector is overriding the model, and that it is recorded', async () => {
    setup()
    await analyse()
    await screen.findByTestId('box-0')
    await userEvent.click(screen.getByRole('button', { name: /change the verdict/i }))
    await userEvent.click(screen.getByRole('radio', { name: /pass/i }))
    const notice = await screen.findByText(/you are overriding the ai/i)
    expect(notice).toHaveTextContent(/override is recorded/i)
  })

  it('does not say overriding when the inspector agrees with the model', async () => {
    setup()
    await analyse()
    await screen.findByTestId('box-0')
    expect(screen.queryByText(/you are overriding the ai/i)).not.toBeInTheDocument()
  })

  it('uploads the photo only once, even if it is analysed again', async () => {
    setup()
    await analyse()
    await screen.findByTestId('box-0')
    await userEvent.click(screen.getByRole('button', { name: /analy[sz]e photo again/i }))
    await waitFor(() => expect(posted().filter((p) => p === '/api/qc/analyze')).toHaveLength(2))
    expect(posted().filter((p) => p === '/api/uploads')).toHaveLength(1)
  })

  it('labels a suggestion from a model that is not validated yet, and still lets the inspector decide', async () => {
    setup({ POST: { '/api/qc/analyze': { available: false, message: 'Vision model not loaded yet (example data)', suggestion: SUGGESTION } } })
    await analyse()
    expect(await screen.findByText(/unvalidated/i)).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /record verdict/i })).toBeEnabled()
  })

  it('works without a suggestion when the model is not available at all', async () => {
    setup({ POST: { '/api/qc/analyze': { available: false, message: 'Vision model not loaded yet', suggestion: null } } })
    await analyse()
    expect(await screen.findByText(/vision model not loaded yet/i)).toBeInTheDocument()
    expect(screen.queryByTestId('box-0')).not.toBeInTheDocument()
    await userEvent.click(screen.getByRole('radio', { name: /pass/i }))
    expect(screen.getByRole('radio', { name: /pass/i })).toBeChecked()
  })

  it('says so, and keeps checking possible, when the analysis fails', async () => {
    setup({ POST: { '/api/qc/analyze': { status: 500, error: 'boom' } } })
    await analyse()
    expect(await screen.findByText(/could not analyse the photo/i)).toBeInTheDocument()
    await userEvent.click(screen.getByRole('radio', { name: /pass/i }))
    expect(screen.getByRole('button', { name: /record verdict/i })).toBeEnabled()
  })
})

describe('QcInspect: errors', () => {
  it('says so plainly when the roll does not exist', async () => {
    setup({ GET: { '/api/rolls/{roll_code}/passport': { status: 404, error: { code: 'NOT_FOUND', message: 'Roll not found', field: null, fields: null } } } })
    expect(await screen.findByRole('alert')).toHaveTextContent('Roll not found')
  })

  it('warns when the roll is not waiting for a check', async () => {
    setup({}, { ...PASSPORT, roll: { ...ROLL, status: 'in_store' } })
    expect(await screen.findByText(/not waiting for a quality check/i)).toBeInTheDocument()
  })
})
