import { Bot, Send, Sparkles, User } from 'lucide-react'
import { useEffect, useRef, useState } from 'react'
import { Alert } from '@/components/common/Alert'
import { Button } from '@/components/ui/Button'
import { type components, errorMessage } from '@/lib/api'
import { useSubmitLock } from '@/lib/forms'

type Chat = components['schemas']['ChatOut']
type Source = components['schemas']['SourceOut']
type Message = { role: 'user' | 'assistant'; text: string; sources?: Source[] }

/** Plain names for the tools the model calls, for the "where this came from" list. */
const TOOL_LABEL: Record<string, string> = {
  get_order_status: 'Order status',
  get_order_cost: 'Order cost',
  get_month_summary: 'Month summary',
  get_machine_utilisation: 'Machine use',
  get_late_orders: 'Late orders',
  get_shortage_forecast: 'Yarn shortages',
  get_defect_root_causes: 'Defect causes',
  get_stock: 'Yarn stock',
  get_my_orders: 'Your orders',
  get_my_order_status: 'Your order',
  get_my_order_eta: 'Delivery date',
}

/**
 * A conversation with the mill's assistant. The model only words what the mill's own functions return, so each answer
 * lists exactly which ones were asked and what they said.
 */
export function ChatPanel({
  send,
  suggestions,
  placeholder,
  label,
}: {
  send: (question: string, history: { role: 'user' | 'assistant'; text: string }[]) => Promise<Chat>
  suggestions: string[]
  placeholder: string
  label: string
}) {
  const [messages, setMessages] = useState<Message[]>([])
  const [text, setText] = useState('')
  const [error, setError] = useState<string | null>(null)
  const { run, pending } = useSubmitLock()
  const end = useRef<HTMLDivElement>(null)

  useEffect(() => {
    end.current?.scrollIntoView?.({ block: 'end' })
  }, [messages.length, pending])

  const ask = (question: string) =>
    run(async () => {
      const q = question.trim()
      if (!q) return
      setError(null)
      const history = messages.slice(-12).map((m) => ({ role: m.role, text: m.text }))
      setMessages((m) => [...m, { role: 'user', text: q }])
      setText('')
      try {
        const reply = await send(q, history)
        setMessages((m) => [...m, { role: 'assistant', text: reply.answer, sources: reply.sources }])
      } catch (err) {
        // the question stays in the box so it can be sent again once the problem is fixed
        setMessages((m) => m.slice(0, -1))
        setText(q)
        setError(errorMessage(err))
      }
    })

  return (
    <section className="chat" aria-label={label}>
      <div className="chat-log" role="log" aria-live="polite">
        {messages.length === 0 && (
          <div className="chat-empty">
            <Sparkles size={22} aria-hidden />
            <p>Ask in your own words. Every answer shows the figures it came from.</p>
            <div className="chat-suggestions">
              {suggestions.map((s) => (
                <button key={s} type="button" className="chat-chip" onClick={() => void ask(s)} disabled={pending}>
                  {s}
                </button>
              ))}
            </div>
          </div>
        )}
        {messages.map((m, i) => (
          <article key={i} className={`chat-message is-${m.role}`}>
            <span className="chat-avatar" aria-hidden>
              {m.role === 'user' ? <User size={16} /> : <Bot size={16} />}
            </span>
            <div className="chat-body">
              <p className="chat-text">{m.text}</p>
              {m.sources && m.sources.length > 0 && <Sources sources={m.sources} />}
            </div>
          </article>
        ))}
        {pending && (
          <p className="chat-thinking muted" role="status">
            <span className="spinner" aria-hidden /> Looking it up…
          </p>
        )}
        <div ref={end} />
      </div>
      {error && <Alert tone="error">{error}</Alert>}
      <form
        className="chat-form"
        onSubmit={(e) => {
          e.preventDefault()
          void ask(text)
        }}
      >
        <input className="input" aria-label={label} placeholder={placeholder} value={text} maxLength={1000} autoComplete="off" onChange={(e) => setText(e.target.value)} />
        <Button type="submit" disabled={pending || !text.trim()}>
          <Send size={16} aria-hidden /> Ask
        </Button>
      </form>
    </section>
  )
}

function Sources({ sources }: { sources: Source[] }) {
  return (
    <details className="chat-sources">
      <summary>
        Where this came from ({sources.length})
      </summary>
      <ul className="plain-list">
        {sources.map((s, i) => (
          <li key={i}>
            <strong>{TOOL_LABEL[s.tool] ?? s.tool}</strong>
            {Object.keys(s.input).length > 0 && <span className="muted text-sm"> {Object.values(s.input).join(', ')}</span>}
            <div className="chat-source-summary">{s.summary}</div>
          </li>
        ))}
      </ul>
    </details>
  )
}
