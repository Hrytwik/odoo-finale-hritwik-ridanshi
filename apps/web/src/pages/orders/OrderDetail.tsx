import { useQuery, useQueryClient } from '@tanstack/react-query'
import { CalendarClock, CheckCircle2, XCircle } from 'lucide-react'
import { useState, type ReactNode } from 'react'
import { useParams } from 'react-router-dom'
import { toast } from 'sonner'
import { Alert } from '@/components/common/Alert'
import { KpiCard } from '@/components/common/KpiCard'
import { PageHeader } from '@/components/common/PageHeader'
import { QueryBoundary } from '@/components/common/QueryBoundary'
import { StatusBadge } from '@/components/common/StatusBadge'
import { SubmitButton } from '@/components/common/SubmitButton'
import { AnimatedGroup } from '@/components/motion/AnimatedGroup'
import { Reveal } from '@/components/motion/Reveal'
import { Badge } from '@/components/ui/Badge'
import { Button } from '@/components/ui/Button'
import { Card } from '@/components/ui/Card'
import { Dialog } from '@/components/ui/Dialog'
import { Field, Input } from '@/components/ui/Field'
import { ProgressBar } from '@/components/ui/ProgressBar'
import { Table } from '@/components/ui/Table'
import { api, call, errorMessage, type components } from '@/lib/api'
import { useMe } from '@/lib/auth'
import { todayIso } from '@/lib/dates'
import { useSubmitLock } from '@/lib/forms'
import { formatDate, formatKg, formatMetres, formatMoney } from '@/lib/format'
import { DelayNoticeButton } from './DelayNotice'

type Order = components['schemas']['OrderOut']

const STAGE_NAME = { spinning: 'Spinning', weaving: 'Weaving', dyeing: 'Dyeing' } as const

function lateText(days: number) {
  if (days <= 0) return 'on time'
  return `${days} ${days === 1 ? 'day' : 'days'} late`
}

export default function OrderDetail() {
  const { code = '' } = useParams()
  const me = useMe()
  const role = me.data?.role
  const canWrite = role === 'owner' || role === 'accountant'
  const canPlan = canWrite || role === 'supervisor'
  const path = { params: { path: { order_code: code } } }

  const order = useQuery({ queryKey: ['orders', code], queryFn: () => call(api.GET('/api/orders/{order_code}', path)), enabled: !!code })
  const eta = useQuery({ queryKey: ['orders', code, 'eta'], queryFn: () => call(api.GET('/api/orders/{order_code}/eta', path)), enabled: !!code && canPlan })
  const yarn = useQuery({ queryKey: ['orders', code, 'yarn-check'], queryFn: () => call(api.GET('/api/orders/{order_code}/yarn-check', path)), enabled: !!code })
  const cost = useQuery({ queryKey: ['orders', code, 'cost'], queryFn: () => call(api.GET('/api/costing/orders/{order_code}', path)), enabled: !!code && canWrite })

  return (
    <QueryBoundary query={order}>
      {(o) => (
        <>
          <PageHeader
            title={o.code}
            description={`${o.buyer.name} · ${o.fabric_type.name}, ${o.colour}`}
            actions={<Actions order={o} canWrite={canWrite} />}
          />
          <div className="stack">
            <div className="row">
              <StatusBadge kind="order" value={o.stage} />
              {o.state === 'draft' && <Badge tone="gray">Draft: not confirmed yet</Badge>}
            </div>
            <AnimatedGroup className="grid-cards">
              <KpiCard label="Ordered" value={o.qty_metres} format={formatMetres} />
              <KpiCard label="Passed quality check" value={o.progress.passed_m} format={formatMetres} />
              <KpiCard label="Dispatched" value={o.progress.dispatched_m} format={formatMetres} />
              <KpiCard label="Price per metre" value={o.price_per_metre} format={formatMoney} />
            </AnimatedGroup>
            <Reveal>
              <ProgressCard order={o} />
            </Reveal>
            {canPlan && (
              <Reveal>
                <DeliveryCard query={eta} deadline={o.deadline} />
              </Reveal>
            )}
            <Reveal>
              <YarnCard query={yarn} />
            </Reveal>
            {canWrite && (
              <Reveal>
                <CostCard query={cost} />
              </Reveal>
            )}
          </div>
        </>
      )}
    </QueryBoundary>
  )
}

function ProgressCard({ order }: { order: Order }) {
  const p = order.progress
  const q = order.qty_metres
  return (
    <Card title="Progress">
      <div className="stack">
        <ProgressBar label="Yarn spun" value={p.spun_kg} max={p.need_kg} unit="kg" tone="blue" />
        <ProgressBar label="Woven" value={p.woven_m} max={q} unit="m" tone="blue" />
        <ProgressBar label="Dyed" value={p.dyed_m} max={q} unit="m" tone="violet" />
        <ProgressBar label="Passed quality check" value={p.passed_m} max={q} unit="m" tone="green" />
        <ProgressBar label="Dispatched" value={p.dispatched_m} max={q} unit="m" tone="gray" />
        <ProgressBar label="Rejected" value={p.rejected_m} max={q} unit="m" tone="red" />
      </div>
    </Card>
  )
}

