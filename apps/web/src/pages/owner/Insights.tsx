import { useQuery } from '@tanstack/react-query'
import { Link } from 'react-router-dom'
import { EmptyState } from '@/components/common/EmptyState'
import { PageHeader } from '@/components/common/PageHeader'
import { QueryBoundary } from '@/components/common/QueryBoundary'
import { Reveal } from '@/components/motion/Reveal'
import { Badge } from '@/components/ui/Badge'
import { Table } from '@/components/ui/Table'
import { api, call, type components } from '@/lib/api'
import { formatDate, formatKg, formatPercent } from '@/lib/format'

type Eta = components['schemas']['EtaOut']
type Shortage = components['schemas']['ShortageOut']
type Cause = components['schemas']['RootCauseRow']

const STAGE: Record<string, string> = { spinning: 'Spinning', weaving: 'Weaving', dyeing: 'Dyeing' }
const FACTOR: Record<Cause['factor'], string> = {
  weaving_machine: 'Weaving machine',
  dyeing_machine: 'Dyeing machine',
  weaving_operator: 'Weaving operator',
  weaving_shift: 'Weaving shift',
  yarn_lot: 'Yarn lot',
}

/** What to act on this week: orders that will miss their date, yarn about to run short, and what is behind the defects. */
export default function Insights() {
  const late = useQuery({ queryKey: ['insights', 'late'], queryFn: () => call(api.GET('/api/insights/late-orders')) })
  const shortages = useQuery({ queryKey: ['insights', 'shortages'], queryFn: () => call(api.GET('/api/insights/shortages')) })
  const causes = useQuery({ queryKey: ['insights', 'causes'], queryFn: () => call(api.GET('/api/insights/root-causes')) })

  return (
    <>
      <PageHeader eyebrow="Owner" title="Insights" description="Late orders and what would fix them, yarn about to run short, and what is behind the defects." />
      <div className="stack">
        <section className="stack-sm" aria-label="Late orders">
          <h2>Late orders</h2>
          <QueryBoundary query={late}>
            {(orders) =>
              orders.length === 0 ? (
                <EmptyState title="Every order is on time" description="Orders that will miss their deadline show here, with what would fix them." />
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

        <section className="stack-sm" aria-label="Yarn shortages">
          <h2>Yarn to reorder</h2>
          <QueryBoundary query={shortages}>
            {(rows) => (rows.length === 0 ? <EmptyState title="No yarn is about to run short" /> : <Reveal><ShortageTable rows={rows} /></Reveal>)}
          </QueryBoundary>
        </section>

        <section className="stack-sm" aria-label="Defect causes">
          <h2>What is behind the defects</h2>
          <p className="muted text-sm">
            Each line compares the defect rate with the rest of the mill. A line is flagged only when the difference is too big to be chance.
          </p>
          <QueryBoundary query={causes}>
            {(rows) => (rows.length === 0 ? <EmptyState title="Not enough inspections yet" description="Causes appear once there are enough checked rolls to compare." /> : <Reveal><CauseTable rows={rows} /></Reveal>)}
          </QueryBoundary>
        </section>
      </div>
    </>
  )
}

function LateOrder({ order: o }: { order: Eta }) {
  return (
    <article className="card insight">
      <div className="card-body stack-sm">
        <div className="row">
          <Link to={`/orders/${o.order_code}`} className="code-text">
            {o.order_code}
          </Link>
          <span className="muted">{o.buyer_name}</span>
          {o.days_late > 0 ? <Badge tone="red">{o.days_late} days late</Badge> : <Badge tone="green">On time</Badge>}
        </div>
        <p>
          Promised for <strong>{formatDate(o.deadline)}</strong>. At the current pace it is ready on <strong>{formatDate(o.delivery_date)}</strong>
          {o.bottleneck_stage && <> and {STAGE[o.bottleneck_stage].toLowerCase()} is what holds it up</>}.
        </p>
        <ol className="finish-steps" aria-label="Finish date for each stage">
          {o.stages.map((s) => (
            <li key={s.stage} className={s.stage === o.bottleneck_stage ? 'is-bottleneck' : undefined}>
              <span className="muted text-sm">{STAGE[s.stage]} done</span>
              <strong>{formatDate(s.finish_date)}</strong>
            </li>
          ))}
        </ol>
        {o.what_ifs.length > 0 && (
          <div>
            <p className="text-sm muted">What would help</p>
            <ul className="plain-list">
              {o.what_ifs.map((w) => (
                <li key={w.kind}>
                  {w.label}: ready {formatDate(w.delivery_date)}, {w.days_late > 0 ? `${w.days_late} days late` : 'on time'}
                </li>
              ))}
            </ul>
          </div>
        )}
      </div>
    </article>
  )
}

function ShortageTable({ rows }: { rows: Shortage[] }) {
  return (
    <Table>
      <thead>
        <tr>
          <th>Yarn</th>
          <th className="num">Free now</th>
          <th className="num">Reorder level</th>
          <th>Order from</th>
          <th>Order by</th>
          <th className="num">Suggested</th>
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
            <td>{r.supplier?.name ?? <span className="muted">No supplier set</span>}</td>
            <td>
              {r.order_by ? formatDate(r.order_by) : <span className="muted">-</span>}
              {r.overdue_days > 0 && (
                <div>
                  <Badge tone="red">{r.overdue_days} days overdue</Badge>
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
  // flagged causes first, then the biggest gap to the rest of the mill
  const sorted = [...rows].sort((a, b) => Number(b.flagged) - Number(a.flagged) || b.rate - b.rest_rate - (a.rate - a.rest_rate))
  return (
    <Table>
      <thead>
        <tr>
          <th>Factor</th>
          <th>Which</th>
          <th className="num">Defective</th>
          <th className="num">Defect rate</th>
          <th className="num">Rest of mill</th>
          <th>Verdict</th>
        </tr>
      </thead>
      <tbody>
        {sorted.map((r) => (
          <tr key={`${r.factor}-${r.value}`}>
            <td>{FACTOR[r.factor]}</td>
            <td>
              <span className="code-text">{r.value}</span>
            </td>
            <td className="num">
              {r.defective} of {r.inspected}
            </td>
            <td className="num">
              <strong>{formatPercent(r.rate)}</strong>
            </td>
            <td className="num">{formatPercent(r.rest_rate)}</td>
            <td>
              {r.flagged ? <Badge tone="red">Likely cause</Badge> : <Badge tone="gray">Could be chance</Badge>}
              <div className="muted text-sm">{r.p_value < 0.001 ? 'p < 0.001' : `p = ${r.p_value.toFixed(2)}`}</div>
            </td>
          </tr>
        ))}
      </tbody>
    </Table>
  )
}
