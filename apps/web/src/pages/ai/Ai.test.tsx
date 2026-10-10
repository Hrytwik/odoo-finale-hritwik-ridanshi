import { fireEvent, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeEach, describe, expect, it, vi } from 'vitest'

vi.mock('@/lib/api/client', () => ({ api: { GET: vi.fn(), POST: vi.fn(), PUT: vi.fn(), PATCH: vi.fn(), DELETE: vi.fn() } }))
vi.mock('@/lib/auth', () => ({ useMe: () => ({ data: { role: 'owner' } }) }))
import { api } from '@/lib/api/client'
import { ExplainDelay, MonthSummary, RecallDrafts } from '@/components/ai/Drafts'
import { mockApi, renderPage } from '@/test/utils'
import AiSettings from './AiSettings'
import Copilot from './Copilot'
import ReportCard from './ReportCard'

const SOURCE = { tool: 'get_stock', input: { yarn: '30S-COT-RAW' }, summary: '30S-COT-RAW: 170 kg free of 212.5 kg' }
const CHAT = { answer: '170 kg of 30S-COT-RAW is free.', model: 'test-model', provider: 'openai_compatible', sources: [SOURCE] }
const SETTINGS = {
  provider: 'anthropic' as const,
  model: 'claude-opus-5-5',
  base_url: null,
  api_key_set: false,
  configured: false,
  supports_tools: true,
  supports_vision: false,
}

const post = vi.mocked(api.POST)
const put = vi.mocked(api.PUT)
beforeEach(() => {
  vi.clearAllMocks()
})

/** The mock table has no PUT, so route it the way mockApi routes the others. */
function mockWithPut(table: Parameters<typeof mockApi>[0], putReply: unknown) {
  mockApi(table)
  put.mockImplementation(() => Promise.resolve({ data: putReply, response: new Response(null, { status: 200 }) }) as never)
}

describe('Copilot page', () => {
  it('sends the question and shows the answer with where it came from', async () => {
    mockApi({ POST: { '/api/ai/copilot': CHAT } })
    renderPage(<Copilot />)
    await userEvent.type(screen.getByRole('textbox'), 'How much yarn is free?')
    await userEvent.click(screen.getByRole('button', { name: /ask/i }))
    expect(await screen.findByText('170 kg of 30S-COT-RAW is free.')).toBeInTheDocument()
    expect(post).toHaveBeenCalledWith('/api/ai/copilot', { body: { question: 'How much yarn is free?', history: [], language: 'English' } })
    expect(screen.getByText('Where this came from (1)')).toBeInTheDocument()
    expect(screen.getByText(SOURCE.summary)).toBeInTheDocument()
  })

  it('sends a suggested question when it is clicked', async () => {
    mockApi({ POST: { '/api/ai/copilot': CHAT } })
    renderPage(<Copilot />)
    await userEvent.click(screen.getByRole('button', { name: 'Which orders will be late?' }))
    await screen.findByText('170 kg of 30S-COT-RAW is free.')
    expect(post).toHaveBeenCalledWith('/api/ai/copilot', { body: { question: 'Which orders will be late?', history: [], language: 'English' } })
  })

  it('offers the month question to the owner', () => {
    mockApi({})
    renderPage(<Copilot />)
    expect(screen.getByRole('button', { name: 'How did we do this month?' })).toBeInTheDocument()
  })

  it('keeps the question in the box and says why when the model is not set up', async () => {
    mockApi({ POST: { '/api/ai/copilot': { status: 409, error: { code: 'AI_NOT_CONFIGURED', message: 'No AI model is set up yet. The owner can set one up under AI settings.', field: null, fields: null } } } })
    renderPage(<Copilot />)
    await userEvent.type(screen.getByRole('textbox'), 'Any late orders?')
    await userEvent.click(screen.getByRole('button', { name: /ask/i }))
    expect(await screen.findByText(/No AI model is set up yet/)).toBeInTheDocument()
    expect(screen.getByRole('textbox')).toHaveValue('Any late orders?')
    expect(screen.queryByRole('article')).not.toBeInTheDocument()
  })

  it('sends earlier turns as history on the next question', async () => {
    mockApi({ POST: { '/api/ai/copilot': CHAT } })
    renderPage(<Copilot />)
    await userEvent.type(screen.getByRole('textbox'), 'First')
    await userEvent.click(screen.getByRole('button', { name: /ask/i }))
    await screen.findByText('170 kg of 30S-COT-RAW is free.')
    await userEvent.type(screen.getByRole('textbox'), 'Second')
    await userEvent.click(screen.getByRole('button', { name: /ask/i }))
    await waitFor(() => expect(post).toHaveBeenCalledTimes(2))
    expect(post).toHaveBeenLastCalledWith('/api/ai/copilot', {
      body: {
        question: 'Second',
        language: 'English',
        history: [
          { role: 'user', text: 'First' },
          { role: 'assistant', text: '170 kg of 30S-COT-RAW is free.' },
        ],
      },
    })
  })
})