function DeliveryCard({ query, deadline }: { query: ReturnType<typeof useQuery<components['schemas']['EtaOut']>>; deadline: string }) {
  return (
    <Card title="Delivery">
      <QueryBoundary query={query} rows={2}>
        {(eta) => (
          <div className="stack">
            <div className="row">
              <CalendarClock size={18} aria-hidden />
              <span>
                Expected delivery <strong>{formatDate(eta.delivery_date)}</strong>, deadline {formatDate(deadline)}
              </span>
              <Badge tone={eta.days_late > 0 ? 'red' : 'green'}>{lateText(eta.days_late)}</Badge>
            </div>
            {eta.bottleneck_stage && (
              <p className="muted text-sm">
                Bottleneck: <strong>{STAGE_NAME[eta.bottleneck_stage]}</strong>. This stage adds the most delay.
              </p>
            )}
            <div className="row">
              {eta.stages.map((s) => (
                <Badge key={s.stage} tone="blue">
                  {STAGE_NAME[s.stage]} done {formatDate(s.finish_date)}
                </Badge>
              ))}
            </div>
            {eta.what_ifs.length > 0 && (
              <div className="stack-sm">
                <strong className="text-sm">What if…</strong>
                {eta.what_ifs.map((w) => (
                  <div key={w.kind} className="shortage">
                    <span>{w.label}</span>
                    <span className="nowrap">
                      {formatDate(w.delivery_date)}, <strong>{lateText(w.days_late)}</strong>
                    </span>
                  </div>
                ))}
              </div>
            )}
          </div>
        )}
      </QueryBoundary>
    </Card>
  )
}

function YarnCard({ query }: { query: ReturnType<typeof useQuery<components['schemas']['YarnCheckOut']>> }) {
  return (
    <Card title="Yarn check">
      <QueryBoundary query={query} rows={2}>
        {(check) => {
          const short = check.lines.reduce((sum, l) => sum + l.short_kg, 0)
          return (
            <div className="stack">
              <div>{check.can_start ? <Badge tone="green">Enough yarn to start</Badge> : <Badge tone="red">Short {formatKg(short)}</Badge>}</div>
              <Table>
                <thead>
                  <tr>
                    <th>Yarn</th>
                    <th className="num">Needed</th>
                    <th className="num">Already issued</th>
                    <th className="num">Available</th>
                    <th className="num">Short</th>
                  </tr>
                </thead>
                <tbody>
                  {check.lines.map((l) => (
                    <tr key={l.yarn_type.id}>
                      <td>{l.yarn_type.name}</td>
                      <td className="num">{formatKg(l.need_kg)}</td>
                      <td className="num">{formatKg(l.issued_kg)}</td>
                      <td className="num">{formatKg(l.available_kg)}</td>
                      <td className="num">{l.short_kg > 0 ? <span className="text-danger">{formatKg(l.short_kg)}</span> : '-'}</td>
                    </tr>
                  ))}
                </tbody>
              </Table>
            </div>
          )
        }}
      </QueryBoundary>
    </Card>
  )
}

function CostCard({ query }: { query: ReturnType<typeof useQuery<components['schemas']['OrderCost']>> }) {
  return (
    <Card title="Cost and profit">
      <QueryBoundary query={query} rows={3}>
        {(c) => (
          <div className="stack">
            <AnimatedGroup className="grid-cards">
              <KpiCard label="Total cost" value={c.total} format={formatMoney} />
              <KpiCard label="Revenue" value={c.revenue} format={formatMoney} hint={`${formatMetres(c.good_metres)} good metres`} />
              <KpiCard label="Profit" value={c.profit} format={formatMoney} tone={c.profit < 0 ? 'danger' : undefined} hint={c.provisional ? 'provisional: the order is not finished' : 'final'} />
            </AnimatedGroup>
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
                  <td className="num">{formatMoney(c.parts.yarn)}</td>
                </tr>
                <tr>
                  <td>Machines</td>
                  <td className="num">{formatMoney(c.parts.machine)}</td>
                </tr>
                <tr>
                  <td>Labour</td>
                  <td className="num">{formatMoney(c.parts.labour)}</td>
                </tr>
                <tr>
                  <td>Rework</td>
                  <td className="num">{formatMoney(c.parts.rework)}</td>
                </tr>
                <tr>
                  <td>Rejected rolls ({formatMetres(c.rejected_metres)})</td>
                  <td className="num">{formatMoney(c.reject_cost)}</td>
                </tr>
              </tbody>
            </Table>
            {c.cost_per_good_metre !== null && (
              <p className="muted text-sm">
                True cost of a good metre: <strong>{formatMoney(c.cost_per_good_metre)}</strong> (rejects and rework included).
              </p>
            )}
            {c.warnings.length > 0 && (
              <Alert tone="info">
                <ul style={{ margin: 0, paddingLeft: '1.2em' }}>
                  {c.warnings.map((w) => (
                    <li key={w}>{w}</li>
                  ))}
                </ul>
              </Alert>
            )}
          </div>
        )}
      </QueryBoundary>
    </Card>
  )
}

