import { useQuery, useQueryClient } from '@tanstack/react-query'
import { CheckCircle2, ListChecks, PlugZap } from 'lucide-react'
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
import { addressProblem } from '@/lib/aiAddress'
import { useI18n } from '@/i18n/I18nContext'
import { useSubmitLock } from '@/lib/forms'

type Settings = components['schemas']['SettingsOut']

/** Starting points for the address of an OpenAI-compatible provider. */
const PRESETS = [
  { label: 'Groq', url: 'https://api.groq.com/openai/v1', model: 'llama-3.3-70b-versatile' },
  { label: 'OpenAI', url: 'https://api.openai.com/v1', model: 'gpt-4o-mini' },
  { label: 'ollama', url: 'http://localhost:11434/v1', model: 'llama3.1' },
]

/** True while the model box still holds a name that belongs to a different provider than the chosen preset. */
const isStarterModel = (model: string) => !model.trim() || model.startsWith('claude-') || PRESETS.some((p) => p.model === model)

export default function AiSettings() {
  const { t } = useI18n()
  const settings = useQuery({ queryKey: ['ai', 'settings'], queryFn: () => call(api.GET('/api/ai/settings')) })
  return (
    <>
      <PageHeader
        eyebrow="AI"
        title={t('nav.aiSettings')}
        description={t('aiset.description')}
        actions={
          <Link to="/settings/ai/report-card">
            <Button variant="secondary">{t('aiset.reportCard')}</Button>
          </Link>
        }
      />
      <QueryBoundary query={settings}>{(s) => <SettingsForm key={`${s.provider}-${s.model}-${s.base_url}-${s.api_key_set}`} current={s} />}</QueryBoundary>
    </>
  )
}

function SettingsForm({ current }: { current: Settings }) {
  const { t } = useI18n()
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
      if (!model.trim()) found.model = t('aiset.enterModel')
      if (provider === 'openai_compatible') {
        const problem = addressProblem(baseUrl)
        if (problem) found.base_url = t(problem)
      }
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
        toast.success(t('aiset.savedToast'))
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
        {current.configured ? <Badge tone="green">{t('aiset.ready')}</Badge> : <Badge tone="amber">{t('aiset.notSetUp')}</Badge>}
        <span className="muted text-sm">
          {current.configured ? t('aiset.using', { model: current.model }) : t('aiset.enterKey')}
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
          <Field label={t('aiset.provider')} error={errors.provider}>
            {(c) => (
              <Select {...c} value={provider} onChange={(e) => setProvider(e.target.value as Settings['provider'])}>
                <option value="anthropic">Anthropic (Claude)</option>
                <option value="openai_compatible">OpenAI-compatible (OpenAI, Groq, OpenRouter, Ollama, LM Studio)</option>
              </Select>
            )}
          </Field>
          <Field label={t('aiset.model')} error={errors.model} hint={provider === 'anthropic' ? t('aiset.modelHintAnthropic') : t('aiset.modelHintOther')}>
            {(c) => (
              <>
                <Input {...c} autoComplete="off" value={model} onChange={(e) => setModel(e.target.value)} />
                <ModelPicker enabled={current.configured} onPick={setModel} />
              </>
            )}
          </Field>
          {provider === 'openai_compatible' && (
            <Field label={t('aiset.address')} error={errors.base_url} hint={t('aiset.addressHint')}>
              {(c) => (
                <>
                  <Input {...c} autoComplete="off" value={baseUrl} onChange={(e) => setBaseUrl(e.target.value)} />
                  <span className="row">
                    {PRESETS.map((p) => (
                      <button
                        key={p.label}
                        type="button"
                        className="chat-chip"
                        onClick={() => {
                          setBaseUrl(p.url)
                          // fill in a matching model name, but never overwrite one the user typed
                          if (isStarterModel(model)) setModel(p.model)
                        }}
                      >
                        {p.label === 'ollama' ? t('aiset.presetOllama') : p.label}
                      </button>
                    ))}
                  </span>
                </>
              )}
            </Field>
          )}
          <Field
            label={t('aiset.apiKey')}
            error={errors.api_key}
            hint={current.api_key_set ? t('aiset.keyHintSaved') : provider === 'openai_compatible' ? t('aiset.keyHintLocal') : t('aiset.keyHintNew')}
          >
            {(c) => <Input {...c} type="password" autoComplete="new-password" placeholder={current.api_key_set ? t('aiset.saved') : ''} value={apiKey} disabled={removeKey} onChange={(e) => setApiKey(e.target.value)} />}
          </Field>
          {current.api_key_set && (
            <label className="check-row">
              <input type="checkbox" checked={removeKey} onChange={(e) => setRemoveKey(e.target.checked)} /> {t('aiset.removeKey')}
            </label>
          )}
          <fieldset className="recipe">
            <legend>{t('aiset.canDo')}</legend>
            <label className="check-row">
              <input type="checkbox" checked={tools} onChange={(e) => setTools(e.target.checked)} /> {t('aiset.canTools')}
            </label>
            <label className="check-row">
              <input type="checkbox" checked={vision} onChange={(e) => setVision(e.target.checked)} /> {t('aiset.canImages')}
            </label>
          </fieldset>
          {formError && <Alert tone="error">{formError}</Alert>}
          <div className="row">
            <SubmitButton pending={pending}>{t('aiset.save')}</SubmitButton>
          </div>
        </div>
      </form>
      <TestConnection disabled={!current.configured} />
    </div>
  )
}