describe('AI settings', () => {
  it('says the model is not set up yet and disables the test', async () => {
    mockApi({ GET: { '/api/ai/settings': SETTINGS } })
    renderPage(<AiSettings />)
    expect(await screen.findByText('Not set up')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /send a test question/i })).toBeDisabled()
  })

  it('fills in the address and a matching model when Groq is picked', async () => {
    mockApi({ GET: { '/api/ai/settings': SETTINGS } })
    renderPage(<AiSettings />)
    await screen.findByText('Not set up')
    fireEvent.change(screen.getByLabelText('Provider'), { target: { value: 'openai_compatible' } })
    await userEvent.click(screen.getByRole('button', { name: 'Groq' }))
    expect(screen.getByLabelText('Address')).toHaveValue('https://api.groq.com/openai/v1')
    expect(screen.getByLabelText('Model')).toHaveValue('llama-3.3-70b-versatile')
  })

  it('does not overwrite a model name the user typed', async () => {
    mockApi({ GET: { '/api/ai/settings': { ...SETTINGS, provider: 'openai_compatible', model: 'my-own-model', base_url: 'http://x/v1' } } })
    renderPage(<AiSettings />)
    await screen.findByText('Not set up')
    await userEvent.click(screen.getByRole('button', { name: 'Groq' }))
    expect(screen.getByLabelText('Model')).toHaveValue('my-own-model')
  })

  it('saves the key and leaves the field empty afterwards', async () => {
    mockWithPut({ GET: { '/api/ai/settings': SETTINGS } }, { ...SETTINGS, configured: true, api_key_set: true })
    renderPage(<AiSettings />)
    await screen.findByText('Not set up')
    await userEvent.type(screen.getByLabelText('API key'), 'secret-key-value')
    await userEvent.click(screen.getByRole('button', { name: 'Save settings' }))
    await waitFor(() => expect(put).toHaveBeenCalled())
    expect(put.mock.calls[0][1]).toMatchObject({ body: { provider: 'anthropic', model: 'claude-opus-5-5', api_key: 'secret-key-value' } })
  })

  it('leaves the key out of the request when the field is empty, so the saved one is kept', async () => {
    mockWithPut({ GET: { '/api/ai/settings': { ...SETTINGS, api_key_set: true, configured: true } } }, SETTINGS)
    renderPage(<AiSettings />)
    await screen.findByText('Ready')
    await userEvent.click(screen.getByRole('button', { name: 'Save settings' }))
    await waitFor(() => expect(put).toHaveBeenCalled())
    expect((put.mock.calls[0][1] as { body: Record<string, unknown> }).body).not.toHaveProperty('api_key')
  })

  it('asks for the address when the provider is OpenAI-compatible and it is empty', async () => {
    mockWithPut({ GET: { '/api/ai/settings': { ...SETTINGS, provider: 'openai_compatible', model: 'llama' } } }, SETTINGS)
    renderPage(<AiSettings />)
    await screen.findByText('Not set up')
    await userEvent.click(screen.getByRole('button', { name: 'Save settings' }))
    expect(await screen.findByText('Enter the address of the provider')).toBeInTheDocument()
    expect(put).not.toHaveBeenCalled()
  })

  it('shows the answer of the test question', async () => {
    mockApi({ GET: { '/api/ai/settings': { ...SETTINGS, configured: true, api_key_set: true } }, POST: { '/api/ai/copilot': { ...CHAT, answer: 'OK' } } })
    renderPage(<AiSettings />)
    await screen.findByText('Ready')
    await userEvent.click(screen.getByRole('button', { name: /send a test question/i }))
    expect(await screen.findByText('test-model answered: OK')).toBeInTheDocument()
  })

  it('shows why the test failed', async () => {
    mockApi({
      GET: { '/api/ai/settings': { ...SETTINGS, configured: true, api_key_set: true } },
      POST: { '/api/ai/copilot': { status: 502, error: { code: 'AI_PROVIDER_ERROR', message: 'The provider refused the key.', field: null, fields: null } } },
    })
    renderPage(<AiSettings />)
    await screen.findByText('Ready')
    await userEvent.click(screen.getByRole('button', { name: /send a test question/i }))
    expect(await screen.findByText('The provider refused the key.')).toBeInTheDocument()
  })
})