/* ---------- actions ---------- */

type DialogKind = 'confirm' | 'cancel' | 'deadline' | null

function Actions({ order, canWrite }: { order: Order; canWrite: boolean }) {
  const [open, setOpen] = useState<DialogKind>(null)
  if (!canWrite || order.state === 'cancelled') return null
  return (
    <>
      {order.state === 'draft' && (
        <Button onClick={() => setOpen('confirm')}>
          <CheckCircle2 size={16} aria-hidden /> Confirm order
        </Button>
      )}
      {order.state === 'confirmed' && (
        <Button variant="secondary" onClick={() => setOpen('deadline')}>
          Change deadline
        </Button>
      )}
      {order.state === 'confirmed' && <DelayNoticeButton orderCode={order.code} buyerName={order.buyer.name} />}
      <Button variant="secondary" onClick={() => setOpen('cancel')}>
        <XCircle size={16} aria-hidden /> Cancel order
      </Button>
      <ConfirmDialog order={order} open={open === 'confirm'} onClose={() => setOpen(null)} />
      <CancelDialog order={order} open={open === 'cancel'} onClose={() => setOpen(null)} />
      <DeadlineDialog order={order} open={open === 'deadline'} onClose={() => setOpen(null)} />
    </>
  )
}

/** Runs one server action, shows its error inside the dialog, and refreshes the order screens when it works. */
function useOrderAction(order: Order, onDone: () => void) {
  const queryClient = useQueryClient()
  const { run, pending } = useSubmitLock()
  const [error, setError] = useState<string | null>(null)
  const act = (fn: () => Promise<unknown>, successMessage: string) =>
    run(async () => {
      setError(null)
      try {
        await fn()
        toast.success(successMessage)
        void queryClient.invalidateQueries({ queryKey: ['orders'] })
        onDone()
      } catch (err) {
        setError(errorMessage(err))
      }
    })
  return { act, pending, error, setError, path: { params: { path: { order_code: order.code } } } }
}

function ActionDialog({ open, onClose, title, error, children }: { open: boolean; onClose: () => void; title: string; error: string | null; children: ReactNode }) {
  return (
    <Dialog open={open} onClose={onClose} title={title}>
      <div className="stack">
        {children}
        {error && <Alert tone="error">{error}</Alert>}
      </div>
    </Dialog>
  )
}

function ConfirmDialog({ order, open, onClose }: { order: Order; open: boolean; onClose: () => void }) {
  const { act, pending, error, path } = useOrderAction(order, onClose)
  return (
    <ActionDialog open={open} onClose={onClose} title={`Confirm ${order.code}?`} error={error}>
      <p>
        Confirming tells the floor to plan this order for {order.buyer.name}. After this only the deadline can change, and it can be cancelled only until production starts.
      </p>
      <div className="row">
        <SubmitButton pending={pending} onClick={() => act(() => call(api.POST('/api/orders/{order_code}/confirm', path)), `${order.code} confirmed`)}>
          Confirm order
        </SubmitButton>
        <Button variant="secondary" onClick={onClose}>
          Not yet
        </Button>
      </div>
    </ActionDialog>
  )
}

function CancelDialog({ order, open, onClose }: { order: Order; open: boolean; onClose: () => void }) {
  const { act, pending, error, path } = useOrderAction(order, onClose)
  return (
    <ActionDialog open={open} onClose={onClose} title={`Cancel ${order.code}?`} error={error}>
      <p>This cannot be undone. An order that already has production runs cannot be cancelled.</p>
      <div className="row">
        <SubmitButton variant="danger" pending={pending} onClick={() => act(() => call(api.POST('/api/orders/{order_code}/cancel', path)), `${order.code} cancelled`)}>
          Yes, cancel order
        </SubmitButton>
        <Button variant="secondary" onClick={onClose}>
          Keep order
        </Button>
      </div>
    </ActionDialog>
  )
}

function DeadlineDialog({ order, open, onClose }: { order: Order; open: boolean; onClose: () => void }) {
  const { act, pending, error, setError, path } = useOrderAction(order, onClose)
  const [deadline, setDeadline] = useState(order.deadline)
  const [today] = useState(todayIso)
  return (
    <ActionDialog open={open} onClose={onClose} title="Change deadline" error={error}>
      <Field label="New deadline" error={deadline && deadline < today ? 'The deadline cannot be in the past' : undefined}>
        {(c) => <Input {...c} type="date" min={today} value={deadline} onChange={(e) => setDeadline(e.target.value)} />}
      </Field>
      <div className="row">
        <SubmitButton
          pending={pending}
          onClick={() => {
            if (!deadline || deadline < today) return setError('Choose a deadline that is today or later')
            return act(() => call(api.PATCH('/api/orders/{order_code}', { ...path, body: { deadline } })), 'Deadline changed')
          }}
        >
          Save deadline
        </SubmitButton>
        <Button variant="secondary" onClick={onClose}>
          Cancel
        </Button>
      </div>
    </ActionDialog>
  )
}
