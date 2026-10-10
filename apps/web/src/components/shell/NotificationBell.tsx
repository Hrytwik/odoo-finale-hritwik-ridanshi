import { useQuery, useQueryClient } from '@tanstack/react-query'
import { Bell } from 'lucide-react'
import { useEffect, useRef, useState } from 'react'
import { Link } from 'react-router-dom'
import { toast } from 'sonner'
import { Button } from '@/components/ui/Button'
import { Dialog } from '@/components/ui/Dialog'
import { api, call, type components } from '@/lib/api'
import { formatDateTime } from '@/lib/format'

type Notifications = components['schemas']['NotificationsOut']

/** The buyer's bell: a count of messages from the mill (such as a delay and why), a list when opened, and a toast when a new one arrives. */
export function NotificationBell() {
  const queryClient = useQueryClient()
  const [open, setOpen] = useState(false)
  const notices = useQuery({ queryKey: ['notices'], queryFn: () => call(api.GET('/api/portal/notifications')) })
  const seen = useRef<Set<number> | null>(null)

  // a toast for each message that arrives while the page is open (not for the ones already there when it loaded)
  useEffect(() => {
    if (!notices.data) return
    if (seen.current) for (const n of notices.data.items) if (!seen.current.has(n.id) && !n.read) toast.info(n.message, { description: `Order ${n.order_code}` })
    seen.current = new Set(notices.data.items.map((n) => n.id))
  }, [notices.data])

  async function openBell() {
    setOpen(true)
    if ((notices.data?.unread ?? 0) > 0) {
      try {
        queryClient.setQueryData<Notifications>(['notices'], await call(api.POST('/api/portal/notifications/read')))
      } catch {
        // the list still shows; it is marked read the next time it is opened
      }
    }
  }

  const unread = notices.data?.unread ?? 0
  return (
    <>
      <Button variant="ghost" icon className="header-square bell" aria-label={unread > 0 ? `Notifications, ${unread} new` : 'Notifications'} onClick={() => void openBell()}>
        <Bell size={18} aria-hidden />
        {unread > 0 && (
          <span className="bell-count" aria-hidden>
            {unread > 9 ? '9+' : unread}
          </span>
        )}
      </Button>
      <Dialog open={open} onClose={() => setOpen(false)} title="Notifications">
        {notices.data && notices.data.items.length === 0 ? (
          <p className="muted">Nothing yet. If the mill has news about one of your orders, it appears here.</p>
        ) : (
          <ul className="notice-list">
            {notices.data?.items.map((n) => (
              <li key={n.id}>
                <p>{n.message}</p>
                <p className="muted text-sm">
                  <Link to={`/portal/orders/${n.order_code}`} onClick={() => setOpen(false)}>
                    {n.order_code}
                  </Link>{' '}
                  · {n.reason_label} · {formatDateTime(n.created_at)}
                  {n.whatsapp_status === 'sent' && <> · also sent on WhatsApp</>}
                </p>
              </li>
            ))}
          </ul>
        )}
      </Dialog>
    </>
  )
}
