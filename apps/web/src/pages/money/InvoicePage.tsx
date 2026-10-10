import { useQuery } from '@tanstack/react-query'
import { ArrowLeft, Printer } from 'lucide-react'
import { Link, useNavigate, useParams } from 'react-router-dom'
import { BrandMark } from '@/components/common/BrandMark'
import { PageHeader } from '@/components/common/PageHeader'
import { QueryBoundary } from '@/components/common/QueryBoundary'
import { Badge } from '@/components/ui/Badge'
import { Button } from '@/components/ui/Button'
import { api, call } from '@/lib/api'
import { useI18n } from '@/i18n/I18nContext'
import { useMe } from '@/lib/auth'
import { formatDate, formatMetres, formatMoney } from '@/lib/format'

/** One invoice, laid out like paper so it prints cleanly. Opened from a dispatch, from receivables, or by the buyer from the portal. */
export default function InvoicePage() {
  const { t } = useI18n()
  const { no = '' } = useParams()
  const navigate = useNavigate()
  const me = useMe()
  const invoice = useQuery({ queryKey: ['invoices', no], queryFn: () => call(api.GET('/api/invoices/{invoice_no}', { params: { path: { invoice_no: no } } })) })
  const isBuyer = me.data?.role === 'buyer'

  return (
    <>
      <div className="no-print">
        <PageHeader
          eyebrow={isBuyer ? t('money.invoice.eyebrowBuyer') : t('nav.group.Money')}
          title={t('money.invoice.title', { no })}
          description={t('money.invoice.description')}
          actions={
            <>
              <Button variant="secondary" onClick={() => navigate(-1)}>
                <ArrowLeft size={16} aria-hidden /> {t('money.back')}
              </Button>
              <Button onClick={() => window.print()}>
                <Printer size={16} aria-hidden /> {t('money.print')}
              </Button>
            </>
          }
        />
      </div>
      <QueryBoundary query={invoice}>
        {(inv) => (
          <article className="invoice" aria-label={t('money.invoice.title', { no: inv.invoice_no })}>
            <header className="invoice-head">
              <div className="invoice-brand">
                <span className="brand-mark">
                  <BrandMark size={18} />
                </span>
                <div>
                  <strong>Everest Textile Mills</strong>
                  <p className="muted text-sm">{t('money.invoice.word')}</p>
                </div>
              </div>
              <div className="invoice-no">
                <strong>{inv.invoice_no}</strong>
                <span className="muted text-sm">{formatDate(inv.issued_at)}</span>
                {inv.balance <= 0 ? <Badge tone="green">{t('money.paid')}</Badge> : inv.paid_amount > 0 ? <Badge tone="amber">{t('money.partPaid')}</Badge> : <Badge tone="gray">{t('money.unpaid')}</Badge>}
              </div>
            </header>

            <dl className="invoice-meta">
              <div>
                <dt>{t('money.invoice.billedTo')}</dt>
                <dd>{inv.buyer.name}</dd>
              </div>
              <div>
                <dt>{t('passport.dispatch')}</dt>
                <dd>{isBuyer ? inv.dispatch_code : <Link to={`/dispatch/${inv.dispatch_code}`}>{inv.dispatch_code}</Link>}</dd>
              </div>
              <div>
                <dt>{t('money.invoice.vehicle')}</dt>
                <dd>{inv.vehicle_no}</dd>
              </div>
            </dl>

            <div className="table-wrap invoice-lines">
              <table className="table">
                <thead>
                  <tr>
                    <th>{t('qc.col.order')}</th>
                    <th>{t('qc.col.fabric')}</th>
                    <th>{t('dispatch.col.rolls')}</th>
                    <th className="num">{t('dispatch.col.metres')}</th>
                    <th className="num">{t('money.invoice.rate')}</th>
                    <th className="num">{t('common.amount')}</th>
                  </tr>
                </thead>
                <tbody>
                  {inv.lines.map((l) => (
                    <tr key={l.order_code}>
                      <td>
                        <span className="code-text">{l.order_code}</span>
                      </td>
                      <td>
                        {l.fabric}
                        <div className="muted text-sm">{l.colour}</div>
                      </td>
                      <td className="text-sm">{l.roll_codes.join(', ')}</td>
                      <td className="num">{formatMetres(l.metres)}</td>
                      <td className="num">{t('money.invoice.perMetre', { amount: formatMoney(l.rate) })}</td>
                      <td className="num">{formatMoney(l.amount)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>

            <dl className="invoice-totals">
              <div>
                <dt>{t('money.invoice.total')}</dt>
                <dd>{formatMoney(inv.total_amount)}</dd>
              </div>
              <div>
                <dt>{t('money.received')}</dt>
                <dd>{formatMoney(inv.paid_amount)}</dd>
              </div>
              <div className="invoice-balance">
                <dt>{t('money.invoice.balanceDue')}</dt>
                <dd>{formatMoney(inv.balance)}</dd>
              </div>
            </dl>
          </article>
        )}
      </QueryBoundary>
    </>
  )
}
