import { useQuery } from '@tanstack/react-query'
import { CalendarClock } from 'lucide-react'
import { Link } from 'react-router-dom'
import { BuyerAssistant } from '@/components/ai/BuyerAssistant'
import { EmptyState } from '@/components/common/EmptyState'
import { LiveBadge } from '@/components/common/LiveBadge'
import { PageHeader } from '@/components/common/PageHeader'
import { QueryBoundary } from '@/components/common/QueryBoundary'
import { StageBar, StageLegend } from '@/components/common/StageBar'
import { Reveal } from '@/components/motion/Reveal'
import { useI18n } from '@/i18n/I18nContext'
import { api, call, type components } from '@/lib/api'
import { formatDate, formatMetres } from '@/lib/format'
import { useStageToasts } from '@/lib/useStageToasts'

type Order = components['schemas']['PortalOrder']

/** The buyer's own orders: where each one stands, and a place to ask in plain words. */
export default function PortalHome() {
  const { t } = useI18n()
  const orders = useQuery({ queryKey: ['portal', 'orders'], queryFn: () => call(api.GET('/api/portal/orders')) })
  useStageToasts(orders.data)
  return (
    <>
      <PageHeader eyebrow={t('portal.eyebrow')} title={t('nav.myOrders')} description={t('portal.description')} />
      <div className="stack">
        <LiveBadge updatedAt={orders.dataUpdatedAt} />
        <QueryBoundary query={orders}>
          {(list) =>
            list.length === 0 ? (
              <EmptyState title={t('portal.emptyTitle')} description={t('portal.emptyDescription')} />
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
  const { t } = useI18n()
  if (order.stage === 'dispatched') return <span className="muted">{t('portal.allSent')}</span>
  if (order.stage === 'cancelled') return <span className="muted">{t('portal.cancelled')}</span>
  return (
    <span className="portal-date">
      <CalendarClock size={15} aria-hidden />
      {order.delivery_date ? (
        <>{t('portal.expected')} <strong>{formatDate(order.delivery_date)}</strong> · {t('portal.promisedShort')} {formatDate(order.deadline)}</>
      ) : (
        <>{t('portal.promisedFor')} <strong>{formatDate(order.deadline)}</strong></>
      )}
    </span>
  )
}

function OrderCard({ order: o }: { order: Order }) {
  const { t } = useI18n()
  return (
    <Link to={`/portal/orders/${o.code}`} className="card portal-card" aria-label={t('portal.orderAria', { code: o.code })}>
      <div className="card-body stack-sm">
        <div className="row">
          <span className="code-text">{o.code}</span>
          <span className="muted">
            {o.fabric} · {o.colour} · {formatMetres(o.qty_metres)}
          </span>
        </div>
        <StageBar stage={o.stage} />
        <div className="portal-meter" role="img" aria-label={t('portal.progressAria', { pct: Math.round(o.progress_pct) })}>
          <i style={{ width: `${Math.min(100, Math.max(0, o.progress_pct))}%` }} />
        </div>
        <DeliveryLine order={o} />
      </div>
    </Link>
  )
}
