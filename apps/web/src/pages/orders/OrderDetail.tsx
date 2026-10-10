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
import type { Key } from '@/i18n/en'
import { useI18n } from '@/i18n/I18nContext'
import { api, call, errorMessage, type components } from '@/lib/api'
import { useMe } from '@/lib/auth'
import { todayIso } from '@/lib/dates'
import { useSubmitLock } from '@/lib/forms'
import { formatDate, formatKg, formatMetres, formatMoney } from '@/lib/format'
import { DelayNoticeButton } from './DelayNotice'
import { ShipmentsCard } from './Shipments'

type Order = components['schemas']['OrderOut']


export default function OrderDetail() {
  const { t } = useI18n()
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
              {o.state === 'draft' && <Badge tone="gray">{t('orders.draftBadge')}</Badge>}
            </div>
            <AnimatedGroup className="grid-cards">
              <KpiCard label={t('orders.kpi.ordered')} value={o.qty_metres} format={formatMetres} />
              <KpiCard label={t('orders.kpi.passed')} value={o.progress.passed_m} format={formatMetres} />
              <KpiCard label={t('orders.kpi.dispatched')} value={o.progress.dispatched_m} format={formatMetres} />
              <KpiCard label={t('orders.kpi.price')} value={o.price_per_metre} format={formatMoney} />
            </AnimatedGroup>
            <Reveal>
              <ProgressCard order={o} />
            </Reveal>
            {role === 'owner' && o.state === 'confirmed' && (
              <Reveal>
                <ShipmentsCard order={o} />
              </Reveal>
            )}
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
  const { t } = useI18n()
  const p = order.progress
  const q = order.qty_metres
  return (
    <Card title={t('orders.progress')}>
      <div className="stack">
        <ProgressBar label={t('orders.bar.spun')} value={p.spun_kg} max={p.need_kg} unit="kg" tone="blue" />
        <ProgressBar label={t('orders.bar.woven')} value={p.woven_m} max={q} unit="m" tone="blue" />
        <ProgressBar label={t('orders.bar.dyed')} value={p.dyed_m} max={q} unit="m" tone="violet" />
        <ProgressBar label={t('orders.kpi.passed')} value={p.passed_m} max={q} unit="m" tone="green" />
        <ProgressBar label={t('orders.kpi.dispatched')} value={p.dispatched_m} max={q} unit="m" tone="gray" />
        <ProgressBar label={t('ship.rejectedLabel')} value={p.rejected_m} max={q} unit="m" tone="red" />
      </div>
    </Card>
  )
}

