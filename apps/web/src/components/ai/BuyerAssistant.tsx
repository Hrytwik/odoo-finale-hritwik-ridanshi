import { ChatPanel } from '@/components/ai/ChatPanel'
import type { Key } from '@/i18n/en'
import { useI18n } from '@/i18n/I18nContext'
import { api, call, type components } from '@/lib/api'

const SUGGESTIONS: Key[] = ['assistant.q.deadline', 'assistant.q.where', 'assistant.q.delivered']

/** The buyer's assistant. It answers only from this buyer's own orders, and shows where each answer came from. */
export function BuyerAssistant() {
  const { t } = useI18n()
  return (
    <section className="stack-sm" aria-label={t('assistant.title')}>
      <h2>{t('assistant.title')}</h2>
      <ChatPanel
        label={t('assistant.title')}
        fill
        placeholder={t('assistant.placeholder')}
        suggestions={SUGGESTIONS.map((k) => t(k))}
        send={(question, history, language) => call(api.POST('/api/ai/buyer-assistant', { body: { question, history, language: language as components['schemas']['ChatIn']['language'] } }))}
      />
    </section>
  )
}
