import { useQuery } from '@tanstack/react-query'
import { Link } from 'react-router-dom'
import { ExplainDelay } from '@/components/ai/Drafts'
import { EmptyState } from '@/components/common/EmptyState'
import { PageHeader } from '@/components/common/PageHeader'
import { QueryBoundary } from '@/components/common/QueryBoundary'
import { Reveal } from '@/components/motion/Reveal'
import { Badge } from '@/components/ui/Badge'
import { Table } from '@/components/ui/Table'
import type { Key } from '@/i18n/en'
import { useI18n } from '@/i18n/I18nContext'
import { api, call, type components } from '@/lib/api'
import { formatDate, formatKg, formatPercent } from '@/lib/format'

type Eta = components['schemas']['EtaOut']
type Shortage = components['schemas']['ShortageOut']
type Cause = components['schemas']['RootCauseRow']


/** What to act on this week: orders that will miss their date, yarn about to run short, and what is behind the defects. */
export default function Insights() {
  const { t } = useI18n()
  const late = useQuery({ queryKey: ['insights', 'late'], queryFn: () => call(api.GET('/api/insights/late-orders')) })
  const shortages = useQuery({ queryKey: ['insights', 'shortages'], queryFn: () => call(api.GET('/api/insights/shortages')) })
  const causes = useQuery({ queryKey: ['insights', 'causes'], queryFn: () => call(api.GET('/api/insights/root-causes')) })

  return (
    <>
      <PageHeader eyebrow={t('nav.group.Owner')} title={t('nav.insights')} description={t('insight.description')} />
      <div className="stack">
        <section className="stack-sm" aria-label={t('insight.lateOrders')}>
          <h2>{t('insight.lateOrders')}</h2>
          <QueryBoundary query={late}>
            {(orders) =>
              orders.length === 0 ? (
                <EmptyState title={t('insight.allOnTime')} description={t('insight.allOnTimeHint')} />
              ) : (
                <div className="stack">
                  {orders.map((o) => (
                    <Reveal key={o.order_code}>
                      <LateOrder order={o} />
                    </Reveal>
                  ))}
                </div>
              )
            }
          </QueryBoundary>
        </section>

        <section className="stack-sm" aria-label={t('insight.yarnAria')}>
          <h2>{t('insight.yarnReorder')}</h2>
          <QueryBoundary query={shortages}>
            {(rows) => (rows.length === 0 ? <EmptyState title={t('insight.noShortage')} /> : <Reveal><ShortageTable rows={rows} /></Reveal>)}
          </QueryBoundary>
        </section>

        <section className="stack-sm" aria-label={t('insight.causes')}>
          <h2>{t('insight.causes')}</h2>
          <p className="muted text-sm">{t('insight.causesNote')}</p>
          <QueryBoundary query={causes}>
            {(rows) => (rows.length === 0 ? <EmptyState title={t('insight.notEnough')} description={t('insight.notEnoughHint')} /> : <Reveal><CauseTable rows={rows} /></Reveal>)}
          </QueryBoundary>
        </section>
      </div>
    </>
  )
}

function LateOrder({ order: o }: { order: Eta }) {
  const { t } = useI18n()
  const stageName = (s: string) => t(`floor.stage.${s}` as Key)
  const lateText = (days: number) => (days > 0 ? t('insight.daysLate', { days }) : t('insight.onTime').toLowerCase())
  return (
    <article className="card insight">
      <div className="card-body stack-sm">
        <div className="row">
          <Link to={`/orders/${o.order_code}`} className="code-text">
            {o.order_code}
          </Link>
          <span className="muted">{o.buyer_name}</span>
          {o.days_late > 0 ? <Badge tone="red">{t('insight.daysLate', { days: o.days_late })}</Badge> : <Badge tone="green">{t('insight.onTime')}</Badge>}
        </div>
        <p>
          {t('insight.lateLine', { deadline: formatDate(o.deadline), ready: formatDate(o.delivery_date) })}
          {o.bottleneck_stage && t('insight.holdsUp', { stage: stageName(o.bottleneck_stage).toLowerCase() })}.
        </p>
        <ol className="finish-steps" aria-label={t('insight.finishAria')}>
          {o.stages.map((s) => (
            <li key={s.stage} className={s.stage === o.bottleneck_stage ? 'is-bottleneck' : undefined}>
              <span className="muted text-sm">{t('insight.stageDone', { stage: stageName(s.stage) })}</span>
              <strong>{formatDate(s.finish_date)}</strong>
            </li>
          ))}
        </ol>
        {o.what_ifs.length > 0 && (
          <div>
            <p className="text-sm muted">{t('insight.whatHelps')}</p>
            <ul className="plain-list">
              {o.what_ifs.map((w) => (
                <li key={w.kind}>
                  {t('insight.whatIfLine', { label: w.label, date: formatDate(w.delivery_date), late: lateText(w.days_late) })}
                </li>
              ))}
            </ul>
          </div>
        )}
        {o.days_late > 0 && <ExplainDelay orderCode={o.order_code} />}
      </div>
    </article>
  )
}

