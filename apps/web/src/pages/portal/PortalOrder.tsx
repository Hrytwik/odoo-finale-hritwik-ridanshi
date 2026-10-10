import { useQuery } from '@tanstack/react-query'
import { ArrowLeft } from 'lucide-react'
import { Link, useParams } from 'react-router-dom'
import { BuyerAssistant } from '@/components/ai/BuyerAssistant'
import { EmptyState } from '@/components/common/EmptyState'
import { KpiCard } from '@/components/common/KpiCard'
import { PageHeader } from '@/components/common/PageHeader'
import { QueryBoundary } from '@/components/common/QueryBoundary'
import { StageBar } from '@/components/common/StageBar'
import { AnimatedGroup } from '@/components/motion/AnimatedGroup'
import { Reveal } from '@/components/motion/Reveal'
import { Button } from '@/components/ui/Button'
import { Table } from '@/components/ui/Table'
import { ApiError, api, call } from '@/lib/api'
import { formatDate, formatDateTime, formatMetres } from '@/lib/format'
import { DeliveryLine } from './PortalHome'

/** One order: its stage, the dates, everything that happened to it so far, and each truck that carried part of it. */
export default function PortalOrder() {
  const { code = '' } = useParams()
  const order = useQuery({
    queryKey: ['portal', 'orders', code],
    queryFn: () => call(api.GET('/api/portal/orders/{order_code}', { params: { path: { order_code: code } } })),
    enabled: !!code,
    retry: false,
  })
  const missing = order.error instanceof ApiError && order.error.status === 404

  if (missing) {
    return (
      <EmptyState
        title="We could not find that order"
        description="Check the order number, or go back to your list."
        action={
          <Link to="/portal">
            <Button variant="secondary">My orders</Button>
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
              description={`${formatMetres(o.qty_metres)} ordered`}
              actions={
                <Link to="/portal">
                  <Button variant="secondary">
                    <ArrowLeft size={16} aria-hidden /> My orders
                  </Button>
                </Link>
              }
            />
            <div className="stack">
              <StageBar stage={o.stage} />
              <AnimatedGroup className="grid-cards">
                <KpiCard label="Work done" value={o.progress_pct} format={(n) => `${Math.round(n)}%`} hint="A rough share of the work finished" />
                <KpiCard label="Promised for" value={0} format={() => formatDate(o.deadline)} hint={o.delivery_date ? `Expected ${formatDate(o.delivery_date)}` : 'We will confirm a date as work moves on'} />
                <KpiCard label="Sent so far" value={o.dispatches.reduce((n, d) => n + d.metres, 0)} format={formatMetres} hint={`${o.dispatches.length} truck${o.dispatches.length === 1 ? '' : 's'}`} />
              </AnimatedGroup>
              <DeliveryLine order={o} />

              <Reveal>
                <section className="card" aria-label="What has happened">
                  <div className="card-header">
                    <h2 className="card-title">What has happened</h2>
                  </div>
                  <div className="card-body">
                    {o.timeline.length === 0 ? (
                      <p className="muted">Nothing yet. Work starts after the order is confirmed.</p>
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
                <section className="stack-sm" aria-label="Dispatches">
                  <h2>Sent to you</h2>
                  {o.dispatches.length === 0 ? (
                    <p className="muted">Nothing has been sent yet.</p>
                  ) : (
                    <Table>
                      <thead>
                        <tr>
                          <th>Truck</th>
                          <th>Sent</th>
                          <th className="num">Length</th>
                          <th>Invoice</th>
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
