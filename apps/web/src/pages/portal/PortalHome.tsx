import { useQuery } from '@tanstack/react-query'
import { CalendarClock } from 'lucide-react'
import { Link } from 'react-router-dom'
import { BuyerAssistant } from '@/components/ai/BuyerAssistant'
import { EmptyState } from '@/components/common/EmptyState'
import { PageHeader } from '@/components/common/PageHeader'
import { QueryBoundary } from '@/components/common/QueryBoundary'
import { StageBar, StageLegend } from '@/components/common/StageBar'
import { Reveal } from '@/components/motion/Reveal'
import { api, call, type components } from '@/lib/api'
import { formatDate, formatMetres } from '@/lib/format'

type Order = components['schemas']['PortalOrder']

/** The buyer's own orders: where each one stands, and a place to ask in plain words. */
export default function PortalHome() {
  const orders = useQuery({ queryKey: ['portal', 'orders'], queryFn: () => call(api.GET('/api/portal/orders')) })
  return (
    <>
      <PageHeader eyebrow="Your orders" title="My orders" description="Where each of your orders stands, and when it should reach you. Updates as the mill works." />
      <div className="stack">
        <QueryBoundary query={orders}>
          {(list) =>
            list.length === 0 ? (
              <EmptyState title="No orders yet" description="Orders the mill has confirmed for you appear here." />
            ) : (
              <>
                <StageLegend />
                <div className="portal-orders">
                  {list.map((o) => (
                    <Reveal key={o.code}>
                      <OrderCard order={o} />
                    </Reveal>
                  ))}
                </div>
              </>
            )
          }
        </QueryBoundary>
        <BuyerAssistant />
      </div>
    </>
  )
}

export function DeliveryLine({ order }: { order: Pick<Order, 'delivery_date' | 'deadline' | 'stage'> }) {
  if (order.stage === 'dispatched') return <span className="muted">All of it has been sent</span>
  if (order.stage === 'cancelled') return <span className="muted">This order was cancelled</span>
  return (
    <span className="portal-date">
      <CalendarClock size={15} aria-hidden />
      {order.delivery_date ? (
        <>Expected <strong>{formatDate(order.delivery_date)}</strong> · promised {formatDate(order.deadline)}</>
      ) : (
        <>Promised for <strong>{formatDate(order.deadline)}</strong></>
      )}
    </span>
  )
}

function OrderCard({ order: o }: { order: Order }) {
  return (
    <Link to={`/portal/orders/${o.code}`} className="card portal-card" aria-label={`Order ${o.code}`}>
      <div className="card-body stack-sm">
        <div className="row">
          <span className="code-text">{o.code}</span>
          <span className="muted">
            {o.fabric} · {o.colour} · {formatMetres(o.qty_metres)}
          </span>
        </div>
        <StageBar stage={o.stage} />
        <div className="portal-meter" role="img" aria-label={`About ${Math.round(o.progress_pct)} percent of the work is done`}>
          <i style={{ width: `${Math.min(100, Math.max(0, o.progress_pct))}%` }} />
        </div>
        <DeliveryLine order={o} />
      </div>
    </Link>
  )
}
