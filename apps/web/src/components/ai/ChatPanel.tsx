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
  fill = false,
}: {
  send: (question: string, history: { role: 'user' | 'assistant'; text: string }[]) => Promise<Chat>
  suggestions: string[]
  placeholder: string
  label: string
  /** use the whole width, and the height of the page, instead of a box */
  fill?: boolean
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
    <section className={fill ? 'chat chat-fill' : 'chat'} aria-label={label}>
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
              <RichText text={m.text} />
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

/** Bold (**like this**) and "- " bullet lines, which models write whatever they are asked; nothing else is interpreted. */
export function RichText({ text }: { text: string }) {
  const inline = (line: string) =>
    line.split(/(\*\*[^*]+\*\*)/g).map((part, i) => (part.startsWith('**') && part.endsWith('**') && part.length > 4 ? <strong key={i}>{part.slice(2, -2)}</strong> : part))
  const blocks: { bullets: boolean; lines: string[] }[] = []
  for (const raw of text.split(String.fromCharCode(10))) {
    const line = raw.trim()
    if (!line) continue
    const bullet = /^[-*•]\s+/.test(line)
    const last = blocks[blocks.length - 1]
    if (last && last.bullets === bullet) last.lines.push(bullet ? line.replace(/^[-*•]\s+/, '') : line)
    else blocks.push({ bullets: bullet, lines: [bullet ? line.replace(/^[-*•]\s+/, '') : line] })
  }
  return (
    <div className="chat-text">
      {blocks.map((b, i) =>
        b.bullets ? (
          <ul key={i} className="chat-list">
            {b.lines.map((l, j) => (
              <li key={j}>{inline(l)}</li>
            ))}
          </ul>
        ) : (
          b.lines.map((l, j) => <p key={`${i}-${j}`}>{inline(l)}</p>)
        ),
      )}
    </div>
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
