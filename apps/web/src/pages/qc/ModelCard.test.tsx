import { screen, within } from '@testing-library/react'
import { beforeEach, describe, expect, it, vi } from 'vitest'

vi.mock('@/lib/api/client', () => ({ api: { GET: vi.fn(), POST: vi.fn(), PATCH: vi.fn(), DELETE: vi.fn() } }))
import { mockApi, renderPage } from '@/test/utils'
import ModelCard from './ModelCard'

const NONE = { available: false, model_version: null, trained_at: null, datasets: [], test_defective: 0, test_clean: 0, clean_false_alarm_rate: null, per_class: [], confusion_labels: [], confusion_matrix: [] }
const GOOD = {
  available: true, model_version: 'yolo-v1', trained_at: '2026-10-12T09:00:00Z', test_defective: 40, test_clean: 35, clean_false_alarm_rate: 0.11,
  per_class: [
    { defect_type: 'hole', found: 34, missed: 6, false_alarms: 4, precision: 0.894, recall: 0.85 },
    { defect_type: 'stain', found: 20, missed: 10, false_alarms: 2, precision: 0.909, recall: 0.667 },
    { defect_type: 'thread_fault', found: 0, missed: 0, false_alarms: 0, precision: null, recall: null },
  ],
  confusion_labels: ['hole', 'stain', 'clean'], confusion_matrix: [[34, 1, 5], [2, 20, 8], [4, 2, 29]],
  datasets: [
    { name: 'Roboflow Fabric Defect Detection Subset', url: 'https://universe.roboflow.com/x/y', licence: 'CC BY 4.0' },
    { name: 'Our own cloth photos', url: 'javascript:alert(1)', licence: 'Own work' },
  ],
}
const WEAK = { ...GOOD, clean_false_alarm_rate: 0.3, per_class: [{ ...GOOD.per_class[0], recall: 0.6 }, ...GOOD.per_class.slice(1)] }

beforeEach(() => {
  vi.clearAllMocks()
})

describe('ModelCard when there is no model yet', () => {
  it('says so honestly, and that checking works without it', async () => {
    mockApi({ GET: { '/api/qc/model-card': NONE } })
    renderPage(<ModelCard />)
    expect(await screen.findByText(/no vision model has been evaluated yet/i)).toBeInTheDocument()
    expect(screen.getByText(/works fully without it/i)).toBeInTheDocument()
    expect(screen.queryByRole('table')).not.toBeInTheDocument()
  })
})

describe('ModelCard with a model', () => {
  it('shows the version and the size of the held-out test set', async () => {
    mockApi({ GET: { '/api/qc/model-card': GOOD } })
    renderPage(<ModelCard />)
    expect(await screen.findByText('yolo-v1')).toBeInTheDocument()
    expect(screen.getByText(/40 defective/i)).toBeInTheDocument()
    expect(screen.getByText(/35 clean/i)).toBeInTheDocument()
    expect(screen.getByText(/never seen in training/i)).toBeInTheDocument()
  })

  it('shows found, missed and false alarms per defect type, with percentages', async () => {
    mockApi({ GET: { '/api/qc/model-card': GOOD } })
    renderPage(<ModelCard />)
    const rows = await screen.findAllByRole('table')
    const perClass = rows[0]
    const hole = within(perClass).getByRole('row', { name: /hole/i })
    expect(hole).toHaveTextContent('34')
    expect(hole).toHaveTextContent('6')
    expect(hole).toHaveTextContent('85%')
    expect(hole).toHaveTextContent('89%')
    expect(within(perClass).getByRole('row', { name: /stain/i })).toHaveTextContent('67%')
  })

  it('shows a dash, not 0%, when a class was not tested', async () => {
    mockApi({ GET: { '/api/qc/model-card': GOOD } })
    renderPage(<ModelCard />)
    const perClass = (await screen.findAllByRole('table'))[0]
    expect(within(within(perClass).getByRole('row', { name: /thread fault/i })).getAllByText('-').length).toBe(2)
  })

  it('shows how often clean cloth was wrongly flagged', async () => {
    mockApi({ GET: { '/api/qc/model-card': GOOD } })
    renderPage(<ModelCard />)
    await screen.findByText('yolo-v1')
    expect(screen.getByText('False alarms on clean cloth').closest('.kpi')).toHaveTextContent('11%')
  })

  it('draws the confusion matrix with its labels', async () => {
    mockApi({ GET: { '/api/qc/model-card': GOOD } })
    renderPage(<ModelCard />)
    const matrix = (await screen.findAllByRole('table'))[1]
    expect(within(matrix).getAllByText('clean').length).toBeGreaterThan(0)
    // the first cell of each data row names the real defect; the numbers after it are what the model said
    expect(within(matrix).getByRole('rowheader', { name: 'hole' }).closest('tr')).toHaveTextContent('34')
    expect(within(matrix).getByRole('rowheader', { name: 'stain' }).closest('tr')).toHaveTextContent('20')
  })

  it('credits every dataset with its licence, and only links to web addresses', async () => {
    mockApi({ GET: { '/api/qc/model-card': GOOD } })
    renderPage(<ModelCard />)
    const link = await screen.findByRole('link', { name: /roboflow fabric defect detection subset/i })
    expect(link).toHaveAttribute('href', 'https://universe.roboflow.com/x/y')
    expect(link).toHaveAttribute('rel', expect.stringContaining('noopener'))
    expect(screen.getByText(/CC BY 4\.0/)).toBeInTheDocument()
    // an unsafe address is shown as text, never as a link
    expect(screen.queryByRole('link', { name: /our own cloth photos/i })).not.toBeInTheDocument()
    expect(screen.getByText(/our own cloth photos/i)).toBeInTheDocument()
  })
})

describe('ModelCard: does it meet the bar from the spec?', () => {
  it('says the model is good enough to be a headline feature when it clears both bars', async () => {
    mockApi({ GET: { '/api/qc/model-card': GOOD } })
    renderPage(<ModelCard />)
    expect(await screen.findByText(/meets the bar/i)).toBeInTheDocument()
  })

  it('says it is only a supporting feature when holes are found too rarely or false alarms are too common', async () => {
    mockApi({ GET: { '/api/qc/model-card': WEAK } })
    renderPage(<ModelCard />)
    expect(await screen.findByText(/below the bar/i)).toBeInTheDocument()
  })
})

describe('ModelCard: errors', () => {
  it('shows a Retry state when the card cannot be loaded', async () => {
    mockApi({ GET: { '/api/qc/model-card': { status: 500, error: 'boom' } } })
    renderPage(<ModelCard />)
    expect(await screen.findByRole('alert')).toHaveTextContent(/something went wrong/i)
    expect(screen.getByRole('button', { name: /retry/i })).toBeInTheDocument()
  })
})
