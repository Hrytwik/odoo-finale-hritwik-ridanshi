import { useQuery, useQueryClient } from '@tanstack/react-query'
import { CheckCircle2, PlugZap } from 'lucide-react'
import { useState } from 'react'
import { Link } from 'react-router-dom'
import { toast } from 'sonner'
import { Alert } from '@/components/common/Alert'
import { PageHeader } from '@/components/common/PageHeader'
import { QueryBoundary } from '@/components/common/QueryBoundary'
import { SubmitButton } from '@/components/common/SubmitButton'
import { Badge } from '@/components/ui/Badge'
import { Button } from '@/components/ui/Button'
import { Field, Input, Select } from '@/components/ui/Field'
import { ApiError, api, call, errorMessage, type components } from '@/lib/api'
import { useSubmitLock } from '@/lib/forms'

type Settings = components['schemas']['SettingsOut']

/** Starting points for the address of an OpenAI-compatible provider. */
const PRESETS = [
  { label: 'Groq', url: 'https://api.groq.com/openai/v1' },
  { label: 'OpenAI', url: 'https://api.openai.com/v1' },
  { label: 'Ollama on this computer', url: 'http://localhost:11434/v1' },
]

export default function AiSettings() {
  const settings = useQuery({ queryKey: ['ai', 'settings'], queryFn: () => call(api.GET('/api/ai/settings')) })
  return (
    <>
      <PageHeader
        eyebrow="AI"
        title="AI settings"
        description="Choose which language model answers questions. The mill works the same without it: every number screen keeps working."
        actions={
          <Link to="/settings/ai/report-card">
            <Button variant="secondary">Report card</Button>
          </Link>
        }
      />
      <QueryBoundary query={settings}>{(s) => <SettingsForm key={`${s.provider}-${s.model}-${s.base_url}-${s.api_key_set}`} current={s} />}</QueryBoundary>
    </>
  )
}

