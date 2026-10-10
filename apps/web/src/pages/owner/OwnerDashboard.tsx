import { useQuery } from '@tanstack/react-query'
import { useState } from 'react'
import { MonthSummary } from '@/components/ai/Drafts'
import { Alert } from '@/components/common/Alert'
import { EmptyState } from '@/components/common/EmptyState'
import { KpiCard } from '@/components/common/KpiCard'
import { PageHeader } from '@/components/common/PageHeader'
import { QueryBoundary } from '@/components/common/QueryBoundary'
import { RevenueCostChart } from '@/components/common/RevenueCostChart'
import { AnimatedGroup } from '@/components/motion/AnimatedGroup'
import { Reveal } from '@/components/motion/Reveal'
import { Table } from '@/components/ui/Table'
import { api, call, type components } from '@/lib/api'
import { todayIso } from '@/lib/dates'
import { formatLakh, formatMoney, formatPercent, formatQty } from '@/lib/format'
import { machineUse } from '@/lib/ownerReport'

type Report = components['schemas']['MonthReport']

const monthName = (month: string) => new Date(`${month}-01T00:00:00`).toLocaleDateString('en-IN', { month: 'long', year: 'numeric' })
const STAGE: Record<string, string> = { spinning: 'Spinning', weaving: 'Weaving', dyeing: 'Dyeing' }

export default function OwnerDashboard() {
  const [month, setMonth] = useState(() => todayIso().slice(0, 7))
  // the key starts with "owner", so payment and attendance events from the live stream refetch it
  const report = useQuery({ queryKey: ['owner', 'month', month], queryFn: () => call(api.GET('/api/reports/month', { params: { query: { month } } })) })

  return (
    <>
      <PageHeader
        eyebrow={`Owner · ${monthName(month)}`}
        title="Month-end"
        description="Profit, cash, machines and idle labour for the month."
        actions={
          <label className="month-picker">
            <span className="muted text-sm">Month</span>
            <input type="month" className="input" value={month} max={todayIso().slice(0, 7)} onChange={(e) => e.target.value && setMonth(e.target.value)} />
          </label>
        }
      />
      <QueryBoundary query={report}>{(r) => <Report report={r} month={month} />}</QueryBoundary>
    </>
  )
}

function Report({ report: r, month }: { report: Report; month: string }) {
  const use = machineUse(r.machines)
  const p = r.profit
  const c = r.cash
  return (
    <div className="stack">
      {r.warnings.length > 0 && (
        <Alert tone="info">
          <strong>Check before you rely on these numbers:</strong>
          <ul className="plain-list">
            {r.warnings.map((w) => (
              <li key={w}>{w}</li>
            ))}
          </ul>
        </Alert>
      )}

      <AnimatedGroup className="grid-cards">
        <KpiCard label="Net profit" value={p.profit} format={formatLakh} tone={p.profit < 0 ? 'danger' : undefined} hint={`${formatMoney(p.invoiced)} invoiced`} />
        <KpiCard label="Cash on hand" value={c.net_cash} format={formatLakh} tone={c.net_cash < 0 ? 'danger' : undefined} hint="Received minus paid out this month" />
        <KpiCard label="Machine use" value={use * 100} format={(n) => `${Math.round(n)}%`} hint="Share of machine time spent running" />
        <KpiCard label="Idle labour" value={p.idle_labour} format={formatMoney} hint="Wages paid while machines stood idle" />
      </AnimatedGroup>

      <Reveal>
        <section className="card" aria-label="Summary for the owner">
          <div className="card-body">
            <MonthSummary key={month} month={month} />
          </div>
        </section>
      </Reveal>

      <Reveal>
        <section className="card" aria-label="Revenue, cost and profit by order">
          <div className="card-header">
            <h2 className="card-title">Revenue and cost by order</h2>
          </div>
          <div className="card-body">
            {r.orders.length === 0 ? (
              <EmptyState title="No orders this month" description="Orders that were invoiced or worked on in this month appear here." />
            ) : (
              <RevenueCostChart
                data={r.orders.map((o) => ({ label: o.order_code, revenue: o.revenue, cost: o.cost, profit: o.profit }))}
                caption={`Revenue and cost for ${r.orders.length} order${r.orders.length === 1 ? '' : 's'}, with the profit or loss of each`}
              />
            )}
          </div>
        </section>
      </Reveal>

      <div className="grid-two">
        <Reveal>
          <section className="card" aria-label="Where the money went">
            <div className="card-header">
              <h2 className="card-title">Where the money went</h2>
            </div>
            <dl className="card-body ledger">
              <Row label="Invoiced to buyers" value={p.invoiced} />
              <Row label="Yarn used" value={-p.yarn_issued} />
              <Row label="Wages earned" value={-p.wages_earned} note={`of which ${formatMoney(p.idle_labour)} was idle labour`} />
              <Row label="Machine running cost" value={-p.machine_running_cost} />
              <Row label="Stock written off" value={-p.stock_writeoffs} />
              <Row label="Net profit" value={p.profit} total />
            </dl>
          </section>
        </Reveal>
        <Reveal delay={0.05}>
          <section className="card" aria-label="Cash">
            <div className="card-header">
              <h2 className="card-title">Cash</h2>
            </div>
            <dl className="card-body ledger">
              <Row label="Received from buyers" value={c.received_from_buyers} />
              <Row label="Paid to suppliers" value={-c.paid_to_suppliers} />
              <Row label="Wages paid" value={-c.paid_wages} />
              <Row label="Cash on hand" value={c.net_cash} total />
              <Row label="Buyers still owe" value={c.receivables_outstanding} muted />
              <Row label="We still owe suppliers" value={c.payables_outstanding} muted />
            </dl>
          </section>
        </Reveal>
      </div>

      <Reveal>
        <section className="stack-sm" aria-label="Machines">
          <h2>Machines</h2>
          {r.machines.length === 0 ? (
            <EmptyState title="No machine hours this month" />
          ) : (
            <Table>
              <thead>
                <tr>
                  <th>Machine</th>
                  <th>Stage</th>
                  <th className="num">Output</th>
                  <th className="num">Running</th>
                  <th className="num">Idle</th>
                  <th className="num">Down</th>
                  <th className="num">Capacity lost</th>
                </tr>
              </thead>
              <tbody>
                {r.machines.map((m) => (
                  <tr key={m.code}>
                    <td>
                      <span className="code-text">{m.name}</span>
                      <div className="muted text-sm">{m.code}</div>
                    </td>
                    <td>{STAGE[m.stage]}</td>
                    <td className="num">{formatQty(m.output, m.output_unit)}</td>
                    <td className="num">{m.running_h} h</td>
                    <td className="num">{m.idle_h} h</td>
                    <td className="num">{m.down_h > 0 ? <span className="text-danger">{m.down_h} h</span> : '0 h'}</td>
                    <td className="num">{formatQty(m.lost_capacity, m.lost_capacity_unit)}</td>
                  </tr>
                ))}
              </tbody>
            </Table>
          )}
          <p className="muted text-sm">Overall, machines ran {formatPercent(use)} of the time.</p>
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
