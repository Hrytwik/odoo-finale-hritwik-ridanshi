import { useQuery } from '@tanstack/react-query'
import { Truck } from 'lucide-react'
import { Link } from 'react-router-dom'
import { Alert } from '@/components/common/Alert'
import { KpiCard } from '@/components/common/KpiCard'
import { QueryBoundary } from '@/components/common/QueryBoundary'
import { AnimatedGroup } from '@/components/motion/AnimatedGroup'
import { Badge } from '@/components/ui/Badge'
import { Button } from '@/components/ui/Button'
import { Card } from '@/components/ui/Card'
import { Table } from '@/components/ui/Table'
import { useI18n } from '@/i18n/I18nContext'
import { api, call, type components } from '@/lib/api'
import { formatDateTime, formatMetres } from '@/lib/format'

type Order = components['schemas']['OrderOut']
type Dispatch = components['schemas']['DispatchOut']

/** What this order has on each truck, in the order the trucks were made. Only this order's rolls are counted. */
function trucksFor(code: string, all: Dispatch[]) {
  return all
    .filter((d) => d.orders.some((o) => o.order_code === code))
    .map((d) => {
      const mine = d.rolls.filter((r) => r.order_code === code)
      return { d, metres: mine.reduce((sum, r) => sum + r.metres, 0), rolls: mine.length }
    })
    .sort((a, b) => (a.d.dispatched_at ?? a.d.created_at).localeCompare(b.d.dispatched_at ?? b.d.created_at))
}

/**
 * The owner's balance sheet for one order: sent, ready in store, still being made, rejected, and each truck. It updates by itself,
 * because confirming a dispatch refreshes the order and the dispatch list. When nothing more is coming and the order will fall
 * short, it says so instead of leaving the order "partly dispatched" with no explanation.
 */
export function ShipmentsCard({ order }: { order: Order }) {
  const { t } = useI18n()
  const dispatches = useQuery({ queryKey: ['dispatches'], queryFn: () => call(api.GET('/api/dispatches')) })
  const p = order.progress
  const ordered = order.qty_metres
  const ready = Math.max(0, p.passed_m - p.dispatched_m)
  const making = Math.max(0, ordered - p.passed_m - p.rejected_m)
  const short = Math.max(0, ordered - p.dispatched_m - ready - making)
  const complete = p.dispatched_m >= ordered
  const startedSending = p.dispatched_m > 0 || ready > 0

  return (
    <Card title={t('ship.title')}>
      <div className="stack">
        <AnimatedGroup className="grid-cards">
          <KpiCard label={t('ship.sent')} value={p.dispatched_m} format={formatMetres} />
          <KpiCard label={t('ship.ready')} value={ready} format={formatMetres} hint={t('ship.readyHint')} tone={ready > 0 ? 'danger' : undefined} />
          <KpiCard label={t('ship.making')} value={making} format={formatMetres} />
          <KpiCard label={t('ship.rejectedLabel')} value={p.rejected_m} format={formatMetres} />
        </AnimatedGroup>
        <p>
          {complete
            ? t('ship.allSent', { ordered: formatMetres(ordered) })
            : t('ship.summary', { sent: formatMetres(p.dispatched_m), ordered: formatMetres(ordered), ready: formatMetres(ready), making: formatMetres(making) })}
        </p>
        {!complete && making === 0 && short > 0 && <Alert tone="error">{t('ship.shortNote', { short: formatMetres(short), rejected: formatMetres(p.rejected_m) })}</Alert>}
        <QueryBoundary query={dispatches} rows={2}>
          {(all) => {
            const trucks = trucksFor(order.code, all)
            if (trucks.length === 0) return <p className="muted">{t('ship.noTrucks')}</p>
            return (
              <Table>
                <thead>
                  <tr>
                    <th>{t('portal.col.truck')}</th>
                    <th>{t('portal.col.sent')}</th>
                    <th>{t('dispatch.col.vehicle')}</th>
                    <th className="num">{t('ship.truckMetres')}</th>
                    <th className="num">{t('dispatch.col.rolls')}</th>
                    <th>{t('dispatch.col.invoice')}</th>
                  </tr>
                </thead>
                <tbody>
                  {trucks.map(({ d, metres, rolls }) => (
                    <tr key={d.code}>
                      <td>
                        <Link to={`/dispatch/${d.code}`}>{d.code}</Link>
                      </td>
                      <td className="nowrap">{d.dispatched_at ? formatDateTime(d.dispatched_at) : <Badge tone="amber">{t('ship.loadingNow')}</Badge>}</td>
                      <td>{d.vehicle_no}</td>
                      <td className="num">{formatMetres(metres)}</td>
                      <td className="num">{rolls}</td>
                      <td>{d.invoice_no ? <Link to={`/invoices/${d.invoice_no}`}>{d.invoice_no}</Link> : <span className="muted">-</span>}</td>
                    </tr>
                  ))}
                </tbody>
              </Table>
            )
          }}
        </QueryBoundary>
        {!complete && startedSending && ready > 0 && (
          <div>
            <Link to="/dispatch">
              <Button variant="secondary">
                <Truck size={16} aria-hidden /> {t('ship.planTruck')}
              </Button>
            </Link>
          </div>
        )}
      </div>
    </Card>
  )
}
