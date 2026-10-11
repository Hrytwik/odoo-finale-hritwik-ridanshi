import { useQuery } from '@tanstack/react-query'
import { useState } from 'react'
import { MonthSummary } from '@/components/ai/Drafts'
import { EmptyState } from '@/components/common/EmptyState'
import { KpiCard } from '@/components/common/KpiCard'
import { PageHeader } from '@/components/common/PageHeader'
import { QueryBoundary } from '@/components/common/QueryBoundary'
import { RevenueCostChart } from '@/components/common/RevenueCostChart'
import { AnimatedGroup } from '@/components/motion/AnimatedGroup'
import { Reveal } from '@/components/motion/Reveal'
import { Table } from '@/components/ui/Table'
import type { Key } from '@/i18n/en'
import { useI18n } from '@/i18n/I18nContext'
import { api, call, type components } from '@/lib/api'
import { todayIso } from '@/lib/dates'
import { formatLakh, formatLocale, formatMoney, formatPercent, formatQty } from '@/lib/format'
import { machineUse } from '@/lib/ownerReport'
import { DataChecks } from './DataChecks'

type Report = components['schemas']['MonthReport']

const monthName = (month: string, locale: string) => new Date(`${month}-01T00:00:00`).toLocaleDateString(locale, { month: 'long', year: 'numeric' })

export default function OwnerDashboard() {
  const { t } = useI18n()
  const [month, setMonth] = useState(() => todayIso().slice(0, 7))
  // the key starts with "owner", so payment and attendance events from the live stream refetch it
  const report = useQuery({ queryKey: ['owner', 'month', month], queryFn: () => call(api.GET('/api/reports/month', { params: { query: { month } } })) })

  return (
    <>
      <PageHeader
        eyebrow={t('owner.eyebrow', { month: monthName(month, formatLocale()) })}
        title={t('nav.monthEnd')}
        description={t('owner.description')}
        actions={
          <label className="month-picker">
            <span className="muted text-sm">{t('owner.month')}</span>
            <input type="month" className="input" value={month} max={todayIso().slice(0, 7)} onChange={(e) => e.target.value && setMonth(e.target.value)} />
          </label>
        }
      />
      <QueryBoundary query={report}>{(r) => <Report report={r} month={month} />}</QueryBoundary>
    </>
  )
}

