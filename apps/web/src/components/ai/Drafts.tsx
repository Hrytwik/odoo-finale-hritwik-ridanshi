import { Copy, Sparkles } from 'lucide-react'
import { useState, type ReactNode } from 'react'
import { toast } from 'sonner'
import { Alert } from '@/components/common/Alert'
import { Button } from '@/components/ui/Button'
import { useI18n } from '@/i18n/I18nContext'
import { api, call, errorMessage, type components } from '@/lib/api'
import { useSubmitLock } from '@/lib/forms'

type Source = components['schemas']['SourceOut']

/** Runs one request for words, once at a time, and keeps either the words or the reason it failed. */
function useDraft<T>(request: () => Promise<T>) {
  const { run, pending } = useSubmitLock()
  const [result, setResult] = useState<T | null>(null)
  const [error, setError] = useState<string | null>(null)
  const start = () =>
    run(async () => {
      setError(null)
      try {
        setResult(await request())
      } catch (err) {
        setError(errorMessage(err))
      }
    })
  return { start, pending, result, error }
}

async function copy(text: string, done: string, failed: string) {
  try {
    await navigator.clipboard.writeText(text)
    toast.success(done)
  } catch {
    toast.error(failed)
  }
}

function Draft({ text, sources, label }: { text: string; sources?: Source[]; label: string }) {
  const { t } = useI18n()
  return (
    <div className="ai-draft" role="group" aria-label={label}>
      <p className="ai-draft-text">{text}</p>
      <p className="muted text-sm">{t('draft.byAi')}</p>
      <div className="row">
        <Button variant="secondary" onClick={() => void copy(text, t('draft.copied'), t('draft.copyFailed'))}>
          <Copy size={14} aria-hidden /> {t('draft.copy')}
        </Button>
      </div>
      {sources && sources.length > 0 && (
        <details className="chat-sources">
          <summary>{t('draft.cameFrom')}</summary>
          <div className="chat-source-summary">{sources.map((s) => s.summary).join(' ')}</div>
        </details>
      )}
    </div>
  )
}

function Trigger({ pending, onClick, children }: { pending: boolean; onClick: () => void; children: ReactNode }) {
  return (
    <Button variant="secondary" onClick={onClick} disabled={pending}>
      {pending ? <span className="spinner" aria-hidden /> : <Sparkles size={14} aria-hidden />} {children}
    </Button>
  )
}

/** Words the delivery estimate of a late order and the two what-ifs the mill tested. */
export function ExplainDelay({ orderCode }: { orderCode: string }) {
  const { t } = useI18n()
  const d = useDraft(() => call(api.POST('/api/ai/explain-delay/{order_code}', { params: { path: { order_code: orderCode } } })))
  return (
    <div className="stack-sm">
      <Trigger pending={d.pending} onClick={() => void d.start()}>
        {t('draft.explainDelay')}
      </Trigger>
      {d.error && <Alert tone="error">{d.error}</Alert>}
      {d.result && <Draft text={d.result.text} sources={d.result.sources} label={t('draft.explanationFor', { code: orderCode })} />}
    </div>
  )
}

/** A short summary paragraph of the month, for the owner to read and copy. */
export function MonthSummary({ month }: { month: string }) {
  const { t, language } = useI18n()
  const d = useDraft(() => call(api.POST('/api/ai/month-summary', { body: { month, language: language.english as components['schemas']['MonthIn']['language'] } })))
  return (
    <div className="stack-sm">
      <Trigger pending={d.pending} onClick={() => void d.start()}>
        {t('draft.monthSummary')}
      </Trigger>
      {d.error && <Alert tone="error">{d.error}</Alert>}
      {d.result && <Draft text={d.result.text} sources={d.result.sources} label={t('draft.monthLabel')} />}
    </div>
  )
}

/** One message for each buyer who received rolls made from a blocked yarn lot. */
export function RecallDrafts({ lotCode }: { lotCode: string }) {
  const { t } = useI18n()
  const d = useDraft(() => call(api.POST('/api/ai/recall-drafts/{lot_code}', { params: { path: { lot_code: lotCode } } })))
  return (
    <div className="stack-sm">
      <Trigger pending={d.pending} onClick={() => void d.start()}>
        {t('draft.recall')}
      </Trigger>
      {d.error && <Alert tone="error">{d.error}</Alert>}
      {d.result && d.result.drafts.length === 0 && <p className="muted text-sm">{t('draft.noBuyers')}</p>}
      {d.result?.drafts.map((x) => (
        <div key={x.buyer_name} className="stack-sm">
          <h3>{x.buyer_name}</h3>
          <Draft text={x.message} label={t('draft.messageTo', { name: x.buyer_name })} />
        </div>
      ))}
    </div>
  )
}