/** Asks the saved provider which models the saved key may use, so the model name is one that exists. */
function ModelPicker({ enabled, onPick }: { enabled: boolean; onPick: (model: string) => void }) {
  const { t } = useI18n()
  const { run, pending } = useSubmitLock()
  const [models, setModels] = useState<string[] | null>(null)
  const [error, setError] = useState<string | null>(null)
  const load = () =>
    run(async () => {
      setError(null)
      try {
        setModels((await call(api.GET('/api/ai/models'))).models)
      } catch (err) {
        setModels(null)
        setError(errorMessage(err))
      }
    })
  return (
    <div className="stack-sm">
      <span className="row">
        <Button variant="secondary" onClick={() => void load()} disabled={!enabled || pending}>
          {pending ? <span className="spinner" aria-hidden /> : <ListChecks size={16} aria-hidden />} {t('aiset.showModels')}
        </Button>
        {!enabled && <span className="muted text-sm">{t('aiset.saveKeyFirst')}</span>}
      </span>
      {error && <Alert tone="error">{error}</Alert>}
      {models && models.length === 0 && <p className="muted text-sm">{t('aiset.noModels')}</p>}
      {models && models.length > 0 && (
        <span className="row" role="group" aria-label={t('aiset.modelsAria')}>
          {models.map((m) => (
            <button key={m} type="button" className="chat-chip" onClick={() => onPick(m)}>
              {m}
            </button>
          ))}
        </span>
      )}
    </div>
  )
}

function TestConnection({ disabled }: { disabled: boolean }) {
  const { t } = useI18n()
  const { run, pending } = useSubmitLock()
  const [result, setResult] = useState<{ ok: boolean; text: string } | null>(null)
  const test = () =>
    run(async () => {
      setResult(null)
      try {
        const r = await call(api.POST('/api/ai/copilot', { body: { question: 'Reply with the single word OK.', history: [], language: 'English' } }))
        setResult({ ok: true, text: t('aiset.answered', { model: r.model, answer: r.answer }) })
      } catch (err) {
        setResult({ ok: false, text: errorMessage(err) })
      }
    })
  return (
    <section className="card" aria-label={t('aiset.test')}>
      <div className="card-body stack-sm">
        <h2 className="card-title">{t('aiset.test')}</h2>
        <p className="muted text-sm">{t('aiset.testHint')}</p>
        <div className="row">
          <Button variant="secondary" onClick={() => void test()} disabled={disabled || pending}>
            {pending ? <span className="spinner" aria-hidden /> : <PlugZap size={16} aria-hidden />} {t('aiset.sendTest')}
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
