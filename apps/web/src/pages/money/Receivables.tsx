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
import { useI18n } from '@/i18n/I18nContext'
import { api, call, type components } from '@/lib/api'
import { formatDate, formatMoney } from '@/lib/format'
import { PaymentDialog } from './PaymentDialog'

type Row = components['schemas']['ReceivableRow']

const sum = (rows: Row[], key: 'total' | 'paid' | 'balance') => rows.reduce((t, r) => t + r[key], 0)

export default function Receivables() {
  const { t } = useI18n()
  const rows = useQuery({ queryKey: ['money', 'receivables'], queryFn: () => call(api.GET('/api/money/receivables')) })
  const [paying, setPaying] = useState<Row | null>(null)

  return (
    <>
      <PageHeader eyebrow={t('nav.group.Money')} title={t('nav.receivables')} description={t('money.recv.description')} />
      <QueryBoundary query={rows}>
        {(list) =>
          list.length === 0 ? (
            <EmptyState title={t('money.recv.emptyTitle')} description={t('money.recv.emptyDescription')} />
          ) : (
            <div className="stack">
              <AnimatedGroup className="grid-cards">
                <KpiCard label={t('money.invoiced')} value={sum(list, 'total')} format={formatMoney} />
                <KpiCard label={t('money.received')} value={sum(list, 'paid')} format={formatMoney} />
                <KpiCard label={t('money.toReceive')} value={sum(list, 'balance')} format={formatMoney} tone={sum(list, 'balance') > 0 ? 'danger' : undefined} />
              </AnimatedGroup>
              <Reveal>
                <Table>
                  <thead>
                    <tr>
                      <th>{t('money.col.invoice')}</th>
                      <th>{t('qc.col.buyer')}</th>
                      <th>{t('money.col.issued')}</th>
                      <th className="num">{t('money.col.total')}</th>
                      <th className="num">{t('money.received')}</th>
                      <th className="num">{t('money.col.balance')}</th>
                      <th>{t('qc.col.status')}</th>
                      <th>
                        <span className="sr-only">{t('money.actions')}</span>
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
                            <Button variant="secondary" onClick={() => setPaying(r)} aria-label={t('money.recordFor', { no: r.invoice_no })}>
                              {t('money.recordPayment')}
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
          title={t('money.dialogBuyer')}
          subject={`${paying.invoice_no} · ${paying.buyer.name}`}
          balance={paying.balance}
          dateLabel={t('money.receivedOn')}
          invalidate={[['money'], ['invoices', paying.invoice_no]]}
          send={(v) =>
            call(api.POST('/api/payments/buyer', { body: { invoice_no: paying.invoice_no, amount: v.amount, received_on: v.date, ...(v.reference ? { reference: v.reference } : {}) } }))
          }
          successMessage={(v) => t('money.recvToast', { amount: formatMoney(v.amount), no: paying.invoice_no })}
          onClose={() => setPaying(null)}
        />
      )}
    </>
  )
}

function PaidBadge({ row }: { row: { paid: number; balance: number } }) {
  const { t } = useI18n()
  if (row.balance <= 0) return <Badge tone="green">{t('money.paid')}</Badge>
  if (row.paid > 0) return <Badge tone="amber">{t('money.partPaid')}</Badge>
  return <Badge tone="gray">{t('money.unpaid')}</Badge>
}