describe('Report card page', () => {
  const RUN = {
    id: 3,
    provider: 'openai_compatible',
    model: 'llama-3.3-70b-versatile',
    run_at: '2026-10-10T10:00:00Z',
    score: 1,
    total: 2,
    details: [
      { question: 'How much 30S-COT-RAW is free?', expected: '170', answer: '170 kg is free.', passed: true },
      { question: 'How many orders are late?', expected: '2', answer: 'None.', passed: false },
    ],
  }

  it('says there are no runs yet', async () => {
    mockApi({ GET: { '/api/ai/report-card': [] } })
    renderPage(<ReportCard />)
    expect(await screen.findByText('No runs yet')).toBeInTheDocument()
  })

  it('marks each answer right or wrong against the figure the mill gives', async () => {
    mockApi({ GET: { '/api/ai/report-card': [RUN] } })
    renderPage(<ReportCard />)
    const panel = await screen.findByRole('region', { name: 'Answers from llama-3.3-70b-versatile' })
    expect(within(panel).getByText('1 wrong')).toBeInTheDocument()
    const rows = within(panel).getAllByRole('row')
    expect(rows[1]).toHaveTextContent('Right')
    expect(rows[2]).toHaveTextContent('Wrong')
    expect(rows[2]).toHaveTextContent('None.')
  })

  it('runs the report card and refreshes the list', async () => {
    let runs = [] as (typeof RUN)[]
    mockApi({
      GET: { '/api/ai/report-card': () => runs },
      POST: {
        '/api/ai/report-card/run': () => {
          runs = [RUN]
          return RUN
        },
      },
    })
    renderPage(<ReportCard />)
    await screen.findByText('No runs yet')
    await userEvent.click(screen.getByRole('button', { name: /run the report card/i }))
    expect(await screen.findByRole('region', { name: 'Answers from llama-3.3-70b-versatile' })).toBeInTheDocument()
  })

  it('shows why a run could not start', async () => {
    mockApi({
      GET: { '/api/ai/report-card': [] },
      POST: { '/api/ai/report-card/run': { status: 409, error: { code: 'AI_NOT_CONFIGURED', message: 'No AI model is set up yet.', field: null, fields: null } } },
    })
    renderPage(<ReportCard />)
    await screen.findByText('No runs yet')
    await userEvent.click(screen.getByRole('button', { name: /run the report card/i }))
    expect(await screen.findByText('No AI model is set up yet.')).toBeInTheDocument()
  })
})

describe('Drafts', () => {
  it('explains a delay and shows where the figures came from', async () => {
    mockApi({ POST: { '/api/ai/explain-delay/{order_code}': { text: 'ORD-0002 is late because weaving is slow.', model: 'm', provider: 'p', sources: [SOURCE] } } })
    renderPage(<ExplainDelay orderCode="ORD-0002" />)
    await userEvent.click(screen.getByRole('button', { name: /explain this delay/i }))
    const draft = await screen.findByRole('group', { name: 'Explanation for ORD-0002' })
    expect(draft).toHaveTextContent('ORD-0002 is late because weaving is slow.')
    expect(post).toHaveBeenCalledWith('/api/ai/explain-delay/{order_code}', { params: { path: { order_code: 'ORD-0002' } } })
    expect(within(draft).getByText('Where this came from')).toBeInTheDocument()
  })

  it('asks for the month it is given', async () => {
    mockApi({ POST: { '/api/ai/month-summary': { text: 'A profitable month.', model: 'm', provider: 'p', sources: [] } } })
    renderPage(<MonthSummary month="2026-10" />)
    await userEvent.click(screen.getByRole('button', { name: /write a summary of the month/i }))
    expect(await screen.findByText('A profitable month.')).toBeInTheDocument()
    expect(post).toHaveBeenCalledWith('/api/ai/month-summary', { body: { month: '2026-10' } })
  })

  it('shows one message for each buyer', async () => {
    mockApi({
      POST: {
        '/api/ai/recall-drafts/{lot_code}': {
          drafts: [
            { buyer_name: 'Sharma Fabrics', message: 'Please hold roll R-0001.' },
            { buyer_name: 'Lotus Apparel', message: 'Please hold roll R-0002.' },
          ],
          model: 'm',
          provider: 'p',
          sources: [],
        },
      },
    })
    renderPage(<RecallDrafts lotCode="L-0001" />)
    await userEvent.click(screen.getByRole('button', { name: /draft messages to buyers/i }))
    expect(await screen.findByRole('group', { name: 'Message to Sharma Fabrics' })).toHaveTextContent('Please hold roll R-0001.')
    expect(screen.getByRole('group', { name: 'Message to Lotus Apparel' })).toBeInTheDocument()
  })

  it('says so when no buyer received rolls from the lot', async () => {
    mockApi({ POST: { '/api/ai/recall-drafts/{lot_code}': { drafts: [], model: 'm', provider: 'p', sources: [] } } })
    renderPage(<RecallDrafts lotCode="L-0001" />)
    await userEvent.click(screen.getByRole('button', { name: /draft messages to buyers/i }))
    expect(await screen.findByText('No buyer received rolls from this lot.')).toBeInTheDocument()
  })

  it('shows the reason when the model cannot be reached', async () => {
    mockApi({ POST: { '/api/ai/month-summary': { status: 502, error: { code: 'AI_PROVIDER_ERROR', message: 'The provider could not be reached.', field: null, fields: null } } } })
    renderPage(<MonthSummary month="2026-10" />)
    await userEvent.click(screen.getByRole('button', { name: /write a summary of the month/i }))
    expect(await screen.findByText('The provider could not be reached.')).toBeInTheDocument()
  })
})