function ShortageTable({ rows }: { rows: Shortage[] }) {
  const { t } = useI18n()
  return (
    <Table>
      <thead>
        <tr>
          <th>{t('insight.col.yarn')}</th>
          <th className="num">{t('insight.col.freeNow')}</th>
          <th className="num">{t('store.stock.reorderLevel')}</th>
          <th>{t('insight.col.orderFrom')}</th>
          <th>{t('insight.col.orderBy')}</th>
          <th className="num">{t('insight.col.suggested')}</th>
        </tr>
      </thead>
      <tbody>
        {rows.map((r) => (
          <tr key={r.yarn_type.id}>
            <td>
              <span className="code-text">{r.yarn_type.code}</span>
              <div className="muted text-sm">
                {r.yarn_type.name} · {r.yarn_type.colour}
              </div>
            </td>
            <td className="num">{r.free_kg < 0 ? <span className="text-danger">{formatKg(r.free_kg)}</span> : formatKg(r.free_kg)}</td>
            <td className="num">{formatKg(r.reorder_level_kg)}</td>
            <td>{r.supplier?.name ?? <span className="muted">{t('insight.noSupplier')}</span>}</td>
            <td>
              {r.order_by ? formatDate(r.order_by) : <span className="muted">-</span>}
              {r.overdue_days > 0 && (
                <div>
                  <Badge tone="red">{t('insight.daysOverdue', { days: r.overdue_days })}</Badge>
                </div>
              )}
            </td>
            <td className="num">
              <strong>{formatKg(r.suggested_kg)}</strong>
            </td>
          </tr>
        ))}
      </tbody>
    </Table>
  )
}

function CauseTable({ rows }: { rows: Cause[] }) {
  const { t } = useI18n()
  // flagged causes first, then the biggest gap to the rest of the mill
  const sorted = [...rows].sort((a, b) => Number(b.flagged) - Number(a.flagged) || b.rate - b.rest_rate - (a.rate - a.rest_rate))
  return (
    <Table>
      <thead>
        <tr>
          <th>{t('insight.col.factor')}</th>
          <th>{t('insight.col.which')}</th>
          <th className="num">{t('insight.col.defective')}</th>
          <th className="num">{t('insight.col.rate')}</th>
          <th className="num">{t('insight.col.restOfMill')}</th>
          <th>{t('insight.col.verdict')}</th>
        </tr>
      </thead>
      <tbody>
        {sorted.map((r) => (
          <tr key={`${r.factor}-${r.value}`}>
            <td>{t(`insight.factor.${r.factor}` as Key)}</td>
            <td>
              <span className="code-text">{r.value}</span>
            </td>
            <td className="num">
              {t('insight.defectiveOf', { n: r.defective, total: r.inspected })}
            </td>
            <td className="num">
              <strong>{formatPercent(r.rate)}</strong>
            </td>
            <td className="num">{formatPercent(r.rest_rate)}</td>
            <td>
              {r.flagged ? <Badge tone="red">{t('insight.likelyCause')}</Badge> : <Badge tone="gray">{t('insight.couldBeChance')}</Badge>}
              <div className="muted text-sm">{r.p_value < 0.001 ? 'p < 0.001' : `p = ${r.p_value.toFixed(2)}`}</div>
            </td>
          </tr>
        ))}
      </tbody>
    </Table>
  )
}
