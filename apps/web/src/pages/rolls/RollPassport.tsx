import { useQuery } from '@tanstack/react-query'
import { Printer, ScanLine } from 'lucide-react'
import { useState } from 'react'
import { Link, useNavigate, useParams } from 'react-router-dom'
import { toast } from 'sonner'
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
import type { Key } from '@/i18n/en'
import { useI18n } from '@/i18n/I18nContext'
import { api, call, type components } from '@/lib/api'
import { useMe } from '@/lib/auth'
import { formatDate, formatDateTime, formatMetres, formatMoney } from '@/lib/format'

type Passport = components['schemas']['Passport']
type Inspection = components['schemas']['InspectionOut']
type Run = components['schemas']['PassportRun']
type DefectType = components['schemas']['DefectOut']['defect_type']

const STAGE: Record<Run['stage'], Key> = { spinning: 'floor.stage.spinning', weaving: 'floor.stage.weaving', dyeing: 'floor.stage.dyeing', rework: 'passport.stage.rework' }
const VERDICT: Record<Inspection['verdict'], { label: Key; tone: Tone }> = {
  pass: { label: 'qc.verdict.pass', tone: 'green' },
  rework: { label: 'qc.verdict.rework', tone: 'amber' },
  reject: { label: 'qc.verdict.reject', tone: 'red' },
}
const defectKey = (type: DefectType, count: number) => `passport.defect.${type}.${count === 1 ? 'one' : 'many'}` as Key

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
  const { t } = useI18n()
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
              <ScanLine size={16} aria-hidden /> {t('qc.scan')}
            </Button>
            <Button variant="secondary" onClick={() => window.print()}>
              <Printer size={16} aria-hidden /> {t('passport.printLabel')}
            </Button>
          </>
        }
      />
      <QrScanner
        open={scanning}
        onClose={() => setScanning(false)}
        onCode={(code) => {
          setScanning(false)
          toast.success(t('passport.scanned', { code }))
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
                {t('qc.col.order')} <Link to={orderPath}>{p.order_code}</Link> {t('passport.orderFor')} <strong>{p.buyer_name}</strong>
              </p>
              <p className="muted text-sm">{t('passport.buyerDeadline', { date: formatDate(p.deadline) })}</p>
            </div>
            <RollQr code={r.code} />
          </div>
        </Tilt>

        {!isBuyer && (
          <Reveal>
            <Card title={t('passport.yarn')}>
              <div className="stack-sm">
                {p.yarn_lots.map((l) => (
                  <div key={l.lot_code} className="shortage">
                    <span>
                      <Link to={`/store/lots/${l.lot_code}`}>{l.lot_code}</Link> · {l.yarn_type} · {l.supplier}
                    </span>
                    {l.is_blocked && <Badge tone="red">{t('passport.recalled')}</Badge>}
                  </div>
                ))}
                {p.yarn_lots.length === 0 && <p className="muted">{t('passport.noYarn')}</p>}
              </div>
            </Card>
          </Reveal>
        )}

        {!isBuyer && (
          <Reveal>
            <Card title={t('passport.machines')}>
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
          <Card title={t('passport.qualityChecks')}>
            {p.inspections.length === 0 ? (
              <p className="muted">{t('passport.notChecked')}</p>
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
          <Card title={t('passport.dispatch')}>
            {p.dispatch ? (
              <div className="stack-sm">
                <p>
                  <strong>{p.dispatch.code}</strong>
                  {p.dispatch.dispatched_at ? `, ${formatDateTime(p.dispatch.dispatched_at)}` : t('passport.dispatchLoading')}
                </p>
                <p className="muted text-sm">{t('passport.vehicle', { no: p.dispatch.vehicle_no })}</p>
                {p.dispatch.invoice_no && (
                  <p>
                    {t('passport.invoice')} <Link to={`/invoices/${p.dispatch.invoice_no}`}>{p.dispatch.invoice_no}</Link>
                  </p>
                )}
              </div>
            ) : (
              <p className="muted">{t('passport.notDispatched')}</p>
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
  const { t } = useI18n()
  return (
    <li>
      {t('passport.runLine', { stage: t(STAGE[run.stage]), machine: run.machine_name ?? t('passport.byHand'), operator: run.operator })}
      <div className="muted text-sm">
        {run.ended_at ? t('passport.runRange', { from: formatDateTime(run.started_at), to: formatDateTime(run.ended_at) }) : `${formatDateTime(run.started_at)}, ${t('passport.stillRunning')}`}
      </div>
    </li>
  )
}

function InspectionItem({ i, showInspector }: { i: Inspection; showInspector: boolean }) {
  const { t } = useI18n()
  return (
    <div className="stack-sm">
      <div className="row">
        <Badge tone={VERDICT[i.verdict].tone}>{t(VERDICT[i.verdict].label)}</Badge>
        <span className="muted text-sm">
          {showInspector ? `${i.inspector.name}, ` : ''}
          {formatDateTime(i.inspected_at)}
        </span>
      </div>
      {i.defects.length > 0 && <p className="text-sm">{i.defects.map((d) => t(defectKey(d.defect_type, d.count), { count: d.count })).join(', ')}</p>}
      {i.notes && <p className="text-sm">{i.notes}</p>}
      {showInspector && i.overrode_ai && <p className="muted text-sm">{t('passport.overrodeAi')}</p>}
    </div>
  )
}

function CostCard({ cost }: { cost: Passport['cost'] }) {
  const { t } = useI18n()
  if (!cost) {
    return (
      <Card title={t('passport.cost')}>
        <p className="muted">{t('passport.costMissing')}</p>
      </Card>
    )
  }
  return (
    <Card title={t('passport.cost')}>
      <div className="stack">
        <div className="grid-cards">
          <KpiCard label={t('passport.perMetre')} value={cost.per_metre} format={formatMoney} hint={cost.provisional ? t('passport.provisionalHint') : t('passport.final')} />
          <KpiCard label={t('passport.totalRoll')} value={cost.total} format={formatMoney} />
        </div>
        <div>
          <Badge tone={cost.provisional ? 'amber' : 'green'}>{cost.provisional ? t('passport.provisional') : t('passport.final')}</Badge>
        </div>
        <Table>
          <thead>
            <tr>
              <th>{t('passport.whereMoney')}</th>
              <th className="num">{t('passport.amount')}</th>
            </tr>
          </thead>
          <tbody>
            <tr>
              <td>{t('passport.yarn')}</td>
              <td className="num">{formatMoney(cost.parts.yarn)}</td>
            </tr>
            <tr>
              <td>{t('passport.machinesCost')}</td>
              <td className="num">{formatMoney(cost.parts.machine)}</td>
            </tr>
            <tr>
              <td>{t('passport.labour')}</td>
              <td className="num">{formatMoney(cost.parts.labour)}</td>
            </tr>
            <tr>
              <td>{t('passport.stage.rework')}</td>
              <td className="num">{formatMoney(cost.parts.rework)}</td>
            </tr>
            <tr>
              <td>{t('passport.rejectShare')}</td>
              <td className="num">{formatMoney(cost.reject_share)}</td>
            </tr>
          </tbody>
        </Table>
      </div>
    </Card>
  )
}
