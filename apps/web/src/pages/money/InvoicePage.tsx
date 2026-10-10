import { useQuery } from '@tanstack/react-query'
import { ArrowLeft, Printer } from 'lucide-react'
import { Link, useNavigate, useParams } from 'react-router-dom'
import { BrandMark } from '@/components/common/BrandMark'
import { PageHeader } from '@/components/common/PageHeader'
import { QueryBoundary } from '@/components/common/QueryBoundary'
import { Badge } from '@/components/ui/Badge'
import { Button } from '@/components/ui/Button'
import { api, call } from '@/lib/api'
import { useMe } from '@/lib/auth'
import { formatDate, formatMetres, formatMoney } from '@/lib/format'

/** One invoice, laid out like paper so it prints cleanly. Opened from a dispatch, from receivables, or by the buyer from the portal. */
export default function InvoicePage() {
  const { no = '' } = useParams()
  const navigate = useNavigate()
  const me = useMe()
  const invoice = useQuery({ queryKey: ['invoices', no], queryFn: () => call(api.GET('/api/invoices/{invoice_no}', { params: { path: { invoice_no: no } } })) })
  const isBuyer = me.data?.role === 'buyer'

  return (
    <>
      <div className="no-print">
        <PageHeader
          eyebrow={isBuyer ? 'Your orders' : 'Money'}
          title={`Invoice ${no}`}
          description="Check the rolls and metres, then print it or save it as a PDF."
          actions={
            <>
              <Button variant="secondary" onClick={() => navigate(-1)}>
                <ArrowLeft size={16} aria-hidden /> Back
              </Button>
              <Button onClick={() => window.print()}>
                <Printer size={16} aria-hidden /> Print
              </Button>
            </>
          }
        />
      </div>
      <QueryBoundary query={invoice}>
        {(inv) => (
          <article className="invoice" aria-label={`Invoice ${inv.invoice_no}`}>
            <header className="invoice-head">
              <div className="invoice-brand">
                <span className="brand-mark">
                  <BrandMark size={18} />
                </span>
                <div>
                  <strong>Everest Textile Mills</strong>
                  <p className="muted text-sm">Invoice</p>
                </div>
              </div>
              <div className="invoice-no">
                <strong>{inv.invoice_no}</strong>
                <span className="muted text-sm">{formatDate(inv.issued_at)}</span>
                {inv.balance <= 0 ? <Badge tone="green">Paid</Badge> : inv.paid_amount > 0 ? <Badge tone="amber">Part paid</Badge> : <Badge tone="gray">Unpaid</Badge>}
              </div>
            </header>

            <dl className="invoice-meta">
              <div>
                <dt>Billed to</dt>
                <dd>{inv.buyer.name}</dd>
              </div>
              <div>
                <dt>Dispatch</dt>
                <dd>{isBuyer ? inv.dispatch_code : <Link to={`/dispatch/${inv.dispatch_code}`}>{inv.dispatch_code}</Link>}</dd>
              </div>
              <div>
                <dt>Vehicle</dt>
                <dd>{inv.vehicle_no}</dd>
              </div>
            </dl>

            <div className="table-wrap invoice-lines">
              <table className="table">
                <thead>
                  <tr>
                    <th>Order</th>
                    <th>Fabric</th>
                    <th>Rolls</th>
                    <th className="num">Metres</th>
                    <th className="num">Rate</th>
                    <th className="num">Amount</th>
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
                      <td className="num">{formatMoney(l.rate)} / m</td>
                      <td className="num">{formatMoney(l.amount)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>

            <dl className="invoice-totals">
              <div>
                <dt>Total</dt>
                <dd>{formatMoney(inv.total_amount)}</dd>
              </div>
              <div>
                <dt>Received</dt>
                <dd>{formatMoney(inv.paid_amount)}</dd>
              </div>
              <div className="invoice-balance">
                <dt>Balance due</dt>
                <dd>{formatMoney(inv.balance)}</dd>
              </div>
            </dl>
          </article>
        )}
      </QueryBoundary>
    </>
  )
}
