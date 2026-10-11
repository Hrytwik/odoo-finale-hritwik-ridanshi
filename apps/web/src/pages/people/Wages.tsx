import { useQuery } from '@tanstack/react-query'
import { useState } from 'react'
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
import { api, call, type components } from '@/lib/api'
import { todayIso } from '@/lib/dates'
import { useI18n } from '@/i18n/I18nContext'
import { formatLocale, formatMoney } from '@/lib/format'
import { PaymentDialog } from '@/pages/money/PaymentDialog'

type Row = components['schemas']['WageRow']

const monthName = (month: string) => new Date(`${month}-01T00:00:00`).toLocaleDateString(formatLocale(), { month: 'long', year: 'numeric' })
const lastDay = (month: string) => {
  const [y, m] = month.split('-').map(Number)
  return `${month}-${String(new Date(y, m, 0).getDate()).padStart(2, '0')}`
}

/** What each worker earned from attendance this month, what has been paid, and what is still owed. */
export default function Wages() {
  const { t } = useI18n()
  const [month, setMonth] = useState(() => todayIso().slice(0, 7))
  const [paying, setPaying] = useState<Row | null>(null)
  const sheet = useQuery({ queryKey: ['people', 'wages', month], queryFn: () => call(api.GET('/api/wages', { params: { query: { month } } })) })

  return (
    <>
      <PageHeader
        eyebrow={t('attendance.eyebrow')}
        title={t('nav.wages')}
        description={t('wages.description')}
        actions={
          <label className="month-picker">
            <span className="muted text-sm">{t('owner.month')}</span>
            <input type="month" className="input" value={month} max={todayIso().slice(0, 7)} onChange={(e) => e.target.value && setMonth(e.target.value)} />
          </label>
        }
      />
      <QueryBoundary query={sheet}>
        {(s) =>
          s.rows.length === 0 ? (
            <EmptyState title={t('attendance.noWorkers')} description={t('wages.emptyDescription')} />
          ) : (
            <div className="stack">
              <AnimatedGroup className="grid-cards">
                <KpiCard label={t('wages.earned')} value={s.total_earned} format={formatMoney} />
                <KpiCard label={t('money.col.paid')} value={s.total_paid} format={formatMoney} />
                <KpiCard label={t('wages.stillOwed')} value={s.total_owed} format={formatMoney} tone={s.total_owed > 0 ? 'danger' : undefined} />
              </AnimatedGroup>
              <Reveal>
                <Filtered
                  rows={s.rows}
                  options={{
                    text: (r) => `${r.worker_name} ${r.worker_code}`,
                    sorts: [
                      { key: 'worker', label: t('wages.col.worker'), value: (r) => r.worker_name },
                      { key: 'earned', label: t('wages.earned'), value: (r) => r.earned },
                      { key: 'paid', label: t('money.col.paid'), value: (r) => r.paid },
                      { key: 'owed', label: t('wages.col.owed'), value: (r) => r.owed },
                    ],
                    filters: [
                      {
                        key: 'owed',
                        label: t('qc.col.status'),
                        options: [
                          { value: 'owed', label: t('wages.stillOwed') },
                          { value: 'paid', label: t('money.paid') },
                        ],
                        test: (r, v) => (v === 'owed' ? r.owed > 0 : r.owed <= 0),
                      },
                    ],
                  }}
                >
                  {(shown) => (
                <Table>
                  <thead>
                    <tr>
                      <th>{t('wages.col.worker')}</th>
                      <th className="num">{t('attendance.present')}</th>
                      <th className="num">{t('wages.col.halfDays')}</th>
                      <th className="num">{t('attendance.absent')}</th>
                      <th className="num">{t('wages.col.dailyWage')}</th>
                      <th className="num">{t('wages.earned')}</th>
                      <th className="num">{t('money.col.paid')}</th>
                      <th className="num">{t('wages.col.owed')}</th>
                      <th>
                        <span className="sr-only">{t('money.actions')}</span>
                      </th>
                    </tr>
                  </thead>
                  <tbody>
                    {shown.map((r) => (
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
                            <Button variant="secondary" onClick={() => setPaying(r)} aria-label={t('money.recordFor', { no: r.worker_name })}>
                              {t('money.recordPayment')}
                            </Button>
                          ) : r.earned > 0 ? (
                            <Badge tone="green">{t('money.paid')}</Badge>
                          ) : null}
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
        }
      </QueryBoundary>
      {paying && (
        <PaymentDialog
          title={t('wages.dialogTitle')}
          subject={t('wages.subject', { name: paying.worker_name, month: monthName(month) })}
          balance={paying.owed}
          dateLabel={t('money.paidOn')}
          invalidate={[['people'], ['owner']]}
          send={(v) =>
            call(api.POST('/api/payments/wages', { body: { worker_id: paying.worker_id, period_start: `${month}-01`, period_end: lastDay(month), amount: v.amount, paid_at: v.date } }))
          }
          successMessage={(v) => t('money.paidToast', { amount: formatMoney(v.amount), name: paying.worker_name })}
          onClose={() => setPaying(null)}
        />
      )}
    </>
  )
}
