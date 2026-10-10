import { useQuery } from '@tanstack/react-query'
import { Plus, Search } from 'lucide-react'
import { useState } from 'react'
import { Link } from 'react-router-dom'
import { EmptyState } from '@/components/common/EmptyState'
import { PageHeader } from '@/components/common/PageHeader'
import { QueryBoundary } from '@/components/common/QueryBoundary'
import { StageBar, StageLegend } from '@/components/common/StageBar'
import { AnimatedBackground } from '@/components/motion/AnimatedBackground'
import { Reveal } from '@/components/motion/Reveal'
import { Badge } from '@/components/ui/Badge'
import { Button } from '@/components/ui/Button'
import { ProgressBar } from '@/components/ui/ProgressBar'
import { Table } from '@/components/ui/Table'
import type { Key } from '@/i18n/en'
import { useI18n } from '@/i18n/I18nContext'
import { api, call, type components } from '@/lib/api'
import { useMe } from '@/lib/auth'
import { formatDate, formatKg, formatMetres } from '@/lib/format'
import { matchesSearch } from '@/lib/orderSearch'

type Order = components['schemas']['OrderOut']

const FILTERS = ['All', 'Active', 'Late', 'Drafts'] as const
type Filter = (typeof FILTERS)[number]

const isLate = (o: Order) => (o.days_late ?? 0) > 0
const MATCH: Record<Filter, (o: Order) => boolean> = {
  All: () => true,
  Active: (o) => o.state === 'confirmed' && o.stage !== 'dispatched',
  Late: isLate,
  Drafts: (o) => o.state === 'draft',
}

export default function OrdersList() {
  const { t } = useI18n()
  const orders = useQuery({ queryKey: ['orders'], queryFn: () => call(api.GET('/api/orders')) })
  const me = useMe()
  const [filter, setFilter] = useState<Filter>('All')
  const [query, setQuery] = useState('')
  const canCreate = me.data?.role === 'owner' || me.data?.role === 'accountant'

  return (
    <>
      <PageHeader
        eyebrow={t('nav.group.Production')}
        title={t('nav.orders')}
        description={t('orders.description')}
        actions={
          canCreate && (
            <Link to="/orders/new">
              <Button>
                <Plus size={16} aria-hidden /> {t('orders.new')}
              </Button>
            </Link>
          )
        }
      />
      <QueryBoundary query={orders}>
        {(all) =>
          all.length === 0 ? (
            <EmptyState
              title={t('portal.emptyTitle')}
              description={t('orders.emptyDescription')}
              action={
                canCreate && (
                  <Link to="/orders/new">
                    <Button>{t('orders.new')}</Button>
                  </Link>
                )
              }
            />
          ) : (
            <div className="stack">
              <div className="pill-tabs">
                <AnimatedBackground defaultValue="All" onValueChange={(id) => id && setFilter(id as Filter)} className="pill-highlight">
                  {FILTERS.map((f) => (
                    <button key={f} type="button" data-id={f} className="pill-tab">
                      {t(`orders.filter.${f}` as Key)}{' '}
                      <span className="pill-count">{all.filter(MATCH[f]).length}</span>
                    </button>
                  ))}
                </AnimatedBackground>
              </div>
              <label className="orders-search">
                <Search size={16} aria-hidden />
                <input
                  type="search"
                  className="input"
                  aria-label={t('orders.findAria')}
                  placeholder={t('orders.findPlaceholder')}
                  value={query}
                  onChange={(e) => setQuery(e.target.value)}
                />
              </label>
              <StageLegend />
              <Reveal>
                <OrdersTable orders={all.filter(MATCH[filter]).filter((o) => matchesSearch(o, query))} searching={query.trim() !== ''} />
              </Reveal>
            </div>
          )
        }
      </QueryBoundary>
    </>
  )
}

function OrdersTable({ orders, searching }: { orders: Order[]; searching: boolean }) {
  const { t } = useI18n()
  if (orders.length === 0) return <EmptyState title={searching ? t('orders.noMatchSearch') : t('orders.noMatchFilter')} description={searching ? t('orders.noMatchSearchHint') : undefined} />
  return (
    <Table>
      <thead>
        <tr>
          <th>{t('qc.col.order')}</th>
          <th>{t('qc.col.fabric')}</th>
          <th className="num">{t('orders.col.quantity')}</th>
          <th>{t('common.stage')}</th>
          <th style={{ minWidth: 160 }}>{t('orders.col.passedQc')}</th>
          <th>{t('passport.yarn')}</th>
          <th>{t('orders.col.deadline')}</th>
        </tr>
      </thead>
      <tbody>
        {orders.map((o) => (
          <tr key={o.code}>
            <td>
              <Link to={`/orders/${o.code}`} className="code">
                {o.code}
              </Link>
              <div className="muted text-sm">{o.buyer.name}</div>
            </td>
            <td>
              {o.fabric_type.name}
              <div className="muted text-sm">{o.colour}</div>
            </td>
            <td className="num">{formatMetres(o.qty_metres)}</td>
            <td>
              <StageBar stage={o.stage} />
            </td>
            <td>
              <ProgressBar label={t('orders.passedLabel', { code: o.code })} value={o.progress.passed_m} max={o.qty_metres} unit="m" />
            </td>
            <td>
              <YarnChip order={o} />
            </td>
            <td>
              {formatDate(o.deadline)}
              {isLate(o) && (
                <div>
                  <Badge tone="red">{t('insight.daysLate', { days: o.days_late ?? 0 })}</Badge>
                </div>
              )}
            </td>
          </tr>
        ))}
      </tbody>
    </Table>
  )
}

function YarnChip({ order }: { order: Order }) {
  const { t } = useI18n()
  if (order.state !== 'confirmed' && order.yarn_status !== 'short') return <span className="muted">-</span>
  if (order.yarn_status === 'short') return <Badge tone="red">{t('orders.yarnShort', { qty: formatKg(order.short_kg) })}</Badge>
  if (order.yarn_status === 'can_start') return <Badge tone="green">{t('orders.yarnReady')}</Badge>
  return <span className="muted">-</span>
}