function Report({ report: r, month }: { report: Report; month: string }) {
  const { t } = useI18n()
  const use = machineUse(r.machines)
  const p = r.profit
  const c = r.cash
  return (
    <div className="stack">
      <DataChecks warnings={r.warnings} />

      <AnimatedGroup className="grid-cards">
        <KpiCard label={t('owner.netProfit')} value={p.profit} format={formatLakh} tone={p.profit < 0 ? 'danger' : undefined} hint={t('owner.invoicedHint', { amount: formatMoney(p.invoiced) })} />
        <KpiCard label={t('owner.cashOnHand')} value={c.net_cash} format={formatLakh} tone={c.net_cash < 0 ? 'danger' : undefined} hint={t('owner.cashHint')} />
        <KpiCard label={t('owner.machineUse')} value={use * 100} format={(n) => `${Math.round(n)}%`} hint={t('owner.machineHint')} />
        <KpiCard label={t('owner.idleLabour')} value={p.idle_labour} format={formatMoney} hint={t('owner.idleHint')} />
      </AnimatedGroup>

      <Reveal>
        <section className="card" aria-label={t('owner.summaryAria')}>
          <div className="card-body">
            <MonthSummary key={month} month={month} />
          </div>
        </section>
      </Reveal>

      <Reveal>
        <section className="card" aria-label={t('owner.revAria')}>
          <div className="card-header">
            <h2 className="card-title">{t('owner.revTitle')}<span className="muted text-sm"> · {monthName(month, formatLocale())}</span></h2>
          </div>
          <div className="card-body">
            {r.orders.length === 0 ? (
              <EmptyState title={t('owner.noOrders')} description={t('owner.noOrdersDescription')} />
            ) : (
              <RevenueCostChart
                data={r.orders.map((o) => ({ label: o.order_code, revenue: o.revenue, cost: o.cost, profit: o.profit }))}
                caption={t(r.orders.length === 1 ? 'owner.chartCaption.one' : 'owner.chartCaption.many', { count: r.orders.length })}
              />
            )}
          </div>
        </section>
      </Reveal>

      <div className="grid-two">
        <Reveal>
          <section className="card" aria-label={t('owner.moneyWent')}>
            <div className="card-header">
              <h2 className="card-title">{t('owner.moneyWent')}<span className="muted text-sm"> · {monthName(month, formatLocale())}</span></h2>
            </div>
            <dl className="card-body ledger">
              <Row label={t('owner.invoiced')} value={p.invoiced} />
              <Row label={t('owner.yarnUsed')} value={-p.yarn_issued} />
              <Row label={t('owner.wagesEarned')} value={-p.wages_earned} note={t('owner.idleNote', { amount: formatMoney(p.idle_labour) })} />
              <Row label={t('owner.machineCost')} value={-p.machine_running_cost} />
              <Row label={t('owner.writeoffs')} value={-p.stock_writeoffs} />
              <Row label={t('owner.netProfit')} value={p.profit} total />
            </dl>
          </section>
        </Reveal>
        <Reveal delay={0.05}>
          <section className="card" aria-label={t('owner.cash')}>
            <div className="card-header">
              <h2 className="card-title">{t('owner.cash')}<span className="muted text-sm"> · {monthName(month, formatLocale())}</span></h2>
            </div>
            <dl className="card-body ledger">
              <Row label={t('owner.received')} value={c.received_from_buyers} />
              <Row label={t('owner.paidSuppliers')} value={-c.paid_to_suppliers} />
              <Row label={t('owner.wagesPaid')} value={-c.paid_wages} />
              <Row label={t('owner.cashOnHand')} value={c.net_cash} total />
              <Row label={t('owner.buyersOwe')} value={c.receivables_outstanding} muted />
              <Row label={t('owner.weOwe')} value={c.payables_outstanding} muted />
            </dl>
          </section>
        </Reveal>
      </div>

      <Reveal>
        <section className="stack-sm" aria-label={t('passport.machines')}>
          <h2>{t('passport.machines')}<span className="muted text-sm"> · {monthName(month, formatLocale())}</span></h2>
          {r.machines.length === 0 ? (
            <EmptyState title={t('owner.noMachineHours')} />
          ) : (
            <Table>
              <thead>
                <tr>
                  <th>{t('common.machine')}</th>
                  <th>{t('common.stage')}</th>
                  <th className="num">{t('machine.col.output')}</th>
                  <th className="num">{t('floor.running')}</th>
                  <th className="num">{t('owner.col.idle')}</th>
                  <th className="num">{t('owner.col.down')}</th>
                  <th className="num">{t('owner.col.capacityLost')}</th>
                </tr>
              </thead>
              <tbody>
                {r.machines.map((m) => (
                  <tr key={m.code}>
                    <td>
                      <span className="code-text">{m.name}</span>
                      <div className="muted text-sm">{m.code}</div>
                    </td>
                    <td>{t(`floor.stage.${m.stage}` as Key)}</td>
                    <td className="num">{formatQty(m.output, m.output_unit)}</td>
                    <td className="num">{t('owner.hours', { h: m.running_h })}</td>
                    <td className="num">{t('owner.hours', { h: m.idle_h })}</td>
                    <td className="num">{m.down_h > 0 ? <span className="text-danger">{t('owner.hours', { h: m.down_h })}</span> : t('owner.hours', { h: 0 })}</td>
                    <td className="num">{formatQty(m.lost_capacity, m.lost_capacity_unit)}</td>
                  </tr>
                ))}
              </tbody>
            </Table>
          )}
          <p className="muted text-sm">{t('owner.overall', { pct: formatPercent(use) })}</p>
        </section>
      </Reveal>
    </div>
  )
}

function Row({ label, value, note, total, muted }: { label: string; value: number; note?: string; total?: boolean; muted?: boolean }) {
  return (
    <div className={total ? 'ledger-row is-total' : muted ? 'ledger-row is-muted' : 'ledger-row'}>
      <dt>
        {label}
        {note && <span className="muted text-sm"> {note}</span>}
      </dt>
      <dd className={value < 0 && total ? 'text-danger' : undefined}>{formatMoney(value)}</dd>
    </div>
  )
}
