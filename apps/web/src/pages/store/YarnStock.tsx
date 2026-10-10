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
import { useI18n } from '@/i18n/I18nContext'
import { api, call, type components } from '@/lib/api'
import { formatDate, formatKg } from '@/lib/format'

type StockRow = components['schemas']['StockRow']
type Shortage = components['schemas']['ShortageOut']

export default function YarnStock() {
  const { t } = useI18n()
  // query keys start with the area name so live "stock" events refresh this screen
  const stock = useQuery({ queryKey: ['stock'], queryFn: () => call(api.GET('/api/stock')) })
  const shortages = useQuery({ queryKey: ['insights', 'shortages'], queryFn: () => call(api.GET('/api/insights/shortages')) })

  return (
    <>
      <PageHeader title={t('nav.stock')} description={t('store.stock.description')} />
      <QueryBoundary query={stock}>
        {(rows) =>
          rows.length === 0 ? (
            <EmptyState title={t('store.stock.emptyTitle')} description={t('store.stock.emptyDescription')} />
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
  const { t } = useI18n()
  const below = rows.filter((r) => r.below_reorder).length
  const onHand = rows.reduce((sum, r) => sum + r.on_hand_kg, 0)
  return (
    <AnimatedGroup className="grid-cards">
      <KpiCard label={t('store.stock.kpiTypes')} value={rows.length} />
      <KpiCard label={t('store.stock.onHand')} value={onHand} format={formatKg} />
      <KpiCard label={t('store.stock.needReorder')} value={below} tone={below > 0 ? 'danger' : undefined} hint={below > 0 ? t('store.stock.hintBelow') : t('store.stock.hintOk')} />
    </AnimatedGroup>
  )
}

function StockTable({ rows }: { rows: StockRow[] }) {
  const { t } = useI18n()
  return (
    <Table>
      <thead>
        <tr>
          <th>{t('store.receive.yarnType')}</th>
          <th className="num">{t('store.stock.onHand')}</th>
          <th className="num">{t('store.stock.neededByOrders')}</th>
          <th className="num">{t('store.stock.free')}</th>
          <th className="num">{t('store.stock.reorderLevel')}</th>
          <th>{t('qc.col.status')}</th>
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
            <td>{r.below_reorder ? <Badge tone="red">{t('store.stock.reorderNow')}</Badge> : <Badge tone="green">{t('store.stock.ok')}</Badge>}</td>
          </tr>
        ))}
      </tbody>
    </Table>
  )
}

function Reorder({ shortages }: { shortages: ReturnType<typeof useQuery<Shortage[]>> }) {
  const { t } = useI18n()
  return (
    <Card title={t('store.stock.suggestions')}>
      {shortages.isError ? (
        // the stock table above stays usable; only this card reports the problem
        <div className="stack-sm">
          <Alert tone="error">{t('store.stock.loadError')}</Alert>
          <div>
            <Button variant="secondary" onClick={() => void shortages.refetch()}>
              {t('store.stock.retry')}
            </Button>
          </div>
        </div>
      ) : (
        <QueryBoundary query={shortages} rows={2}>
          {(list) =>
            list.length === 0 ? (
              <p className="muted">{t('store.stock.nothingToOrder')}</p>
            ) : (
              <div className="stack">
                {list.map((s) => (
                  <div key={s.yarn_type.id} className="shortage">
                    <div>
                      <strong>
                        {t('store.stock.orderQty', { qty: formatKg(s.suggested_kg), yarn: s.yarn_type.name })}
                      </strong>
                      <div className="muted text-sm">
                        {s.supplier ? t('store.stock.fromSupplier', { supplier: s.supplier.name }) : t('store.stock.noSupplier')}
                        {s.order_by ? t('store.stock.orderBy', { date: formatDate(s.order_by) }) : ''}
                      </div>
                    </div>
                    {s.overdue_days > 0 && <Badge tone="red">{t('store.stock.daysLate', { days: s.overdue_days })}</Badge>}
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
