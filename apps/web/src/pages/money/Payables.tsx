import { useQuery } from '@tanstack/react-query'
import { useState } from 'react'
import { Link } from 'react-router-dom'
import { EmptyState } from '@/components/common/EmptyState'
import { Filtered } from '@/components/common/ListToolbar'
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

type Row = components['schemas']['PayableRow']

export default function Payables() {
  const { t } = useI18n()
  const rows = useQuery({ queryKey: ['money', 'payables'], queryFn: () => call(api.GET('/api/money/payables')) })
  const [paying, setPaying] = useState<Row | null>(null)

  return (
    <>
      <PageHeader eyebrow={t('nav.group.Money')} title={t('nav.payables')} description={t('money.pay.description')} />
      <QueryBoundary query={rows}>
        {(list) => {
          if (list.length === 0) return <EmptyState title={t('money.pay.emptyTitle')} description={t('money.pay.emptyDescription')} />
          // overdue first, then the earliest due date: the order a clerk would pay in
          const sorted = [...list].sort((a, b) => Number(b.overdue) - Number(a.overdue) || a.due_date.localeCompare(b.due_date))
          const owed = list.reduce((t, r) => t + r.balance, 0)
          const overdue = list.filter((r) => r.overdue).reduce((t, r) => t + r.balance, 0)
          return (
            <div className="stack">
              <AnimatedGroup className="grid-cards">
                <KpiCard label={t('money.toPay')} value={owed} format={formatMoney} />
                <KpiCard label={t('money.overdue')} value={overdue} format={formatMoney} tone={overdue > 0 ? 'danger' : undefined} hint={overdue > 0 ? t('money.payFirst') : t('money.none')} />
              </AnimatedGroup>
              <Reveal>
                <Filtered
                  rows={sorted}
                  options={{
                    text: (r) => `${r.bill_no} ${r.supplier.name} ${r.lot_code}`,
                    sorts: [
                      { key: 'due', label: t('money.col.due'), value: (r) => r.due_date },
                      { key: 'bill', label: t('money.col.bill'), value: (r) => r.bill_no },
                      { key: 'supplier', label: t('money.col.supplier'), value: (r) => r.supplier.name },
                      { key: 'amount', label: t('common.amount'), value: (r) => r.amount },
                      { key: 'balance', label: t('money.col.balance'), value: (r) => r.balance },
                    ],
                    filters: [
                      {
                        key: 'state',
                        label: t('qc.col.status'),
                        options: [
                          { value: 'overdue', label: t('money.overdue') },
                          { value: 'open', label: t('money.open') },
                        ],
                        test: (r, v) => (v === 'overdue' ? r.overdue : !r.overdue),
                      },
                    ],
                  }}
                >
                  {(shown) => (
                <Table>
                  <thead>
                    <tr>
                      <th>{t('money.col.bill')}</th>
                      <th>{t('money.col.supplier')}</th>
                      <th>{t('money.col.lot')}</th>
                      <th>{t('money.col.due')}</th>
                      <th className="num">{t('common.amount')}</th>
                      <th className="num">{t('money.col.paid')}</th>
                      <th className="num">{t('money.col.balance')}</th>
                      <th>
                        <span className="sr-only">{t('money.actions')}</span>
                      </th>
                    </tr>
                  </thead>
                  <tbody>
                    {shown.map((r) => (
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
                              <Badge tone="red">{t('money.overdue')}</Badge>
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
                            <Button variant="secondary" onClick={() => setPaying(r)} aria-label={t('money.recordForBill', { no: r.bill_no })}>
                              {t('money.recordPayment')}
                            </Button>
                          ) : (
                            <Badge tone="green">{t('money.paid')}</Badge>
                          )}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </Table>
                  )}
                </Filtered>
              </Reveal>
            </div>
          )
        }}
      </QueryBoundary>
      {paying && (
        <PaymentDialog
          title={t('money.dialogSupplier')}
          subject={t('money.billSubject', { no: paying.bill_no, name: paying.supplier.name })}
          balance={paying.balance}
          dateLabel={t('money.paidOn')}
          invalidate={[['money']]}
          send={(v) =>
            call(api.POST('/api/payments/supplier', { body: { bill_id: paying.bill_id, amount: v.amount, paid_on: v.date, ...(v.reference ? { reference: v.reference } : {}) } }))
          }
          successMessage={(v) => t('money.paidToast', { amount: formatMoney(v.amount), name: paying.supplier.name })}
          onClose={() => setPaying(null)}
        />
      )}
    </>
  )
}
