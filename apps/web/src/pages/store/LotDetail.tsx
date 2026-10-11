import { useQuery, useQueryClient } from '@tanstack/react-query'
import { Ban, Radar } from 'lucide-react'
import { useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import { toast } from 'sonner'
import { RecallDrafts } from '@/components/ai/Drafts'
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
import type { Key } from '@/i18n/en'
import { useI18n } from '@/i18n/I18nContext'
import { api, call, errorMessage, type components } from '@/lib/api'
import { useMe } from '@/lib/auth'
import { useSubmitLock } from '@/lib/forms'
import { formatDate, formatDateTime, formatKg, formatMetres, formatMoney } from '@/lib/format'

type Lot = components['schemas']['LotDetail']
type Movement = components['schemas']['MovementOut']
type Recall = components['schemas']['RecallOut']

const KIND: Record<Movement['kind'], { label: Key; tone: Tone }> = {
  receipt: { label: 'lot.kind.receipt', tone: 'green' },
  issue: { label: 'lot.kind.issue', tone: 'amber' },
  return: { label: 'lot.kind.return', tone: 'blue' },
  adjustment: { label: 'lot.kind.adjustment', tone: 'violet' },
}

export default function LotDetail() {
  const { t } = useI18n()
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
            description={t('lot.subtitle', { yarn: l.yarn_type.name, colour: l.yarn_type.colour, supplier: l.supplier.name, challan: l.challan_no, date: formatDate(l.received_at) })}
            actions={
              <>
                {l.is_blocked ? <Badge tone="red">{t('lot.blocked')}</Badge> : <Badge tone="green">{t('lot.ok')}</Badge>}
                {canBlock && !l.is_blocked && <BlockButton lot={l} />}
                {!l.is_blocked && !preview && (
                  <Button variant="secondary" onClick={() => setPreview(true)}>
                    <Radar size={16} aria-hidden /> {t('lot.touched')}
                  </Button>
                )}
              </>
            }
          />
          <div className="stack">
            {l.is_blocked && <Alert tone="error">{t('lot.blockedAlert', { reason: l.blocked_reason ?? '' })}</Alert>}
            <AnimatedGroup className="grid-cards">
              <KpiCard label={t('money.received')} value={l.qty_received_kg} format={formatKg} />
              <KpiCard label={t('store.stock.onHand')} value={l.on_hand_kg} format={formatKg} />
              <KpiCard label={t('lot.valueOnHand')} value={l.on_hand_kg * l.cost_per_kg} format={formatMoney} hint={t('lot.atPrice', { price: formatMoney(l.cost_per_kg) })} />
            </AnimatedGroup>
            <Reveal>
              <Disclosure title={t('lot.ledger')} meta={t('lot.movements', { count: l.movements.length })} defaultOpen>
                <Ledger movements={l.movements} />
              </Disclosure>
            </Reveal>
            {exposureWanted && (
              <Reveal>
                <QueryBoundary query={recall}>{(r) => <Exposure recall={r} />}</QueryBoundary>
              </Reveal>
            )}
            {l.is_blocked && canBlock && (
              <Reveal>
                <section className="card" aria-label={t('lot.messagesAria')}>
                  <div className="card-body stack-sm">
                    <h2 className="card-title">{t('lot.tellBuyers')}</h2>
                    <p className="muted text-sm">{t('lot.tellBuyersHint')}</p>
                    <RecallDrafts lotCode={l.lot_code} />
                  </div>
                </section>
              </Reveal>
            )}
          </div>
        </>
      )}
    </QueryBoundary>
  )
}

function Ledger({ movements }: { movements: Movement[] }) {
  const { t } = useI18n()
  if (movements.length === 0) return <EmptyState title={t('lot.noMovements')} />
  return (
    <Table>
      <thead>
        <tr>
          <th>{t('lot.col.when')}</th>
          <th>{t('lot.col.kind')}</th>
          <th className="num">{t('orders.col.quantity')}</th>
          <th>{t('lot.col.where')}</th>
          <th>{t('lot.col.by')}</th>
        </tr>
      </thead>
      <tbody>
        {movements.map((m) => (
          <tr key={m.id}>
            <td className="nowrap">{formatDateTime(m.at)}</td>
            <td>
              <Badge tone={KIND[m.kind].tone}>{t(KIND[m.kind].label)}</Badge>
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
  const { t } = useI18n()
  const groups: { title: string; rolls: Recall['on_floor'] }[] = [
    { title: t('lot.group.floor'), rolls: recall.on_floor },
    { title: t('lot.group.store'), rolls: recall.in_store },
    { title: t('lot.group.loading'), rolls: recall.loading },
    { title: t('lot.group.dispatched'), rolls: recall.dispatched },
  ]
  const total = groups.reduce((n, g) => n + g.rolls.length, 0)
  return (
    <div className="stack">
      <Card title={t('lot.exposure', { rolls: t(total === 1 ? 'dispatch.rolls.one' : 'dispatch.rolls.many', { count: total }) })}>
        {total === 0 ? (
          <p className="muted">{t('lot.noRolls')}</p>
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
                        <th>{t('qc.col.roll')}</th>
                        <th>{t('qc.col.order')}</th>
                        <th>{t('qc.col.buyer')}</th>
                        <th className="num">{t('dispatch.col.metres')}</th>
                        <th>{t('qc.col.status')}</th>
                        <th>{t('lot.col.dispatch')}</th>
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
        <Card title={t('lot.buyersToContact')}>
          <div className="stack">
            <Table>
              <thead>
                <tr>
                  <th>{t('qc.col.buyer')}</th>
                  <th>{t('lot.col.rollsFromLot')}</th>
                  <th>{t('lot.col.dispatches')}</th>
                </tr>
              </thead>
              <tbody>
                {recall.buyers.map((b) => (
                  <tr key={b.buyer_id}>
                    <td>{b.buyer_name}</td>
                    <td>
                      {t('lot.alreadySent', { sent: b.dispatched_roll_count, total: b.roll_count })}
                    </td>
                    <td>{b.dispatch_codes.length ? b.dispatch_codes.join(', ') : <span className="muted">{t('lot.noneYet')}</span>}</td>
                  </tr>
                ))}
              </tbody>
            </Table>
            <p className="muted text-sm">{t('lot.draftNote')}</p>
          </div>
        </Card>
      )}
    </div>
  )
}

/* ---------- block lot ---------- */

function BlockButton({ lot }: { lot: Lot }) {
  const { t } = useI18n()
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
      if (!text) return setFieldError(t('lot.reasonEnter'))
      setFieldError(undefined)
      setError(null)
      try {
        await call(api.POST('/api/lots/{lot_code}/block', { params: { path: { lot_code: lot.lot_code } }, body: { reason: text } }))
        toast.success(t('lot.blockedToast', { code: lot.lot_code }))
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
        <Ban size={16} aria-hidden /> {t('lot.blockButton')}
      </Button>
      <Dialog open={open} onClose={close} title={t('lot.blockTitle', { code: lot.lot_code })}>
        <div className="stack">
          <p>
            {t('lot.blockBody')}
          </p>
          <Field label={t('lot.reason')} error={fieldError}>
            {(c) => <Textarea {...c} value={reason} onChange={(e) => setReason(e.target.value)} />}
          </Field>
          {error && <Alert tone="error">{error}</Alert>}
          <div className="row">
            <SubmitButton variant="danger" pending={pending} onClick={submit}>
              {t('lot.blockConfirm')}
            </SubmitButton>
            <Button variant="secondary" onClick={close}>
              {t('lot.keepUsing')}
            </Button>
          </div>
        </div>
      </Dialog>
    </>
  )
}
