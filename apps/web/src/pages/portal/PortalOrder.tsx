import { useQuery } from '@tanstack/react-query'
import { ArrowLeft } from 'lucide-react'
import { Link, useParams } from 'react-router-dom'
import { BuyerAssistant } from '@/components/ai/BuyerAssistant'
import { EmptyState } from '@/components/common/EmptyState'
import { KpiCard } from '@/components/common/KpiCard'
import { LiveBadge } from '@/components/common/LiveBadge'
import { PageHeader } from '@/components/common/PageHeader'
import { QueryBoundary } from '@/components/common/QueryBoundary'
import { StageBar } from '@/components/common/StageBar'
import { AnimatedGroup } from '@/components/motion/AnimatedGroup'
import { Reveal } from '@/components/motion/Reveal'
import { Button } from '@/components/ui/Button'
import { Table } from '@/components/ui/Table'
import { useI18n } from '@/i18n/I18nContext'
import { ApiError, api, call } from '@/lib/api'
import { formatDate, formatDateTime, formatMetres } from '@/lib/format'
import { useStageToasts } from '@/lib/useStageToasts'
import { DeliveryLine } from './PortalHome'

/** One order: its stage, the dates, everything that happened to it so far, and each truck that carried part of it. */
export default function PortalOrder() {
  const { t } = useI18n()
  const { code = '' } = useParams()
  const order = useQuery({
    queryKey: ['portal', 'orders', code],
    queryFn: () => call(api.GET('/api/portal/orders/{order_code}', { params: { path: { order_code: code } } })),
    enabled: !!code,
    retry: false,
  })
  useStageToasts(order.data ? [order.data] : undefined)
  const missing = order.error instanceof ApiError && order.error.status === 404

  if (missing) {
    return (
      <EmptyState
        title={t('portal.notFound')}
        description={t('portal.notFoundHint')}
        action={
          <Link to="/portal">
            <Button variant="secondary">{t('nav.myOrders')}</Button>
          </Link>
        }
      />
    )
  }
  return (
    <>
      <QueryBoundary query={order}>
        {(o) => (
          <>
            <PageHeader
              eyebrow={`${o.fabric} · ${o.colour}`}
              title={o.code}
              description={t('portal.orderedQty', { metres: formatMetres(o.qty_metres) })}
              actions={
                <Link to="/portal">
                  <Button variant="secondary">
                    <ArrowLeft size={16} aria-hidden /> {t('nav.myOrders')}
                  </Button>
                </Link>
              }
            />
            <div className="stack">
              <LiveBadge updatedAt={order.dataUpdatedAt} />
              <StageBar stage={o.stage} />
              <AnimatedGroup className="grid-cards">
                <KpiCard label={t('portal.workDone')} value={o.progress_pct} format={(n) => `${Math.round(n)}%`} hint={t('portal.workDoneHint')} />
                <KpiCard label={t('portal.promisedFor')} value={0} format={() => formatDate(o.deadline)} hint={o.delivery_date ? t('portal.expectedOn', { date: formatDate(o.delivery_date) }) : t('portal.willConfirm')} />
                <KpiCard label={t('portal.sentSoFar')} value={o.dispatches.reduce((n, d) => n + d.metres, 0)} format={formatMetres} hint={t(o.dispatches.length === 1 ? 'portal.trucks.one' : 'portal.trucks.many', { count: o.dispatches.length })} />
              </AnimatedGroup>
              <DeliveryLine order={o} />

              <Reveal>
                <section className="card" aria-label={t('portal.happened')}>
                  <div className="card-header">
                    <h2 className="card-title">{t('portal.happened')}</h2>
                  </div>
                  <div className="card-body">
                    {o.timeline.length === 0 ? (
                      <p className="muted">{t('portal.nothingYet')}</p>
                    ) : (
                      <ol className="portal-timeline">
                        {o.timeline.map((e, i) => (
                          <li key={`${e.at}-${i}`}>
                            <strong>{e.label}</strong>
                            <span className="muted text-sm">{formatDateTime(e.at)}</span>
                          </li>
                        ))}
                      </ol>
                    )}
                  </div>
                </section>
              </Reveal>

              <Reveal>
                <section className="stack-sm" aria-label={t('portal.dispatches')}>
                  <h2>{t('portal.sentToYou')}</h2>
                  {o.dispatches.length === 0 ? (
                    <p className="muted">{t('portal.nothingSent')}</p>
                  ) : (
                    <Table>
                      <thead>
                        <tr>
                          <th>{t('portal.col.truck')}</th>
                          <th>{t('portal.col.sent')}</th>
                          <th className="num">{t('portal.col.length')}</th>
                          <th>{t('dispatch.col.invoice')}</th>
                        </tr>
                      </thead>
                      <tbody>
                        {o.dispatches.map((d) => (
                          <tr key={d.code}>
                            <td>
                              <span className="code-text">{d.code}</span>
                            </td>
                            <td className="nowrap">{formatDateTime(d.dispatched_at)}</td>
                            <td className="num">{formatMetres(d.metres)}</td>
                            <td>{d.invoice_no ? <Link to={`/invoices/${d.invoice_no}`}>{d.invoice_no}</Link> : <span className="muted">-</span>}</td>
                          </tr>
                        ))}
                      </tbody>
                    </Table>
                  )}
                </section>
              </Reveal>
              <BuyerAssistant />
            </div>
          </>
        )}
      </QueryBoundary>
    </>
  )
}