function DeliveryCard({ query, deadline }: { query: ReturnType<typeof useQuery<components['schemas']['EtaOut']>>; deadline: string }) {
  const { t } = useI18n()
  const stageName = (s: string) => t(`floor.stage.${s}` as Key)
  const lateText = (days: number) => (days <= 0 ? t('insight.onTime').toLowerCase() : t(days === 1 ? 'insight.dayLate' : 'insight.daysLate', { days }))
  return (
    <Card title={t('orders.delivery')}>
      <QueryBoundary query={query} rows={2}>
        {(eta) => (
          <div className="stack">
            <div className="row">
              <CalendarClock size={18} aria-hidden />
              <span>
                {t('orders.expectedDelivery', { date: formatDate(eta.delivery_date), deadline: formatDate(deadline) })}
              </span>
              <Badge tone={eta.days_late > 0 ? 'red' : 'green'}>{lateText(eta.days_late)}</Badge>
            </div>
            {eta.bottleneck_stage && (
              <p className="muted text-sm">
                {t('orders.bottleneck', { stage: stageName(eta.bottleneck_stage) })}
              </p>
            )}
            <div className="row">
              {eta.stages.map((s) => (
                <Badge key={s.stage} tone="blue">
                  {t('orders.stageDoneOn', { stage: stageName(s.stage), date: formatDate(s.finish_date) })}
                </Badge>
              ))}
            </div>
            {eta.what_ifs.length > 0 && (
              <div className="stack-sm">
                <strong className="text-sm">{t('orders.whatIf')}</strong>
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
  const { t } = useI18n()
  return (
    <Card title={t('orders.yarnCheck')}>
      <QueryBoundary query={query} rows={2}>
        {(check) => {
          const short = check.lines.reduce((sum, l) => sum + l.short_kg, 0)
          return (
            <div className="stack">
              <div>{check.can_start ? <Badge tone="green">{t('orders.enoughYarn')}</Badge> : <Badge tone="red">{t('orders.yarnShort', { qty: formatKg(short) })}</Badge>}</div>
              <Table>
                <thead>
                  <tr>
                    <th>{t('passport.yarn')}</th>
                    <th className="num">{t('orders.col.needed')}</th>
                    <th className="num">{t('orders.col.issued')}</th>
                    <th className="num">{t('orders.col.available')}</th>
                    <th className="num">{t('orders.col.short')}</th>
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
  const { t } = useI18n()
  return (
    <Card title={t('orders.cost.title')}>
      <QueryBoundary query={query} rows={3}>
        {(c) => (
          <div className="stack">
            <AnimatedGroup className="grid-cards">
              <KpiCard label={t('orders.cost.total')} value={c.total} format={formatMoney} />
              <KpiCard label={t('chart.revenue')} value={c.revenue} format={formatMoney} hint={t('orders.cost.goodMetres', { metres: formatMetres(c.good_metres) })} />
              <KpiCard label={t('chart.profitWord')} value={c.profit} format={formatMoney} tone={c.profit < 0 ? 'danger' : undefined} hint={c.provisional ? t('orders.cost.provisional') : t('orders.cost.final')} />
            </AnimatedGroup>
            <Table>
              <thead>
                <tr>
                  <th>{t('passport.whereMoney')}</th>
                  <th className="num">{t('common.amount')}</th>
                </tr>
              </thead>
              <tbody>
                <tr>
                  <td>{t('passport.yarn')}</td>
                  <td className="num">{formatMoney(c.parts.yarn)}</td>
                </tr>
                <tr>
                  <td>{t('passport.machinesCost')}</td>
                  <td className="num">{formatMoney(c.parts.machine)}</td>
                </tr>
                <tr>
                  <td>{t('passport.labour')}</td>
                  <td className="num">{formatMoney(c.parts.labour)}</td>
                </tr>
                <tr>
                  <td>{t('passport.stage.rework')}</td>
                  <td className="num">{formatMoney(c.parts.rework)}</td>
                </tr>
                <tr>
                  <td>{t('orders.cost.rejectedRolls', { metres: formatMetres(c.rejected_metres) })}</td>
                  <td className="num">{formatMoney(c.reject_cost)}</td>
                </tr>
              </tbody>
            </Table>
            {c.cost_per_good_metre !== null && (
              <p className="muted text-sm">
                {t('orders.cost.trueCost', { amount: formatMoney(c.cost_per_good_metre) })}
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
  const { t } = useI18n()
  const [open, setOpen] = useState<DialogKind>(null)
  if (!canWrite || order.state === 'cancelled') return null
  return (
    <>
      {order.state === 'draft' && (
        <Button onClick={() => setOpen('confirm')}>
          <CheckCircle2 size={16} aria-hidden /> {t('orders.confirm')}
        </Button>
      )}
      {order.state === 'confirmed' && (
        <Button variant="secondary" onClick={() => setOpen('deadline')}>
          {t('orders.changeDeadline')}
        </Button>
      )}
      {order.state === 'confirmed' && <DelayNoticeButton orderCode={order.code} buyerName={order.buyer.name} />}
      <Button variant="secondary" onClick={() => setOpen('cancel')}>
        <XCircle size={16} aria-hidden /> {t('orders.cancelOrder')}
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
  const { t } = useI18n()
  const { act, pending, error, path } = useOrderAction(order, onClose)
  return (
    <ActionDialog open={open} onClose={onClose} title={t('orders.confirmTitle', { code: order.code })} error={error}>
      <p>
        {t('orders.confirmBody', { buyer: order.buyer.name })}
      </p>
      <div className="row">
        <SubmitButton pending={pending} onClick={() => act(() => call(api.POST('/api/orders/{order_code}/confirm', path)), t('orders.confirmedToast', { code: order.code }))}>
          {t('orders.confirm')}
        </SubmitButton>
        <Button variant="secondary" onClick={onClose}>
          {t('orders.notYet')}
        </Button>
      </div>
    </ActionDialog>
  )
}

function CancelDialog({ order, open, onClose }: { order: Order; open: boolean; onClose: () => void }) {
  const { t } = useI18n()
  const { act, pending, error, path } = useOrderAction(order, onClose)
  return (
    <ActionDialog open={open} onClose={onClose} title={t('orders.cancelTitle', { code: order.code })} error={error}>
      <p>{t('orders.cancelBody')}</p>
      <div className="row">
        <SubmitButton variant="danger" pending={pending} onClick={() => act(() => call(api.POST('/api/orders/{order_code}/cancel', path)), t('orders.cancelledToast', { code: order.code }))}>
          {t('orders.yesCancel')}
        </SubmitButton>
        <Button variant="secondary" onClick={onClose}>
          {t('orders.keepOrder')}
        </Button>
      </div>
    </ActionDialog>
  )
}

function DeadlineDialog({ order, open, onClose }: { order: Order; open: boolean; onClose: () => void }) {
  const { t } = useI18n()
  const { act, pending, error, setError, path } = useOrderAction(order, onClose)
  const [deadline, setDeadline] = useState(order.deadline)
  const [today] = useState(todayIso)
  return (
    <ActionDialog open={open} onClose={onClose} title={t('orders.changeDeadline')} error={error}>
      <Field label={t('orders.newDeadline')} error={deadline && deadline < today ? t('orders.err.deadlinePast') : undefined}>
        {(c) => <Input {...c} type="date" min={today} value={deadline} onChange={(e) => setDeadline(e.target.value)} />}
      </Field>
      <div className="row">
        <SubmitButton
          pending={pending}
          onClick={() => {
            if (!deadline || deadline < today) return setError(t('orders.deadlineTodayOrLater'))
            return act(() => call(api.PATCH('/api/orders/{order_code}', { ...path, body: { deadline } })), t('orders.deadlineChanged'))
          }}
        >
          {t('orders.saveDeadline')}
        </SubmitButton>
        <Button variant="secondary" onClick={onClose}>
          {t('dispatch.cancel')}
        </Button>
      </div>
    </ActionDialog>
  )
}
