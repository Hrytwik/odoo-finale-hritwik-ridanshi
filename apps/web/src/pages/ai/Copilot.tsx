import { ChatPanel } from '@/components/ai/ChatPanel'
import { PageHeader } from '@/components/common/PageHeader'
import { api, call } from '@/lib/api'
import { useMe } from '@/lib/auth'

const MANAGER = [
  'Which orders will be late?',
  'How much yarn is free right now?',
  'Which machines are down right now?',
  'What fabrics do we make?',
  'Which rolls are waiting for quality check?',
  'What is behind our defects?',
]
const FINANCE = [...MANAGER, 'How did we do this month?', 'Which buyers owe us money?', 'What do we owe suppliers?']

/** Ask about orders, stock, late work and defects in plain language. Supervisors do not see cost questions, as elsewhere. */
export default function Copilot() {
  const me = useMe()
  const finance = me.data?.role === 'owner' || me.data?.role === 'accountant'
  return (
    <>
      <PageHeader eyebrow="AI" title="Copilot" description="Ask about orders, yarn, late work and defects. The answer comes from the mill's own numbers, never from a guess." />
      <ChatPanel
        label="Ask the copilot"
        fill
        placeholder="For example: which orders will be late?"
        suggestions={finance ? FINANCE : MANAGER}
        send={(question, history) => call(api.POST('/api/ai/copilot', { body: { question, history } }))}
      />
    </>
  )
}
