/**
 * How the message will look in WhatsApp, as it is really sent: the sentence, then the tracking link on its own line.
 * (A tap-able button needs a business sender with an approved template, so none is drawn here.)
 */
import { useI18n } from '@/i18n/I18nContext'

export function WhatsAppPreview({ message, trackingUrl, time }: { message: string; trackingUrl: string | null; time?: string }) {
  const { t } = useI18n()
  return (
    <figure className="wa-preview" aria-label={t('wa.previewAria')}>
      <figcaption className="wa-from">
        <span className="wa-avatar" aria-hidden>
          EM
        </span>
        <span>
          {t('brand.name')} <small>{t('wa.business')}</small>
        </span>
      </figcaption>
      <div className="wa-bubble">
        <p>{message || '\u2026'}</p>
        {trackingUrl && (
          <p>
            {t('wa.track')} <span className="wa-link">{trackingUrl}</span>
          </p>
        )}
        <span className="wa-time">{time ?? t('portal.justNow')}</span>
      </div>
    </figure>
  )
}