function SettingsForm({ current }: { current: Settings }) {
  const queryClient = useQueryClient()
  const { run, pending } = useSubmitLock()
  const [provider, setProvider] = useState<Settings['provider']>(current.provider)
  const [model, setModel] = useState(current.model)
  const [baseUrl, setBaseUrl] = useState(current.base_url ?? '')
  const [apiKey, setApiKey] = useState('')
  const [removeKey, setRemoveKey] = useState(false)
  const [tools, setTools] = useState(current.supports_tools)
  const [vision, setVision] = useState(current.supports_vision)
  const [errors, setErrors] = useState<Record<string, string>>({})
  const [formError, setFormError] = useState<string | null>(null)

  const save = () =>
    run(async () => {
      const found: Record<string, string> = {}
      if (!model.trim()) found.model = 'Enter the model name'
      if (provider === 'openai_compatible' && !baseUrl.trim()) found.base_url = 'Enter the address of the provider'
      setErrors(found)
      setFormError(null)
      if (Object.keys(found).length) return
      try {
        await call(
          api.PUT('/api/ai/settings', {
            body: {
              provider,
              model: model.trim(),
              base_url: baseUrl.trim() || null,
              // empty means "remove it"; leaving the field out means "keep the saved one"
              ...(removeKey ? { api_key: '' } : apiKey.trim() ? { api_key: apiKey.trim() } : {}),
              supports_tools: tools,
              supports_vision: vision,
            },
          }),
        )
        toast.success('AI settings saved')
        setApiKey('')
        setRemoveKey(false)
        await queryClient.invalidateQueries({ queryKey: ['ai'] })
      } catch (err) {
        const placed: Record<string, string> = {}
        if (err instanceof ApiError) {
          const names: Record<string, string> = { model: 'model', base_url: 'base_url', provider: 'provider', api_key: 'api_key' }
          for (const [name, message] of Object.entries(err.fields ?? (err.field ? { [err.field]: err.body.message } : {}))) if (names[name]) placed[names[name]] = message
        }
        if (Object.keys(placed).length) setErrors(placed)
        else setFormError(errorMessage(err))
      }
    })

  return (
    <div className="stack">
      <p className="row">
        {current.configured ? <Badge tone="green">Ready</Badge> : <Badge tone="amber">Not set up</Badge>}
        <span className="muted text-sm">
          {current.configured ? `Using ${current.model}` : 'Enter a key, or the address of a local model, then save.'}
        </span>
      </p>
      <form
        className="card"
        noValidate
        onSubmit={(e) => {
          e.preventDefault()
          void save()
        }}
      >
        <div className="card-body stack">
          <Field label="Provider" error={errors.provider}>
            {(c) => (
              <Select {...c} value={provider} onChange={(e) => setProvider(e.target.value as Settings['provider'])}>
                <option value="anthropic">Anthropic (Claude)</option>
                <option value="openai_compatible">OpenAI-compatible (OpenAI, Groq, OpenRouter, Ollama, LM Studio)</option>
              </Select>
            )}
          </Field>
          <Field label="Model" error={errors.model} hint={provider === 'anthropic' ? 'For example claude-opus-5-5' : 'The exact name the provider uses, for example llama-3.3-70b-versatile'}>
            {(c) => <Input {...c} autoComplete="off" value={model} onChange={(e) => setModel(e.target.value)} />}
          </Field>
          {provider === 'openai_compatible' && (
            <Field label="Address" error={errors.base_url} hint="The provider's base address, ending in /v1">
              {(c) => (
                <>
                  <Input {...c} autoComplete="off" value={baseUrl} onChange={(e) => setBaseUrl(e.target.value)} />
                  <span className="row">
                    {PRESETS.map((p) => (
                      <button key={p.label} type="button" className="chat-chip" onClick={() => setBaseUrl(p.url)}>
                        {p.label}
                      </button>
                    ))}
                  </span>
                </>
              )}
            </Field>
          )}
          <Field
            label="API key"
            error={errors.api_key}
            hint={current.api_key_set ? 'A key is saved. Leave this empty to keep it. It is stored encrypted and is never shown again.' : provider === 'openai_compatible' ? 'Leave empty for a local model.' : 'It is stored encrypted and is never shown again.'}
          >
            {(c) => <Input {...c} type="password" autoComplete="new-password" placeholder={current.api_key_set ? 'Saved' : ''} value={apiKey} disabled={removeKey} onChange={(e) => setApiKey(e.target.value)} />}
          </Field>
          {current.api_key_set && (
            <label className="check-row">
              <input type="checkbox" checked={removeKey} onChange={(e) => setRemoveKey(e.target.checked)} /> Remove the saved key
            </label>
          )}
          <fieldset className="recipe">
            <legend>What this model can do</legend>
            <label className="check-row">
              <input type="checkbox" checked={tools} onChange={(e) => setTools(e.target.checked)} /> It can call tools (needed for the copilot and the buyer assistant)
            </label>
            <label className="check-row">
              <input type="checkbox" checked={vision} onChange={(e) => setVision(e.target.checked)} /> It can read images
            </label>
          </fieldset>
          {formError && <Alert tone="error">{formError}</Alert>}
          <div className="row">
            <SubmitButton pending={pending}>Save settings</SubmitButton>
          </div>
        </div>
      </form>
      <TestConnection disabled={!current.configured} />
    </div>
  )
}

function TestConnection({ disabled }: { disabled: boolean }) {
  const { run, pending } = useSubmitLock()
  const [result, setResult] = useState<{ ok: boolean; text: string } | null>(null)
  const test = () =>
    run(async () => {
      setResult(null)
      try {
        const r = await call(api.POST('/api/ai/copilot', { body: { question: 'Reply with the single word OK.', history: [] } }))
        setResult({ ok: true, text: `${r.model} answered: ${r.answer}` })
      } catch (err) {
        setResult({ ok: false, text: errorMessage(err) })
      }
    })
  return (
    <section className="card" aria-label="Test the connection">
      <div className="card-body stack-sm">
        <h2 className="card-title">Test the connection</h2>
        <p className="muted text-sm">Sends one short question to the saved provider. Save your changes first.</p>
        <div className="row">
          <Button variant="secondary" onClick={() => void test()} disabled={disabled || pending}>
            {pending ? <span className="spinner" aria-hidden /> : <PlugZap size={16} aria-hidden />} Send a test question
          </Button>
        </div>
        {result &&
          (result.ok ? (
            <p role="status" className="row">
              <CheckCircle2 size={16} aria-hidden /> {result.text}
            </p>
          ) : (
            <Alert tone="error">{result.text}</Alert>
          ))}
      </div>
    </section>
  )
}
