import { Copy, Sparkles } from 'lucide-react'
import { useState, type ReactNode } from 'react'
import { toast } from 'sonner'
import { Alert } from '@/components/common/Alert'
import { Button } from '@/components/ui/Button'
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

async function copy(text: string) {
  try {
    await navigator.clipboard.writeText(text)
    toast.success('Copied')
  } catch {
    toast.error('Could not copy. Select the text and copy it by hand.')
  }
}

function Draft({ text, sources, label }: { text: string; sources?: Source[]; label: string }) {
  return (
    <div className="ai-draft" role="group" aria-label={label}>
      <p className="ai-draft-text">{text}</p>
      <p className="muted text-sm">Written by the AI from the figures below. Read it before you use it.</p>
      <div className="row">
        <Button variant="secondary" onClick={() => void copy(text)}>
          <Copy size={14} aria-hidden /> Copy
        </Button>
      </div>
      {sources && sources.length > 0 && (
        <details className="chat-sources">
          <summary>Where this came from</summary>
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
  const d = useDraft(() => call(api.POST('/api/ai/explain-delay/{order_code}', { params: { path: { order_code: orderCode } } })))
  return (
    <div className="stack-sm">
      <Trigger pending={d.pending} onClick={() => void d.start()}>
        Explain this delay
      </Trigger>
      {d.error && <Alert tone="error">{d.error}</Alert>}
      {d.result && <Draft text={d.result.text} sources={d.result.sources} label={`Explanation for ${orderCode}`} />}
    </div>
  )
}

/** A short summary paragraph of the month, for the owner to read and copy. */
export function MonthSummary({ month }: { month: string }) {
  const d = useDraft(() => call(api.POST('/api/ai/month-summary', { body: { month } })))
  return (
    <div className="stack-sm">
      <Trigger pending={d.pending} onClick={() => void d.start()}>
        Write a summary of the month
      </Trigger>
      {d.error && <Alert tone="error">{d.error}</Alert>}
      {d.result && <Draft text={d.result.text} sources={d.result.sources} label="Summary of the month" />}
    </div>
  )
}

/** One message for each buyer who received rolls made from a blocked yarn lot. */
export function RecallDrafts({ lotCode }: { lotCode: string }) {
  const d = useDraft(() => call(api.POST('/api/ai/recall-drafts/{lot_code}', { params: { path: { lot_code: lotCode } } })))
  return (
    <div className="stack-sm">
      <Trigger pending={d.pending} onClick={() => void d.start()}>
        Draft messages to buyers
      </Trigger>
      {d.error && <Alert tone="error">{d.error}</Alert>}
      {d.result && d.result.drafts.length === 0 && <p className="muted text-sm">No buyer received rolls from this lot.</p>}
      {d.result?.drafts.map((x) => (
        <div key={x.buyer_name} className="stack-sm">
          <h3>{x.buyer_name}</h3>
          <Draft text={x.message} label={`Message to ${x.buyer_name}`} />
        </div>
      ))}
    </div>
  )
}
