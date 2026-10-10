import { useQuery, useQueryClient } from '@tanstack/react-query'
import { Ban, Radar } from 'lucide-react'
import { useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import { toast } from 'sonner'
import { Alert } from '@/components/common/Alert'
import { EmptyState } from '@/components/common/EmptyState'
import { KpiCard } from '@/components/common/KpiCard'
import { PageHeader } from '@/components/common/PageHeader'
import { QueryBoundary } from '@/components/common/QueryBoundary'
import { StatusBadge } from '@/components/common/StatusBadge'
import { SubmitButton } from '@/components/common/SubmitButton'
import { AnimatedGroup } from '@/components/motion/AnimatedGroup'
import { Disclosure } from '@/components/motion/Disclosure'
import { Reveal } from '@/components/motion/Reveal'
import { Badge, type Tone } from '@/components/ui/Badge'
import { Button } from '@/components/ui/Button'
import { Card } from '@/components/ui/Card'
import { Dialog } from '@/components/ui/Dialog'
import { Field, Textarea } from '@/components/ui/Field'
import { Table } from '@/components/ui/Table'
import { api, call, errorMessage, type components } from '@/lib/api'
import { useMe } from '@/lib/auth'
import { useSubmitLock } from '@/lib/forms'
import { formatDate, formatDateTime, formatKg, formatMetres, formatMoney } from '@/lib/format'

type Lot = components['schemas']['LotDetail']
type Movement = components['schemas']['MovementOut']
type Recall = components['schemas']['RecallOut']

const KIND: Record<Movement['kind'], { label: string; tone: Tone }> = {
  receipt: { label: 'Receipt', tone: 'green' },
  issue: { label: 'Issued', tone: 'amber' },
  return: { label: 'Returned', tone: 'blue' },
  adjustment: { label: 'Adjustment', tone: 'violet' },
}

export default function LotDetail() {
  const { code = '' } = useParams()
  const me = useMe()
  const canBlock = me.data?.role === 'store' || me.data?.role === 'owner'
  const [preview, setPreview] = useState(false)
  const path = { params: { path: { lot_code: code } } }

  const lot = useQuery({ queryKey: ['lots', code], queryFn: () => call(api.GET('/api/lots/{lot_code}', path)), enabled: !!code })
  const exposureWanted = preview || lot.data?.is_blocked === true
  const recall = useQuery({ queryKey: ['lots', code, 'recall'], queryFn: () => call(api.GET('/api/lots/{lot_code}/recall', path)), enabled: !!code && exposureWanted })

  return (
    <QueryBoundary query={lot}>
      {(l) => (
        <>
          <PageHeader
            title={l.lot_code}
            description={`${l.yarn_type.name} (${l.yarn_type.colour}) · ${l.supplier.name} · challan ${l.challan_no} · received ${formatDate(l.received_at)}`}
            actions={
              <>
                {l.is_blocked ? <Badge tone="red">Blocked</Badge> : <Badge tone="green">OK to use</Badge>}
                {canBlock && !l.is_blocked && <BlockButton lot={l} />}
                {!l.is_blocked && !preview && (
                  <Button variant="secondary" onClick={() => setPreview(true)}>
                    <Radar size={16} aria-hidden /> See what this lot touched
                  </Button>
                )}
              </>
            }
          />
          <div className="stack">
            {l.is_blocked && <Alert tone="error">This lot is blocked: {l.blocked_reason}. It cannot be issued to any run.</Alert>}
            <AnimatedGroup className="grid-cards">
              <KpiCard label="Received" value={l.qty_received_kg} format={formatKg} />
              <KpiCard label="On hand" value={l.on_hand_kg} format={formatKg} />
              <KpiCard label="Value on hand" value={l.on_hand_kg * l.cost_per_kg} format={formatMoney} hint={`at ${formatMoney(l.cost_per_kg)} per kg`} />
            </AnimatedGroup>
            <Reveal>
              <Disclosure title="Stock ledger" meta={`${l.movements.length} movements`} defaultOpen>
                <Ledger movements={l.movements} />
              </Disclosure>
            </Reveal>
            {exposureWanted && (
              <Reveal>
                <QueryBoundary query={recall}>{(r) => <Exposure recall={r} />}</QueryBoundary>
              </Reveal>
            )}
          </div>
        </>
      )}
    </QueryBoundary>
  )
}

function Ledger({ movements }: { movements: Movement[] }) {
  if (movements.length === 0) return <EmptyState title="No movements yet" />
  return (
    <Table>
      <thead>
        <tr>
          <th>When</th>
          <th>Kind</th>
          <th className="num">Quantity</th>
          <th>Where</th>
          <th>By</th>
        </tr>
      </thead>
      <tbody>
        {movements.map((m) => (
          <tr key={m.id}>
            <td className="nowrap">{formatDateTime(m.at)}</td>
            <td>
              <Badge tone={KIND[m.kind].tone}>{KIND[m.kind].label}</Badge>
            </td>
            <td className="num">{formatKg(m.qty_kg)}</td>
            <td>
              {[m.order_code, m.machine_code, m.note].filter(Boolean).join(' · ') || <span className="muted">-</span>}
            </td>
            <td>{m.by}</td>
          </tr>
        ))}
      </tbody>
    </Table>
  )
}

/* ---------- recall ---------- */

function Exposure({ recall }: { recall: Recall }) {
  const groups: { title: string; rolls: Recall['on_floor'] }[] = [
    { title: 'On the floor', rolls: recall.on_floor },
    { title: 'In store', rolls: recall.in_store },
    { title: 'Loading on a truck', rolls: recall.loading },
    { title: 'Already dispatched', rolls: recall.dispatched },
  ]
  const total = groups.reduce((n, g) => n + g.rolls.length, 0)
  return (
    <div className="stack">
      <Card title={`Recall exposure: ${total} ${total === 1 ? 'roll' : 'rolls'}`}>
        {total === 0 ? (
          <p className="muted">No roll was made from this lot yet.</p>
        ) : (
          <div className="stack">
            {groups
              .filter((g) => g.rolls.length > 0)
              .map((g) => (
                <div key={g.title} className="stack-sm">
                  <h3 className="text-sm">
                    {g.title} <span className="muted">({g.rolls.length})</span>
                  </h3>
                  <Table>
                    <thead>
                      <tr>
                        <th>Roll</th>
                        <th>Order</th>
                        <th>Buyer</th>
                        <th className="num">Metres</th>
                        <th>Status</th>
                        <th>Dispatch</th>
                      </tr>
                    </thead>
                    <tbody>
                      {g.rolls.map((r) => (
                        <tr key={r.roll_code}>
                          <td>
                            <Link to={`/r/${r.roll_code}`}>{r.roll_code}</Link>
                          </td>
                          <td>{r.order_code}</td>
                          <td>{r.buyer_name}</td>
                          <td className="num">{formatMetres(r.metres)}</td>
                          <td>
                            <StatusBadge kind="roll" value={r.status} />
                          </td>
                          <td>{r.dispatch_code ?? <span className="muted">-</span>}</td>
                        </tr>
                      ))}
                    </tbody>
                  </Table>
                </div>
              ))}
          </div>
        )}
      </Card>
      {recall.buyers.length > 0 && (
        <Card title="Buyers to contact">
          <div className="stack">
            <Table>
              <thead>
                <tr>
                  <th>Buyer</th>
                  <th>Rolls from this lot</th>
                  <th>Dispatches</th>
                </tr>
              </thead>
              <tbody>
                {recall.buyers.map((b) => (
                  <tr key={b.buyer_id}>
                    <td>{b.buyer_name}</td>
                    <td>
                      {b.dispatched_roll_count} of {b.roll_count} already dispatched
                    </td>
                    <td>{b.dispatch_codes.length ? b.dispatch_codes.join(', ') : <span className="muted">none yet</span>}</td>
                  </tr>
                ))}
              </tbody>
            </Table>
            <p className="muted text-sm">A drafted message for each buyer appears here once the AI assistant is set up.</p>
          </div>
        </Card>
      )}
    </div>
  )
}

/* ---------- block lot ---------- */

function BlockButton({ lot }: { lot: Lot }) {
  const [open, setOpen] = useState(false)
  const [reason, setReason] = useState('')
  const [error, setError] = useState<string | null>(null)
  const [fieldError, setFieldError] = useState<string | undefined>()
  const { run, pending } = useSubmitLock()
  const queryClient = useQueryClient()

  function close() {
    setOpen(false)
    setError(null)
    setFieldError(undefined)
  }

  const submit = () =>
    run(async () => {
      const text = reason.trim()
      if (!text) return setFieldError('Say why the lot is being blocked')
      setFieldError(undefined)
      setError(null)
      try {
        await call(api.POST('/api/lots/{lot_code}/block', { params: { path: { lot_code: lot.lot_code } }, body: { reason: text } }))
        toast.success(`${lot.lot_code} blocked`)
        void queryClient.invalidateQueries({ queryKey: ['lots'] })
        void queryClient.invalidateQueries({ queryKey: ['stock'] })
        close()
      } catch (err) {
        setError(errorMessage(err))
      }
    })

  return (
    <>
      <Button variant="danger" onClick={() => setOpen(true)}>
        <Ban size={16} aria-hidden /> Block this lot
      </Button>
      <Dialog open={open} onClose={close} title={`Block ${lot.lot_code}?`}>
        <div className="stack">
          <p>
            No more yarn can be issued from this lot. The roll history shows every roll made from it, so you can recall them. This is meant for a quality problem with the yarn.
          </p>
          <Field label="Reason" error={fieldError}>
            {(c) => <Textarea {...c} value={reason} onChange={(e) => setReason(e.target.value)} />}
          </Field>
          {error && <Alert tone="error">{error}</Alert>}
          <div className="row">
            <SubmitButton variant="danger" pending={pending} onClick={submit}>
              Block lot
            </SubmitButton>
            <Button variant="secondary" onClick={close}>
              Keep using it
            </Button>
          </div>
        </div>
      </Dialog>
    </>
  )
}