describe('settings: address check and model list', () => {
  it('refuses a website page where the API address belongs, and says what to do', async () => {
    mockWithPut({ GET: { '/api/ai/settings': { ...SETTINGS, provider: 'openai_compatible', model: 'm', base_url: 'https://console.groq.com/keys' } } }, SETTINGS)
    renderPage(<AiSettings />)
    await screen.findByText('Not set up')
    await userEvent.click(screen.getByRole('button', { name: 'Save settings' }))
    expect(await screen.findByText(/website page, not the API address/)).toBeInTheDocument()
    expect(put).not.toHaveBeenCalled()
  })

  it('lists the models the key can use and puts the chosen one in the model box', async () => {
    mockApi({ GET: { '/api/ai/settings': { ...SETTINGS, configured: true, api_key_set: true }, '/api/ai/models': { models: ['openai/gpt-oss-120b', 'qwen/qwen3.8-27b'] } } })
    renderPage(<AiSettings />)
    await screen.findByText('Ready')
    await userEvent.click(screen.getByRole('button', { name: /show the models my key can use/i }))
    await userEvent.click(await screen.findByRole('button', { name: 'openai/gpt-oss-120b' }))
    expect(screen.getByLabelText('Model')).toHaveValue('openai/gpt-oss-120b')
  })

  it('asks for a key before it can list models', async () => {
    mockApi({ GET: { '/api/ai/settings': SETTINGS } })
    renderPage(<AiSettings />)
    await screen.findByText('Not set up')
    expect(screen.getByRole('button', { name: /show the models my key can use/i })).toBeDisabled()
  })

  it('shows why the list could not be fetched', async () => {
    mockApi({
      GET: {
        '/api/ai/settings': { ...SETTINGS, configured: true, api_key_set: true },
        '/api/ai/models': { status: 503, error: { code: 'AI_UNAVAILABLE', message: 'The provider refused the API key', field: null, fields: null } },
      },
    })
    renderPage(<AiSettings />)
    await screen.findByText('Ready')
    await userEvent.click(screen.getByRole('button', { name: /show the models my key can use/i }))
    expect(await screen.findByText(/refused the API key/)).toBeInTheDocument()
  })
})

describe('chat text', () => {
  it('shows bold words and bullet lines instead of the raw marks', async () => {
    mockApi({ POST: { '/api/ai/copilot': { ...CHAT, answer: 'Stock:' + String.fromCharCode(10) + '- **30s cotton**: 170 kg' + String.fromCharCode(10) + '- 40s: 950 kg' } } })
    renderPage(<Copilot />)
    await userEvent.click(screen.getByRole('button', { name: 'How much yarn is free right now?' }))
    const strong = await screen.findByText('30s cotton')
    expect(strong.tagName).toBe('STRONG')
    expect(document.querySelectorAll('.chat-list li')).toHaveLength(2)
    expect(screen.queryByText(/[*][*]/)).not.toBeInTheDocument()
  })
})

describe('chat tables', () => {
  it('shows a table the model wrote as a table', async () => {
    const nl = String.fromCharCode(10)
    const answer = ['Workers', '| Code | Name |', '|------|------|', '| W-001 | Ravi Kumar |', '| W-002 | Meena Devi |'].join(nl)
    mockApi({ POST: { '/api/ai/copilot': { ...CHAT, answer } } })
    renderPage(<Copilot />)
    await userEvent.click(screen.getByRole('button', { name: 'Which orders will be late?' }))
    const table = await screen.findByRole('table')
    expect(within(table).getAllByRole('columnheader').map((h) => h.textContent)).toEqual(['Code', 'Name'])
    expect(within(table).getAllByRole('row')).toHaveLength(3)
    expect(screen.queryByText(/[|]---/)).not.toBeInTheDocument()
  })
})
