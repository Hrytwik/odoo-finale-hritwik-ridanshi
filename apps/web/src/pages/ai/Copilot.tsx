import { ChatPanel } from '@/components/ai/ChatPanel'
import { PageHeader } from '@/components/common/PageHeader'
import type { Key } from '@/i18n/en'
import { useI18n } from '@/i18n/I18nContext'
import { api, call, type components } from '@/lib/api'
import { useMe } from '@/lib/auth'

const MANAGER: Key[] = ['copilot.q.late', 'copilot.q.yarn', 'copilot.q.down', 'copilot.q.fabrics', 'copilot.q.qc', 'copilot.q.defects']
const FINANCE: Key[] = [...MANAGER, 'copilot.q.month', 'copilot.q.owed', 'copilot.q.suppliers']

/** Ask about orders, stock, late work and defects in plain language. Supervisors do not see cost questions, as elsewhere. */
type Language = components['schemas']['ChatIn']['language']

export default function Copilot() {
  const me = useMe()
  const { t } = useI18n()
  const finance = me.data?.role === 'owner' || me.data?.role === 'accountant'
  return (
    <>
      <PageHeader eyebrow={t('nav.group.AI')} title={t('copilot.title')} description={t('copilot.description')} />
      <ChatPanel
        label="Ask the copilot"
        fill
        placeholder={t('copilot.placeholder')}
        suggestions={(finance ? FINANCE : MANAGER).map((k) => t(k))}
        send={(question, history, language) => call(api.POST('/api/ai/copilot', { body: { question, history, language: language as Language } }))}
      />
    </>
  )
}
