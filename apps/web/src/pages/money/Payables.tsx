import { useQuery } from '@tanstack/react-query'
import { useState } from 'react'
import { Link } from 'react-router-dom'
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
import { formatDate, formatMoney } from '@/lib/format'
import { PaymentDialog } from './PaymentDialog'

type Row = components['schemas']['PayableRow']

export default function Payables() {
  const rows = useQuery({ queryKey: ['money', 'payables'], queryFn: () => call(api.GET('/api/money/payables')) })
  const [paying, setPaying] = useState<Row | null>(null)

  return (
    <>
      <PageHeader eyebrow="Money" title="Payables" description="What we owe suppliers for yarn, bill by bill. Overdue bills come first." />
      <QueryBoundary query={rows}>
        {(list) => {
          if (list.length === 0) return <EmptyState title="No supplier bills yet" description="A bill appears here when yarn is received with a bill." />
          // overdue first, then the earliest due date: the order a clerk would pay in
          const sorted = [...list].sort((a, b) => Number(b.overdue) - Number(a.overdue) || a.due_date.localeCompare(b.due_date))
          const owed = list.reduce((t, r) => t + r.balance, 0)
          const overdue = list.filter((r) => r.overdue).reduce((t, r) => t + r.balance, 0)
          return (
            <div className="stack">
              <AnimatedGroup className="grid-cards">
                <KpiCard label="Still to pay" value={owed} format={formatMoney} />
                <KpiCard label="Overdue" value={overdue} format={formatMoney} tone={overdue > 0 ? 'danger' : undefined} hint={overdue > 0 ? 'pay these first' : 'none'} />
              </AnimatedGroup>
              <Reveal>
                <Table>
                  <thead>
                    <tr>
                      <th>Bill</th>
                      <th>Supplier</th>
                      <th>Yarn lot</th>
                      <th>Due</th>
                      <th className="num">Amount</th>
                      <th className="num">Paid</th>
                      <th className="num">Balance</th>
                      <th>
                        <span className="sr-only">Actions</span>
                      </th>
                    </tr>
                  </thead>
                  <tbody>
                    {sorted.map((r) => (
                      <tr key={r.bill_id}>
                        <td>
                          <span className="code-text">{r.bill_no}</span>
                          <div className="muted text-sm">{formatDate(r.bill_date)}</div>
                        </td>
                        <td>{r.supplier.name}</td>
                        <td>
                          <Link to={`/store/lots/${r.lot_code}`}>{r.lot_code}</Link>
                        </td>
                        <td>
                          {formatDate(r.due_date)}
                          {r.overdue && (
                            <div>
                              <Badge tone="red">Overdue</Badge>
                            </div>
                          )}
                        </td>
                        <td className="num">{formatMoney(r.amount)}</td>
                        <td className="num">{formatMoney(r.paid)}</td>
                        <td className="num">
                          <strong>{formatMoney(r.balance)}</strong>
                        </td>
                        <td>
                          {r.balance > 0 ? (
                            <Button variant="secondary" onClick={() => setPaying(r)} aria-label={`Record payment for bill ${r.bill_no}`}>
                              Record payment
                            </Button>
                          ) : (
                            <Badge tone="green">Paid</Badge>
                          )}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </Table>
              </Reveal>
            </div>
          )
        }}
      </QueryBoundary>
      {paying && (
        <PaymentDialog
          title="Record a payment to a supplier"
          subject={`Bill ${paying.bill_no} · ${paying.supplier.name}`}
          balance={paying.balance}
          dateLabel="Paid on"
          invalidate={[['money']]}
          send={(v) =>
            call(api.POST('/api/payments/supplier', { body: { bill_id: paying.bill_id, amount: v.amount, paid_on: v.date, ...(v.reference ? { reference: v.reference } : {}) } }))
          }
          successMessage={(v) => `${formatMoney(v.amount)} paid to ${paying.supplier.name}`}
          onClose={() => setPaying(null)}
        />
      )}
    </>
  )
}
