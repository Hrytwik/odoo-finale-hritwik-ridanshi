import { BellRing, MessageCircle } from 'lucide-react'
import { useState } from 'react'
import { toast } from 'sonner'
import { ActionDialog } from '@/components/common/ActionDialog'
import { WhatsAppPreview } from '@/components/common/WhatsAppPreview'
import { Button } from '@/components/ui/Button'
import { Field, Select, Textarea } from '@/components/ui/Field'
import type { Key } from '@/i18n/en'
import { useI18n } from '@/i18n/I18nContext'
import { api, call, errorMessage, type components } from '@/lib/api'
import { useMe } from '@/lib/auth'
import { useSubmitLock } from '@/lib/forms'
import { whatsappLink } from '@/lib/whatsappLink'

/** The reasons the owner can pick from. The same list, in the same order, as the server's. */
const DELAY_REASONS = ['yarn_shortage', 'machine_breakdown', 'power_cut', 'staff_shortage', 'quality_rework', 'dye_delay', 'transport', 'buyer_change', 'other'] as const
type Reason = (typeof DELAY_REASONS)[number]
type Channel = components['schemas']['ChannelOut']

/** "Tell the buyer about a delay": the owner picks one reason, a sentence is drafted, the owner can edit it, then it goes to the buyer's bell. */
export function DelayNoticeButton({ orderCode, buyerName }: { orderCode: string; buyerName: string }) {
  const { t } = useI18n()
  const me = useMe()
  const [open, setOpen] = useState(false)
  if (me.data?.role !== 'owner') return null
  return (
    <>
      <Button variant="secondary" onClick={() => setOpen(true)}>
        <BellRing size={16} aria-hidden /> {t('delay.button')}
      </Button>
      {open && <DelayNoticeDialog orderCode={orderCode} buyerName={buyerName} onClose={() => setOpen(false)} />}
    </>
  )
}

function DelayNoticeDialog({ orderCode, buyerName, onClose }: { orderCode: string; buyerName: string; onClose: () => void }) {
  const { t } = useI18n()
  const path = { params: { path: { order_code: orderCode } } }
  const [reason, setReason] = useState<Reason | ''>('')
  const [message, setMessage] = useState('')
  const [byModel, setByModel] = useState<boolean | null>(null)
  const [channel, setChannel] = useState<Channel | null>(null)
  const [drafting, setDrafting] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const { run, pending } = useSubmitLock()

  async function choose(next: Reason | '') {
    setReason(next)
    setMessage('')
    setByModel(null)
    setError(null)
    if (!next) return
    setDrafting(true)
    try {
      const d = await call(api.POST('/api/orders/{order_code}/delay-notice/draft', { ...path, body: { reason: next } }))
      setMessage(d.message)
      setByModel(d.drafted_by_ai)
      setChannel(d.channel)
    } catch (err) {
      setError(errorMessage(err))
    } finally {
      setDrafting(false)
    }
  }

  const send = () =>
    run(async () => {
      if (!reason) return setError(t('delay.err.chooseReason'))
      if (!message.trim()) return setError(t('delay.err.empty'))
      setError(null)
      try {
        const sent = await call(api.POST('/api/orders/{order_code}/delay-notice', { ...path, body: { reason, message } }))
        if (sent.whatsapp_status === 'sent') toast.success(t('delay.toast.both', { buyer: buyerName }))
        else if (sent.whatsapp_status === 'failed') toast.warning(t('delay.toast.failed', { buyer: buyerName, detail: sent.whatsapp_detail ?? '' }))
        else toast.success(t('delay.toast.app', { buyer: buyerName }))
        onClose()
      } catch (err) {
        setError(errorMessage(err))
      }
    })

  return (
    <ActionDialog open onClose={onClose} title={t('delay.title', { buyer: buyerName })} confirmLabel={t('delay.send')} onConfirm={() => void send()} pending={pending} error={error}>
      <p className="muted text-sm">
        {t('delay.intro', { order: orderCode })}
      </p>
      <Field label={t('delay.reasonLabel')}>
        {(c) => (
          <Select {...c} value={reason} onChange={(e) => void choose(e.target.value as Reason | '')}>
            <option value="">{t('delay.choose')}</option>
            {DELAY_REASONS.map((r) => (
              <option key={r} value={r}>
                {t(`delay.reason.${r}` as Key)}
              </option>
            ))}
          </Select>
        )}
      </Field>
      {drafting && (
        <p className="muted text-sm" role="status">
          <span className="spinner" aria-hidden /> {t('delay.writing')}
        </p>
      )}
      {reason && !drafting && byModel !== null && (
        <Field label={t('delay.messageLabel')} hint={byModel ? t('delay.hintAi') : t('delay.hintStandard')}>
          {(c) => <Textarea {...c} rows={4} maxLength={400} value={message} onChange={(e) => setMessage(e.target.value)} />}
        </Field>
      )}
      {reason && !drafting && channel && message !== '' && (
        <div className="stack-sm">
          <p className="eyebrow">{t('delay.alsoWhatsapp')}</p>
          <WhatsAppPreview message={message} trackingUrl={channel.tracking_url} />
          <p className={channel.whatsapp_ready || channel.phone ? 'muted text-sm' : 'text-sm text-danger'}>{channel.whatsapp_ready ? `It will also be sent to ${channel.to}.` : channel.problem}</p>
          {channel.phone && (
            <p className="row">
              <a className="btn btn-secondary" href={whatsappLink(channel.phone, message, channel.tracking_url)} target="_blank" rel="noopener noreferrer">
                <MessageCircle size={16} aria-hidden /> {t('delay.sendFromMine')}
              </a>
              <span className="muted text-sm">{t('delay.opens', { to: channel.to ?? '' })}</span>
            </p>
          )}
        </div>
      )}
    </ActionDialog>
  )
}
