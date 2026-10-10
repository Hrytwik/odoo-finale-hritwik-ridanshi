import { useQuery } from '@tanstack/react-query'
import { Printer, ScanLine } from 'lucide-react'
import { useState } from 'react'
import { Link, useNavigate, useParams } from 'react-router-dom'
import { KpiCard } from '@/components/common/KpiCard'
import { PageHeader } from '@/components/common/PageHeader'
import { QrScanner } from '@/components/common/QrScanner'
import { QueryBoundary } from '@/components/common/QueryBoundary'
import { RollQr } from '@/components/common/RollQr'
import { StatusBadge } from '@/components/common/StatusBadge'
import { Reveal } from '@/components/motion/Reveal'
import { Tilt } from '@/components/motion/Tilt'
import { Badge, type Tone } from '@/components/ui/Badge'
import { Button } from '@/components/ui/Button'
import { Card } from '@/components/ui/Card'
import { Table } from '@/components/ui/Table'
import { api, call, type components } from '@/lib/api'
import { useMe } from '@/lib/auth'
import { formatDate, formatDateTime, formatMetres, formatMoney } from '@/lib/format'

type Passport = components['schemas']['Passport']
type Inspection = components['schemas']['InspectionOut']
type Run = components['schemas']['PassportRun']
type DefectType = components['schemas']['DefectOut']['defect_type']

const STAGE = { spinning: 'Spinning', weaving: 'Weaving', dyeing: 'Dyeing', rework: 'Rework' } as const
const VERDICT: Record<Inspection['verdict'], { label: string; tone: Tone }> = {
  pass: { label: 'Pass', tone: 'green' },
  rework: { label: 'Rework', tone: 'amber' },
  reject: { label: 'Reject', tone: 'red' },
}
const DEFECT: Record<DefectType, [string, string]> = {
  hole: ['hole', 'holes'],
  stain: ['stain', 'stains'],
  thread_fault: ['thread fault', 'thread faults'],
  colour_mismatch: ['colour mismatch', 'colour mismatches'],
  other: ['other defect', 'other defects'],
}
const defectText = (type: DefectType, count: number) => `${count} ${DEFECT[type][count === 1 ? 0 : 1]}`

export default function RollPassport() {
  const { code = '' } = useParams()
  const me = useMe()
  const isBuyer = me.data?.role === 'buyer'
  const passport = useQuery({
    queryKey: ['rolls', code],
    queryFn: () => call(api.GET('/api/rolls/{roll_code}/passport', { params: { path: { roll_code: code } } })),
    enabled: !!code,
  })
  return <QueryBoundary query={passport}>{(p) => <Content p={p} isBuyer={isBuyer} />}</QueryBoundary>
}

function Content({ p, isBuyer }: { p: Passport; isBuyer: boolean }) {
  const navigate = useNavigate()
  const [scanning, setScanning] = useState(false)
  const r = p.roll
  // buyers see their own order in the portal; staff see it in the orders area
  const orderPath = isBuyer ? `/portal/orders/${p.order_code}` : `/orders/${p.order_code}`

  return (
    <>
      <PageHeader
        title={r.code}
        description={`${r.fabric}, ${r.colour} · ${formatMetres(r.metres)}`}
        actions={
          <>
            <Button variant="secondary" onClick={() => setScanning(true)}>
              <ScanLine size={16} aria-hidden /> Scan a roll
            </Button>
            <Button variant="secondary" onClick={() => window.print()}>
              <Printer size={16} aria-hidden /> Print label
            </Button>
          </>
        }
      />
      <QrScanner
        open={scanning}
        onClose={() => setScanning(false)}
        onCode={(code) => {
          setScanning(false)
          navigate(`/r/${code}`)
        }}
      />

      <div className="stack">
        <Tilt>
          <div className="passport-hero">
            <div className="stack-sm">
              <div className="row">
                <StatusBadge kind="roll" value={r.status} />
              </div>
              <p>
                Order <Link to={orderPath}>{p.order_code}</Link> for <strong>{p.buyer_name}</strong>
              </p>
              <p className="muted text-sm">Buyer deadline {formatDate(p.deadline)}</p>
            </div>
            <RollQr code={r.code} />
          </div>
        </Tilt>

        {!isBuyer && (
          <Reveal>
            <Card title="Yarn">
              <div className="stack-sm">
                {p.yarn_lots.map((l) => (
                  <div key={l.lot_code} className="shortage">
                    <span>
                      <Link to={`/store/lots/${l.lot_code}`}>{l.lot_code}</Link> · {l.yarn_type} · {l.supplier}
                    </span>
                    {l.is_blocked && <Badge tone="red">Recalled</Badge>}
                  </div>
                ))}
                {p.yarn_lots.length === 0 && <p className="muted">No yarn lot recorded yet.</p>}
              </div>
            </Card>
          </Reveal>
        )}

        {!isBuyer && (
          <Reveal>
            <Card title="Machines">
              <ol className="timeline">
                {[...p.runs]
                  .sort((a, b) => a.started_at.localeCompare(b.started_at))
                  .map((run) => (
                    <RunItem key={run.id} run={run} />
                  ))}
              </ol>
            </Card>
          </Reveal>
        )}

        <Reveal>
          <Card title="Quality checks">
            {p.inspections.length === 0 ? (
              <p className="muted">This roll has not been checked yet.</p>
            ) : (
              <div className="stack">
                {p.inspections.map((i) => (
                  <InspectionItem key={i.id} i={i} showInspector={!isBuyer} />
                ))}
              </div>
            )}
          </Card>
        </Reveal>

        <Reveal>
          <Card title="Dispatch">
            {p.dispatch ? (
              <div className="stack-sm">
                <p>
                  <strong>{p.dispatch.code}</strong>
                  {p.dispatch.dispatched_at ? `, ${formatDateTime(p.dispatch.dispatched_at)}` : ', loading'}
                </p>
                <p className="muted text-sm">Vehicle {p.dispatch.vehicle_no}</p>
                {p.dispatch.invoice_no && (
                  <p>
                    Invoice <Link to={`/invoices/${p.dispatch.invoice_no}`}>{p.dispatch.invoice_no}</Link>
                  </p>
                )}
              </div>
            ) : (
              <p className="muted">This roll has not been dispatched.</p>
            )}
          </Card>
        </Reveal>

        {!isBuyer && (
          <Reveal>
            <CostCard cost={p.cost} />
          </Reveal>
        )}
      </div>
    </>
  )
}

