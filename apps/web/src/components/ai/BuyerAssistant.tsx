import { ChatPanel } from '@/components/ai/ChatPanel'
import { api, call } from '@/lib/api'

const SUGGESTIONS = ['Will my order make its deadline?', 'Where is my order right now?', 'When will it be delivered?']

/** The buyer's assistant. It answers only from this buyer's own orders, and shows where each answer came from. */
export function BuyerAssistant() {
  return (
    <section className="stack-sm" aria-label="Ask about your orders">
      <h2>Ask about your orders</h2>
      <ChatPanel
        label="Ask about your orders"
        fill
        placeholder="For example: will my order make the 20th?"
        suggestions={SUGGESTIONS}
        send={(question, history) => call(api.POST('/api/ai/buyer-assistant', { body: { question, history } }))}
      />
    </section>
  )
}
