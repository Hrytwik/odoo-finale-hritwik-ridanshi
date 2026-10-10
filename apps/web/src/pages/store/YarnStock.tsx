import { useQuery } from '@tanstack/react-query'
import { Alert } from '@/components/common/Alert'
import { EmptyState } from '@/components/common/EmptyState'
import { KpiCard } from '@/components/common/KpiCard'
import { PageHeader } from '@/components/common/PageHeader'
import { QueryBoundary } from '@/components/common/QueryBoundary'
import { AnimatedGroup } from '@/components/motion/AnimatedGroup'
import { Reveal } from '@/components/motion/Reveal'
import { Badge } from '@/components/ui/Badge'
import { Button } from '@/components/ui/Button'
import { Card } from '@/components/ui/Card'
import { Table } from '@/components/ui/Table'
import { api, call, type components } from '@/lib/api'
import { formatDate, formatKg } from '@/lib/format'

type StockRow = components['schemas']['StockRow']
type Shortage = components['schemas']['ShortageOut']

export default function YarnStock() {
  // query keys start with the area name so live "stock" events refresh this screen
  const stock = useQuery({ queryKey: ['stock'], queryFn: () => call(api.GET('/api/stock')) })
  const shortages = useQuery({ queryKey: ['insights', 'shortages'], queryFn: () => call(api.GET('/api/insights/shortages')) })

  return (
    <>
      <PageHeader title="Yarn stock" description="What is on the shelf, what open orders need, and what is free. Updates live." />
      <QueryBoundary query={stock}>
        {(rows) =>
          rows.length === 0 ? (
            <EmptyState title="No yarn types yet" description="The owner adds yarn types under Master data. Received lots appear here." />
          ) : (
            <div className="stack">
              <Summary rows={rows} />
              <Reveal>
                <StockTable rows={rows} />
              </Reveal>
              <Reveal>
                <Reorder shortages={shortages} />
              </Reveal>
            </div>
          )
        }
      </QueryBoundary>
    </>
  )
}

function Summary({ rows }: { rows: StockRow[] }) {
  const below = rows.filter((r) => r.below_reorder).length
  const onHand = rows.reduce((sum, r) => sum + r.on_hand_kg, 0)
  return (
    <AnimatedGroup className="grid-cards">
      <KpiCard label="Yarn types" value={rows.length} />
      <KpiCard label="On hand" value={onHand} format={formatKg} />
      <KpiCard label="Need reordering" value={below} tone={below > 0 ? 'danger' : undefined} hint={below > 0 ? 'free stock is below the reorder level' : 'all above their reorder level'} />
    </AnimatedGroup>
  )
}

function StockTable({ rows }: { rows: StockRow[] }) {
  return (
    <Table>
      <thead>
        <tr>
          <th>Yarn type</th>
          <th className="num">On hand</th>
          <th className="num">Needed by orders</th>
          <th className="num">Free</th>
          <th className="num">Reorder level</th>
          <th>Status</th>
        </tr>
      </thead>
      <tbody>
        {rows.map((r) => (
          <tr key={r.yarn_type.id}>
            <td>
              <strong>{r.yarn_type.name}</strong>
              <div className="muted text-sm">
                {r.yarn_type.code} · {r.yarn_type.colour}
              </div>
            </td>
            <td className="num">{formatKg(r.on_hand_kg)}</td>
            <td className="num">{formatKg(r.outstanding_kg)}</td>
            <td className="num">
              <span className={r.free_kg < 0 ? 'text-danger' : undefined}>{formatKg(r.free_kg)}</span>
            </td>
            <td className="num">{formatKg(r.reorder_level_kg)}</td>
            <td>{r.below_reorder ? <Badge tone="red">Reorder now</Badge> : <Badge tone="green">OK</Badge>}</td>
          </tr>
        ))}
      </tbody>
    </Table>
  )
}

function Reorder({ shortages }: { shortages: ReturnType<typeof useQuery<Shortage[]>> }) {
  return (
    <Card title="Reorder suggestions">
      {shortages.isError ? (
        // the stock table above stays usable; only this card reports the problem
        <div className="stack-sm">
          <Alert tone="error">Could not load the reorder suggestions.</Alert>
          <div>
            <Button variant="secondary" onClick={() => void shortages.refetch()}>
              Retry
            </Button>
          </div>
        </div>
      ) : (
        <QueryBoundary query={shortages} rows={2}>
          {(list) =>
            list.length === 0 ? (
              <p className="muted">Nothing needs ordering right now.</p>
            ) : (
              <div className="stack">
                {list.map((s) => (
                  <div key={s.yarn_type.id} className="shortage">
                    <div>
                      <strong>
                        Order {formatKg(s.suggested_kg)} of {s.yarn_type.name}
                      </strong>
                      <div className="muted text-sm">
                        {s.supplier ? `from ${s.supplier.name}` : 'no supplier on record'}
                        {s.order_by ? `, by ${formatDate(s.order_by)}` : ''}
                      </div>
                    </div>
                    {s.overdue_days > 0 && <Badge tone="red">{s.overdue_days} days late</Badge>}
                  </div>
                ))}
              </div>
            )
          }
        </QueryBoundary>
      )}
    </Card>
  )
}
