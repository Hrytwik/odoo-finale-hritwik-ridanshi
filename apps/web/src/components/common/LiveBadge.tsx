import { useEffect, useState } from 'react'
import { useI18n } from '@/i18n/I18nContext'

/** A small "Live" pill with how long ago the data was fetched. The screen refetches by itself when the mill changes something. */
export function LiveBadge({ updatedAt }: { updatedAt: number }) {
  const { t } = useI18n()
  const [now, setNow] = useState(() => Date.now())
  useEffect(() => {
    const id = window.setInterval(() => setNow(Date.now()), 1000)
    return () => window.clearInterval(id)
  }, [])
  const seconds = updatedAt ? (now - updatedAt) / 1000 : 0
  const when = seconds < 5 ? t('portal.justNow') : seconds < 60 ? t('portal.secondsAgo', { n: Math.floor(seconds) }) : t('portal.minutesAgo', { n: Math.floor(seconds / 60) })
  return (
    <span className="live-badge" role="status" aria-label={t('portal.liveAria')}>
      <i aria-hidden /> {t('portal.liveUpdated', { when })}
    </span>
  )
}
