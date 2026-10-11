import { screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeEach, describe, expect, it, vi } from 'vitest'

vi.mock('@/lib/api/client', () => ({ api: { GET: vi.fn(), POST: vi.fn(), PATCH: vi.fn(), DELETE: vi.fn() } }))
import { api } from '@/lib/api/client'
import { mockApi, renderPage } from '@/test/utils'
import VisionModel from './VisionModel'

const item = (id: number, over: Record<string, unknown> = {}) => ({
  id, roll_code: `R-000${id}`, order_code: 'ORD-0001', buyer_name: 'Sharma Fabrics', fabric: 'Poplin 58in', colour: 'navy', metres: 120,
  lots: ['LOT-0001'], inspector: 'Asha', inspected_at: '2026-10-10T09:00:00Z', verdict: 'pass', overrode_ai: false, defects: [],
  remark: null, photo_url: `/api/uploads/p${id}.jpg`, ai: null, ...over,
})
const PAGE = {
  items: [
    item(2, { verdict: 'rework', remark: 'Slub near the edge', overrode_ai: true, defects: [{ defect_type: 'thread_fault', count: 2, ai_detected: false }], ai: { model_version: 'm1', verdict: 'pass', boxes: [] } }),
    item(1),
  ],
  counts: { total: 2, passed: 1, rework: 1, rejected: 0, overrode_ai: 1 }, limit: 24, offset: 0,
}
const FILTERS = { orders: [{ code: 'ORD-0001', buyer_name: 'Sharma Fabrics' }], lots: ['LOT-0001'] }
const me = { id: 1, username: 'owner', role: 'owner', display_name: 'Owner', worker_id: null, buyer_id: null }
const QUEUE = { counts: { awaiting_qc: 0, awaiting_rework: 0, in_rework: 0, passed: 0, rejected: 0 }, rolls: [] }
const NO_MODEL = { available: false, model_version: null, trained_at: null, datasets: [], test_defective: 0, test_clean: 0, clean_false_alarm_rate: null, per_class: [], confusion_labels: [], confusion_matrix: [] }

function setup(page: unknown = PAGE) {
  mockApi({ GET: { '/api/auth/me': me, '/api/qc/log': page, '/api/qc/log/filters': FILTERS, '/api/qc/queue': QUEUE, '/api/qc/model-card': NO_MODEL } })
  return renderPage(<VisionModel />)
}
beforeEach(() => vi.clearAllMocks())

describe('Vision model photo log', () => {
  it('shows each photo with its order, batch, result and the inspector remark', async () => {
    setup()
    const card = (await screen.findByText('R-0002')).closest('article')!
    expect(within(card).getByText('Slub near the edge')).toBeInTheDocument()
    expect(within(card).getByText(/LOT-0001/)).toBeInTheDocument()
    expect(within(card).getAllByText('Rework').length).toBeGreaterThan(0)
    expect(within(card).getByText(/Model said pass/)).toBeInTheDocument()
    expect(within(card).getByRole('link', { name: 'ORD-0001' })).toHaveAttribute('href', '/orders/ORD-0001')
    expect(screen.getByText('R-0001').closest('article')).toHaveTextContent('No remark was written')
  })

  it('summarises the results and how often the inspector overrode the model', async () => {
    setup()
    await screen.findByText('R-0002')
    const kpi = (label: string) => screen.getByText(label).closest('.kpi')!
    expect(kpi('Photos checked')).toHaveTextContent('2')
    expect(kpi('Inspector overrode the model')).toHaveTextContent('1')
  })

  it('asks the server for the chosen order, batch, result and sort', async () => {
    setup()
    await screen.findByText('R-0002')
    await userEvent.selectOptions(screen.getByLabelText('Order'), 'ORD-0001')
    await userEvent.selectOptions(screen.getByLabelText('Batch (yarn lot)'), 'LOT-0001')
    await userEvent.selectOptions(screen.getByLabelText('Result'), 'reject')
    await userEvent.selectOptions(screen.getByLabelText('Sort by'), 'batch')
    const get = vi.mocked(api.GET)
    await waitFor(() => {
      const calls = get.mock.calls.filter((c) => c[0] === '/api/qc/log')
      const last = calls[calls.length - 1][1] as unknown as { params: { query: Record<string, unknown> } }
      expect(last.params.query).toMatchObject({ order: 'ORD-0001', lot: 'LOT-0001', verdict: 'reject', sort: 'batch' })
    })
  })

  it('opens a photo large, with the inspector and the remark', async () => {
    setup()
    await userEvent.click(await screen.findByRole('button', { name: 'View photo of R-0002' }))
    const dialog = await screen.findByRole('dialog')
    expect(within(dialog).getByText(/Checked by Asha/)).toBeInTheDocument()
    expect(within(dialog).getByText('Slub near the edge')).toBeInTheDocument()
  })

  it('says so when nothing matches', async () => {
    setup({ ...PAGE, items: [], counts: { total: 0, passed: 0, rework: 0, rejected: 0, overrode_ai: 0 } })
    expect(await screen.findByText('No photos match')).toBeInTheDocument()
  })

  it('lets the owner try the model on a photo when no roll is waiting, without saving anything', async () => {
    setup()
    await userEvent.click(await screen.findByRole('button', { name: /Check a photo/ }))
    const dialog = await screen.findByRole('dialog')
    expect(await within(dialog).findByText(/No rolls are waiting/)).toBeInTheDocument()
    expect(within(dialog).getByText(/Nothing is saved/)).toBeInTheDocument()
  })

  it('has a second tab for how accurate the model has been', async () => {
    setup()
    await userEvent.click(await screen.findByRole('tab', { name: 'Model metrics' }))
    expect(await screen.findByText(/no vision model has been evaluated yet/i)).toBeInTheDocument()
  })
})
