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

type Row = components['schemas']['ReceivableRow']

const sum = (rows: Row[], key: 'total' | 'paid' | 'balance') => rows.reduce((t, r) => t + r[key], 0)

export default function Receivables() {
  const rows = useQuery({ queryKey: ['money', 'receivables'], queryFn: () => call(api.GET('/api/money/receivables')) })
  const [paying, setPaying] = useState<Row | null>(null)

  return (
    <>
      <PageHeader eyebrow="Money" title="Receivables" description="What buyers owe us, invoice by invoice. Record a payment when money arrives." />
      <QueryBoundary query={rows}>
        {(list) =>
          list.length === 0 ? (
            <EmptyState title="No invoices yet" description="An invoice appears here when a dispatch is sent." />
          ) : (
            <div className="stack">
              <AnimatedGroup className="grid-cards">
                <KpiCard label="Invoiced" value={sum(list, 'total')} format={formatMoney} />
                <KpiCard label="Received" value={sum(list, 'paid')} format={formatMoney} />
                <KpiCard label="Still to receive" value={sum(list, 'balance')} format={formatMoney} tone={sum(list, 'balance') > 0 ? 'danger' : undefined} />
              </AnimatedGroup>
              <Reveal>
                <Table>
                  <thead>
                    <tr>
                      <th>Invoice</th>
                      <th>Buyer</th>
                      <th>Issued</th>
                      <th className="num">Total</th>
                      <th className="num">Received</th>
                      <th className="num">Balance</th>
                      <th>Status</th>
                      <th>
                        <span className="sr-only">Actions</span>
                      </th>
                    </tr>
                  </thead>
                  <tbody>
                    {list.map((r) => (
                      <tr key={r.invoice_no}>
                        <td>
                          <Link to={`/invoices/${r.invoice_no}`} className="code">
                            {r.invoice_no}
                          </Link>
                        </td>
                        <td>{r.buyer.name}</td>
                        <td>{formatDate(r.issued_at)}</td>
                        <td className="num">{formatMoney(r.total)}</td>
                        <td className="num">{formatMoney(r.paid)}</td>
                        <td className="num">
                          <strong>{formatMoney(r.balance)}</strong>
                        </td>
                        <td>
                          <PaidBadge row={r} />
                        </td>
                        <td>
                          {r.balance > 0 && (
                            <Button variant="secondary" onClick={() => setPaying(r)} aria-label={`Record payment for ${r.invoice_no}`}>
                              Record payment
                            </Button>
                          )}
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
          title="Record a payment from a buyer"
          subject={`${paying.invoice_no} · ${paying.buyer.name}`}
          balance={paying.balance}
          dateLabel="Received on"
          invalidate={[['money'], ['invoices', paying.invoice_no]]}
          send={(v) =>
            call(api.POST('/api/payments/buyer', { body: { invoice_no: paying.invoice_no, amount: v.amount, received_on: v.date, ...(v.reference ? { reference: v.reference } : {}) } }))
          }
          successMessage={(v) => `${formatMoney(v.amount)} recorded for ${paying.invoice_no}`}
          onClose={() => setPaying(null)}
        />
      )}
    </>
  )
}

function PaidBadge({ row }: { row: { paid: number; balance: number } }) {
  if (row.balance <= 0) return <Badge tone="green">Paid</Badge>
  if (row.paid > 0) return <Badge tone="amber">Part paid</Badge>
  return <Badge tone="gray">Unpaid</Badge>
}
