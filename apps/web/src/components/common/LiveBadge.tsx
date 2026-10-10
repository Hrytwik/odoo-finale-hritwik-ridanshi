import { useEffect, useState } from 'react'
import { sinceText } from '@/lib/stageChanges'

/** A small "Live" pill with how long ago the data was fetched. The screen refetches by itself when the mill changes something. */
export function LiveBadge({ updatedAt }: { updatedAt: number }) {
  const [now, setNow] = useState(() => Date.now())
  useEffect(() => {
    const id = window.setInterval(() => setNow(Date.now()), 1000)
    return () => window.clearInterval(id)
  }, [])
  return (
    <span className="live-badge" role="status" aria-label="Live: this page updates by itself">
      <i aria-hidden /> Live · updated {updatedAt ? sinceText((now - updatedAt) / 1000) : 'just now'}
    </span>
  )
}
