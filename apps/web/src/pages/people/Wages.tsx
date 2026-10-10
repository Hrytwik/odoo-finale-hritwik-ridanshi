import { useQuery } from '@tanstack/react-query'
import { useState } from 'react'
import { EmptyState } from '@/components/common/EmptyState'
import { KpiCard } from '@/components/common/KpiCard'
import { PageHeader } from '@/components/common/PageHeader'
import { QueryBoundary } from '@/components/common/QueryBoundary'
import { AnimatedGroup } from '@/components/motion/AnimatedGroup'
import { Reveal } from '@/components/motion/Reveal'
import { Badge } from '@/components/ui/Badge'
import { Button } from '@/components/ui/Button'
import { Table } from '@/components/ui/Table'
import { api, call, type components } from '@/lib/api'
import { todayIso } from '@/lib/dates'
import { formatMoney } from '@/lib/format'
import { PaymentDialog } from '@/pages/money/PaymentDialog'

type Row = components['schemas']['WageRow']

const monthName = (month: string) => new Date(`${month}-01T00:00:00`).toLocaleDateString('en-IN', { month: 'long', year: 'numeric' })
const lastDay = (month: string) => {
  const [y, m] = month.split('-').map(Number)
  return `${month}-${String(new Date(y, m, 0).getDate()).padStart(2, '0')}`
}

/** What each worker earned from attendance this month, what has been paid, and what is still owed. */
export default function Wages() {
  const [month, setMonth] = useState(() => todayIso().slice(0, 7))
  const [paying, setPaying] = useState<Row | null>(null)
  const sheet = useQuery({ queryKey: ['people', 'wages', month], queryFn: () => call(api.GET('/api/wages', { params: { query: { month } } })) })

  return (
    <>
      <PageHeader
        eyebrow="People"
        title="Wages"
        description="Earned from attendance: a full day pays the daily wage, a half day pays half. Pay what is owed, never more."
        actions={
          <label className="month-picker">
            <span className="muted text-sm">Month</span>
            <input type="month" className="input" value={month} max={todayIso().slice(0, 7)} onChange={(e) => e.target.value && setMonth(e.target.value)} />
          </label>
        }
      />
      <QueryBoundary query={sheet}>
        {(s) =>
          s.rows.length === 0 ? (
            <EmptyState title="No workers on the payroll" description="Add workers under People to see their wages here." />
          ) : (
            <div className="stack">
              <AnimatedGroup className="grid-cards">
                <KpiCard label="Earned" value={s.total_earned} format={formatMoney} />
                <KpiCard label="Paid" value={s.total_paid} format={formatMoney} />
                <KpiCard label="Still owed" value={s.total_owed} format={formatMoney} tone={s.total_owed > 0 ? 'danger' : undefined} />
              </AnimatedGroup>
              <Reveal>
                <Table>
                  <thead>
                    <tr>
                      <th>Worker</th>
                      <th className="num">Present</th>
                      <th className="num">Half days</th>
                      <th className="num">Absent</th>
                      <th className="num">Daily wage</th>
                      <th className="num">Earned</th>
                      <th className="num">Paid</th>
                      <th className="num">Owed</th>
                      <th>
                        <span className="sr-only">Actions</span>
                      </th>
                    </tr>
                  </thead>
                  <tbody>
                    {s.rows.map((r) => (
                      <tr key={r.worker_id}>
                        <td>
                          <span className="code-text">{r.worker_name}</span>
                          <div className="muted text-sm">{r.worker_code}</div>
                        </td>
                        <td className="num">{r.present}</td>
                        <td className="num">{r.half_days}</td>
                        <td className="num">{r.absent}</td>
                        <td className="num">{formatMoney(r.daily_wage)}</td>
                        <td className="num">{formatMoney(r.earned)}</td>
                        <td className="num">{formatMoney(r.paid)}</td>
                        <td className="num">
                          <strong>{formatMoney(r.owed)}</strong>
                        </td>
                        <td>
                          {r.owed > 0 ? (
                            <Button variant="secondary" onClick={() => setPaying(r)} aria-label={`Record payment for ${r.worker_name}`}>
                              Record payment
                            </Button>
                          ) : r.earned > 0 ? (
                            <Badge tone="green">Paid</Badge>
                          ) : null}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </Table>
              </Reveal>
            </div>
          )
        }
      </QueryBoundary>
      {paying && (
        <PaymentDialog
          title="Record a wage payment"
          subject={`${paying.worker_name} · wages for ${monthName(month)}`}
          balance={paying.owed}
          dateLabel="Paid on"
          invalidate={[['people'], ['owner']]}
          send={(v) =>
            call(api.POST('/api/payments/wages', { body: { worker_id: paying.worker_id, period_start: `${month}-01`, period_end: lastDay(month), amount: v.amount, paid_at: v.date } }))
          }
          successMessage={(v) => `${formatMoney(v.amount)} paid to ${paying.worker_name}`}
          onClose={() => setPaying(null)}
        />
      )}
    </>
  )
}