function RunItem({ run }: { run: Run }) {
  return (
    <li>
      <strong>{STAGE[run.stage]}</strong> on {run.machine_name ?? 'manual mending'} · {run.operator}
      <div className="muted text-sm">
        {formatDateTime(run.started_at)}
        {run.ended_at ? ` to ${formatDateTime(run.ended_at)}` : ', still running'}
      </div>
    </li>
  )
}

function InspectionItem({ i, showInspector }: { i: Inspection; showInspector: boolean }) {
  return (
    <div className="stack-sm">
      <div className="row">
        <Badge tone={VERDICT[i.verdict].tone}>{VERDICT[i.verdict].label}</Badge>
        <span className="muted text-sm">
          {showInspector ? `${i.inspector.name}, ` : ''}
          {formatDateTime(i.inspected_at)}
        </span>
      </div>
      {i.defects.length > 0 && <p className="text-sm">{i.defects.map((d) => defectText(d.defect_type, d.count)).join(', ')}</p>}
      {i.notes && <p className="text-sm">{i.notes}</p>}
      {showInspector && i.overrode_ai && <p className="muted text-sm">The inspector overrode the AI suggestion.</p>}
    </div>
  )
}

function CostCard({ cost }: { cost: Passport['cost'] }) {
  if (!cost) {
    return (
      <Card title="True cost">
        <p className="muted">Cost is not available yet.</p>
      </Card>
    )
  }
  return (
    <Card title="True cost">
      <div className="stack">
        <div className="grid-cards">
          <KpiCard label="Cost per metre" value={cost.per_metre} format={formatMoney} hint={cost.provisional ? 'Provisional: the order is not finished' : 'Final'} />
          <KpiCard label="Total for this roll" value={cost.total} format={formatMoney} />
        </div>
        <div>
          <Badge tone={cost.provisional ? 'amber' : 'green'}>{cost.provisional ? 'Provisional' : 'Final'}</Badge>
        </div>
        <Table>
          <thead>
            <tr>
              <th>Where the money went</th>
              <th className="num">Amount</th>
            </tr>
          </thead>
          <tbody>
            <tr>
              <td>Yarn</td>
              <td className="num">{formatMoney(cost.parts.yarn)}</td>
            </tr>
            <tr>
              <td>Machines</td>
              <td className="num">{formatMoney(cost.parts.machine)}</td>
            </tr>
            <tr>
              <td>Labour</td>
              <td className="num">{formatMoney(cost.parts.labour)}</td>
            </tr>
            <tr>
              <td>Rework</td>
              <td className="num">{formatMoney(cost.parts.rework)}</td>
            </tr>
            <tr>
              <td>Share of rejected rolls</td>
              <td className="num">{formatMoney(cost.reject_share)}</td>
            </tr>
          </tbody>
        </Table>
      </div>
    </Card>
  )
}
