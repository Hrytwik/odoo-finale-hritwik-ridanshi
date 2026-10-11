import { useQuery } from '@tanstack/react-query'
import { AlertTriangle, ArrowRightLeft, CircleStop, Hammer, Layers, Play, Scissors, Wrench } from 'lucide-react'
import { useState } from 'react'
import { useParams } from 'react-router-dom'
import { ActionDialog } from '@/components/common/ActionDialog'
import { EmptyState } from '@/components/common/EmptyState'
import { PageHeader } from '@/components/common/PageHeader'
import { QueryBoundary } from '@/components/common/QueryBoundary'
import { StatusBadge } from '@/components/common/StatusBadge'
import { Reveal } from '@/components/motion/Reveal'
import { Badge } from '@/components/ui/Badge'
import { Button } from '@/components/ui/Button'
import { Card } from '@/components/ui/Card'
import { Field, Input, Select, Textarea } from '@/components/ui/Field'
import { ProgressBar } from '@/components/ui/ProgressBar'
import { Table } from '@/components/ui/Table'
import type { Key } from '@/i18n/en'
import { useI18n } from '@/i18n/I18nContext'
import { api, call, type components } from '@/lib/api'
import { formatDateTime, formatKg, formatMetres } from '@/lib/format'
import { useAction } from '@/lib/useAction'

type Detail = components['schemas']['MachineDetail']
type Run = components['schemas']['RunOut']

/** Everything a floor action can change: the board, this machine, the order screens and the stock. */
const REFRESH = [['floor'], ['machine'], ['orders'], ['stock']]

export default function MachineDetail() {
  const { code = '' } = useParams()
  const machine = useQuery({
    queryKey: ['machine', code],
    queryFn: () => call(api.GET('/api/machines/{machine_code}', { params: { path: { machine_code: code } } })),
    enabled: !!code,
  })
  return <QueryBoundary query={machine}>{(m) => <Machine m={m} />}</QueryBoundary>
}

function Machine({ m }: { m: Detail }) {
  const { t } = useI18n()
  return (
    <>
      <PageHeader title={m.name} description={t('machine.subtitle', { code: m.code, stage: t(`floor.stage.${m.stage}` as Key) })} actions={<Actions m={m} />} />
      <div className="stack">
        <div className="row">
          <StatusBadge kind="machine" value={m.status} />
          <span className="muted text-sm">
            {t('floor.today')}: <strong>{m.output_unit === 'kg' ? formatKg(m.output_today) : formatMetres(m.output_today)}</strong>
          </span>
        </div>

        {m.status === 'down' && m.downtime && (
          <div className="machine-note machine-note-down">
            <AlertTriangle size={18} aria-hidden />
            <span>
              <strong>{m.downtime.reason}</strong>
              <br />
              <span className="text-sm">{t('floor.downSince', { time: formatDateTime(m.downtime.started_at) })}</span>
            </span>
          </div>
        )}

        {m.current_run && (
          <Reveal>
            <Card title={t('machine.runningNow')}>
              <div className="stack-sm">
                <p>
                  <strong>{m.current_run.order_code}</strong> · {t('machine.runningLine', { operator: m.current_run.operator.name, time: formatDateTime(m.current_run.started_at) })}
                </p>
                <ProgressBar label={t('floor.orderProgress')} value={m.current_run.order_progress_pct} max={100} tone="blue" unit="%" />
              </div>
            </Card>
          </Reveal>
        )}

        <Reveal>
          <Card title={t('machine.recentRuns')}>
            <RecentRuns runs={m.recent_runs} />
          </Card>
        </Reveal>
      </div>
    </>
  )
}

function RecentRuns({ runs }: { runs: Run[] }) {
  const { t } = useI18n()
  if (runs.length === 0) return <EmptyState title={t('machine.noRuns')} />
  return (
    <Table>
      <thead>
        <tr>
          <th>{t('machine.col.run')}</th>
          <th>{t('qc.col.order')}</th>
          <th>{t('qc.rework.operator')}</th>
          <th>{t('machine.col.started')}</th>
          <th>{t('machine.col.ended')}</th>
          <th className="num">{t('machine.col.output')}</th>
        </tr>
      </thead>
      <tbody>
        {runs.map((r) => (
          <tr key={r.id}>
            <td>#{r.id}</td>
            <td>{r.order_code}</td>
            <td>{r.operator.name}</td>
            <td className="nowrap">{formatDateTime(r.started_at)}</td>
            <td className="nowrap">{r.ended_at ? formatDateTime(r.ended_at) : <Badge tone="green">{t('floor.running')}</Badge>}</td>
            <td className="num">{r.stage === 'spinning' ? (r.output_kg === null ? '-' : formatKg(r.output_kg)) : formatMetres(r.metres)}</td>
          </tr>
        ))}
      </tbody>
    </Table>
  )
}

/* ---------- actions ---------- */

type Kind = 'start' | 'end' | 'handover' | 'rolloff' | 'load' | 'issue' | 'breakdown' | null

function Actions({ m }: { m: Detail }) {
  const { t } = useI18n()
  const [open, setOpen] = useState<Kind>(null)
  const close = () => setOpen(null)
  const run = m.current_run
  const repair = useAction({ invalidate: REFRESH })

  if (m.status === 'down') {
    return (
      <Button
        onClick={() =>
          repair.act(() => call(api.POST('/api/machines/{machine_code}/repair', { params: { path: { machine_code: m.code } } })), t('machine.repairedToast', { name: m.name }))
        }
        aria-busy={repair.pending}
      >
        <Wrench size={16} aria-hidden /> {t('machine.markRepaired')}
      </Button>
    )
  }

  return (
    <>
      {!run && (
        <Button onClick={() => setOpen('start')}>
          <Play size={16} aria-hidden /> {t('machine.startRun')}
        </Button>
      )}
      {run && m.stage === 'weaving' && (
        <Button onClick={() => setOpen('rolloff')}>
          <Scissors size={16} aria-hidden /> {t('machine.rollOff')}
        </Button>
      )}
      {run && m.stage === 'dyeing' && (
        <Button onClick={() => setOpen('load')}>
          <Layers size={16} aria-hidden /> {t('machine.loadRolls')}
        </Button>
      )}
      {run && m.stage === 'spinning' && (
        <Button onClick={() => setOpen('issue')}>
          <Hammer size={16} aria-hidden /> {t('machine.issueYarn')}
        </Button>
      )}
      {run && (
        <Button variant="secondary" onClick={() => setOpen('handover')}>
          <ArrowRightLeft size={16} aria-hidden /> {t('machine.handOver')}
        </Button>
      )}
      {run && (
        <Button variant="secondary" onClick={() => setOpen('end')}>
          <CircleStop size={16} aria-hidden /> {t('machine.endRun')}
        </Button>
      )}
      <Button variant="secondary" onClick={() => setOpen('breakdown')}>
        <AlertTriangle size={16} aria-hidden /> {t('machine.reportBreakdown')}
      </Button>

      <StartRunDialog m={m} open={open === 'start'} onClose={close} />
      {run && <EndRunDialog m={m} runId={run.id} open={open === 'end'} onClose={close} />}
      {run && <HandoverDialog m={m} runId={run.id} currentOperatorId={run.operator.id} open={open === 'handover'} onClose={close} />}
      {run && <RollOffDialog runId={run.id} open={open === 'rolloff'} onClose={close} />}
      {run && <LoadRollsDialog runId={run.id} open={open === 'load'} onClose={close} />}
      {run && <IssueYarnDialog runId={run.id} open={open === 'issue'} onClose={close} />}
      <BreakdownDialog m={m} open={open === 'breakdown'} onClose={close} />
    </>
  )
}

type DialogProps = { open: boolean; onClose: () => void }

/** Active operators only: inspectors and people who have left cannot be put on a machine. */
function useOperators(enabled: boolean) {
  return useQuery({
    queryKey: ['people', 'workers'],
    queryFn: async () => (await call(api.GET('/api/workers'))).filter((w) => w.role === 'operator' && w.active),
    enabled,
  })
}

function OperatorSelect({ label, value, onChange, exclude, error, enabled }: { label: string; value: string; onChange: (v: string) => void; exclude?: number; error?: string; enabled: boolean }) {
  const { t } = useI18n()
  const operators = useOperators(enabled)
  return (
    <Field label={label} error={error}>
      {(c) => (
        <Select {...c} value={value} onChange={(e) => onChange(e.target.value)}>
          <option value="">{t('qc.rework.selectOperator')}</option>
          {(operators.data ?? [])
            .filter((w) => w.id !== exclude)
            .map((w) => (
              <option key={w.id} value={w.id}>
                {w.name}
              </option>
            ))}
        </Select>
      )}
    </Field>
  )
}

function StartRunDialog({ m, open, onClose }: { m: Detail; open: boolean } & Pick<DialogProps, 'onClose'>) {
  const { t } = useI18n()
  const [order, setOrder] = useState('')
  const [operator, setOperator] = useState('')
  const [inputRun, setInputRun] = useState('')
  const [errors, setErrors] = useState<Record<string, string>>({})
  const { act, pending, error } = useAction({ invalidate: REFRESH, onDone: onClose })
  const orders = useQuery({ queryKey: ['orders'], queryFn: () => call(api.GET('/api/orders', { params: { query: { state: 'confirmed' } } })), enabled: open })
  const board = useQuery({ queryKey: ['floor'], queryFn: () => call(api.GET('/api/floor')), enabled: open && m.stage === 'weaving' })
  const needsInput = m.stage === 'weaving'
  // open spinning runs for the chosen order, offered as quick picks
  const candidates = (board.data?.machines ?? []).filter((x) => x.stage === 'spinning' && x.current_run && x.current_run.order_code === order)

  function submit() {
    const next: Record<string, string> = {}
    if (!order) next.order = t('machine.chooseOrder')
    if (!operator) next.operator = t('machine.chooseOperator')
    if (needsInput && !(Number.isInteger(Number(inputRun)) && Number(inputRun) > 0)) next.input = t('machine.needSpinningRun')
    setErrors(next)
    if (Object.keys(next).length) return
    return act(
      () =>
        call(
          api.POST('/api/runs', {
            body: { order_code: order, machine_code: m.code, operator_worker_id: Number(operator), ...(needsInput ? { input_run_id: Number(inputRun) } : {}) },
          }),
        ),
      t('machine.startedToast', { name: m.name }),
    )
  }

  return (
    <ActionDialog open={open} onClose={onClose} title={t('machine.startTitle', { name: m.name })} confirmLabel={t('machine.startRun')} onConfirm={submit} pending={pending} error={error}>
      <Field label={t('qc.col.order')} error={errors.order}>
        {(c) => (
          <Select {...c} value={order} onChange={(e) => setOrder(e.target.value)}>
            <option value="">{t('machine.selectOrder')}</option>
            {(orders.data ?? []).map((o) => (
              <option key={o.code} value={o.code}>
                {o.code} · {o.buyer.name}
              </option>
            ))}
          </Select>
        )}
      </Field>
      <OperatorSelect label={t('qc.rework.operator')} value={operator} onChange={setOperator} error={errors.operator} enabled={open} />
      {needsInput && (
        <Field label={t('machine.spinningRun')} error={errors.input} hint={t('machine.spinningRunHint')}>
          {(c) => <Input {...c} inputMode="numeric" value={inputRun} onChange={(e) => setInputRun(e.target.value)} />}
        </Field>
      )}
      {needsInput && candidates.length > 0 && (
        <div className="row">
          {candidates.map((x) => (
            <Button key={x.code} variant="secondary" onClick={() => setInputRun(String(x.current_run!.id))}>
              {t('machine.runOn', { id: x.current_run!.id, code: x.code })}
            </Button>
          ))}
        </div>
      )}
    </ActionDialog>
  )
}

function EndRunDialog({ m, runId, open, onClose }: { m: Detail; runId: number } & DialogProps) {
  const { t } = useI18n()
  const [kg, setKg] = useState('')
  const [err, setErr] = useState<string | undefined>()
  const { act, pending, error } = useAction({ invalidate: REFRESH, onDone: onClose })
  const spinning = m.stage === 'spinning'

  function submit() {
    if (spinning && (kg.trim() === '' || !(Number(kg) >= 0))) return setErr(t('machine.enterKilos'))
    setErr(undefined)
    return act(
      () => call(api.POST('/api/runs/{run_id}/end', { params: { path: { run_id: runId } }, body: spinning ? { output_kg: Number(kg) } : {} })),
      t('machine.endedToast'),
    )
  }

  return (
    <ActionDialog open={open} onClose={onClose} title={t('machine.endTitle')} confirmLabel={t('machine.endRun')} onConfirm={submit} pending={pending} error={error}>
      <p>{t('machine.endBody')}</p>
      {spinning && (
        <Field label={t('machine.kilosSpun')} error={err}>
          {(c) => <Input {...c} type="number" inputMode="decimal" step="any" value={kg} onChange={(e) => setKg(e.target.value)} />}
        </Field>
      )}
    </ActionDialog>
  )
}

function HandoverDialog({ m, runId, currentOperatorId, open, onClose }: { m: Detail; runId: number; currentOperatorId: number } & DialogProps) {
  const { t } = useI18n()
  const [operator, setOperator] = useState('')
  const [err, setErr] = useState<string | undefined>()
  const { act, pending, error } = useAction({ invalidate: REFRESH, onDone: onClose })

  function submit() {
    if (!operator) return setErr(t('machine.chooseNewOperator'))
    setErr(undefined)
    return act(() => call(api.POST('/api/runs/{run_id}/handover', { params: { path: { run_id: runId } }, body: { operator_worker_id: Number(operator) } })), t('machine.handedToast', { name: m.name }))
  }

  return (
    <ActionDialog open={open} onClose={onClose} title={t('machine.handoverTitle')} confirmLabel={t('machine.handOver')} onConfirm={submit} pending={pending} error={error}>
      <p>{t('machine.handoverBody')}</p>
      <OperatorSelect label={t('machine.newOperator')} value={operator} onChange={setOperator} exclude={currentOperatorId} error={err} enabled={open} />
    </ActionDialog>
  )
}

function RollOffDialog({ runId, open, onClose }: { runId: number } & DialogProps) {
  const { t } = useI18n()
  const [metres, setMetres] = useState('')
  const [err, setErr] = useState<string | undefined>()
  const { act, pending, error } = useAction({ invalidate: REFRESH, onDone: onClose })

  function submit() {
    const n = Number(metres)
    if (metres.trim() === '' || !(n > 0)) return setErr(t('machine.enterMetres'))
    setErr(undefined)
    return act(
      async () => {
        const roll = await call(api.POST('/api/runs/{run_id}/rolls', { params: { path: { run_id: runId } }, body: { metres: n } }))
        setMetres('')
        return roll
      },
      (roll) => t('machine.rollCreated', { code: roll.code, metres: formatMetres(roll.metres) }),
    )
  }

  return (
    <ActionDialog open={open} onClose={onClose} title={t('machine.rollOffTitle')} confirmLabel={t('machine.rollOff')} onConfirm={submit} pending={pending} error={error}>
      <p>{t('machine.rollOffBody')}</p>
      <Field label={t('dispatch.col.metres')} error={err}>
        {(c) => <Input {...c} type="number" inputMode="decimal" step="any" value={metres} onChange={(e) => setMetres(e.target.value)} />}
      </Field>
    </ActionDialog>
  )
}

function LoadRollsDialog({ runId, open, onClose }: { runId: number } & DialogProps) {
  const { t } = useI18n()
  const [text, setText] = useState('')
  const [err, setErr] = useState<string | undefined>()
  const { act, pending, error } = useAction({ invalidate: REFRESH, onDone: onClose })

  function submit() {
    const codes = text.split(/[\s,;]+/).map((c) => c.trim().toUpperCase()).filter(Boolean)
    if (codes.length === 0) return setErr(t('machine.enterOneRoll'))
    setErr(undefined)
    return act(() => call(api.POST('/api/runs/{run_id}/load-rolls', { params: { path: { run_id: runId } }, body: { roll_codes: codes } })), t(codes.length === 1 ? 'machine.loaded.one' : 'machine.loaded.many', { count: codes.length }))
  }

  return (
    <ActionDialog open={open} onClose={onClose} title={t('machine.loadTitle')} confirmLabel={t('machine.loadRolls')} onConfirm={submit} pending={pending} error={error}>
      <Field label={t('machine.rollCodes')} error={err} hint={t('machine.rollCodesHint')}>
        {(c) => <Textarea {...c} value={text} onChange={(e) => setText(e.target.value)} />}
      </Field>
    </ActionDialog>
  )
}

function IssueYarnDialog({ runId, open, onClose }: { runId: number } & DialogProps) {
  const { t } = useI18n()
  const [lot, setLot] = useState('')
  const [qty, setQty] = useState('')
  const [errors, setErrors] = useState<Record<string, string>>({})
  const { act, pending, error } = useAction({ invalidate: REFRESH, onDone: onClose })
  const lots = useQuery({ queryKey: ['lots'], queryFn: () => call(api.GET('/api/lots')), enabled: open })
  const usable = (lots.data ?? []).filter((l) => !l.is_blocked)

  function submit() {
    const next: Record<string, string> = {}
    if (!lot) next.lot = t('machine.chooseLot')
    if (!(Number(qty) > 0)) next.qty = t('machine.enterQty')
    setErrors(next)
    if (Object.keys(next).length) return
    return act(() => call(api.POST('/api/movements/issue', { body: { lot_code: lot, run_id: runId, qty_kg: Number(qty) } })), t('machine.issuedToast', { qty: formatKg(Number(qty)), lot }))
  }

  return (
    <ActionDialog open={open} onClose={onClose} title={t('machine.issueTitle')} confirmLabel={t('machine.issueYarn')} onConfirm={submit} pending={pending} error={error}>
      <Field label={t('machine.lot')} error={errors.lot}>
        {(c) => (
          <Select {...c} value={lot} onChange={(e) => setLot(e.target.value)}>
            <option value="">{t('machine.selectLot')}</option>
            {usable.map((l) => (
              <option key={l.lot_code} value={l.lot_code}>
                {t('machine.lotOption', { code: l.lot_code, yarn: l.yarn_type.name, qty: formatKg(l.on_hand_kg) })}
              </option>
            ))}
          </Select>
        )}
      </Field>
      <Field label={t('store.receive.qty')} error={errors.qty}>
        {(c) => <Input {...c} type="number" inputMode="decimal" step="any" value={qty} onChange={(e) => setQty(e.target.value)} />}
      </Field>
    </ActionDialog>
  )
}

function BreakdownDialog({ m, open, onClose }: { m: Detail } & DialogProps) {
  const { t } = useI18n()
  const [reason, setReason] = useState('')
  const [err, setErr] = useState<string | undefined>()
  const { act, pending, error } = useAction({ invalidate: REFRESH, onDone: onClose })

  function submit() {
    if (!reason.trim()) return setErr(t('machine.sayWhat'))
    setErr(undefined)
    return act(
      async () => {
        const card = await call(api.POST('/api/machines/{machine_code}/breakdown', { params: { path: { machine_code: m.code } }, body: { reason: reason.trim() } }))
        setReason('')
        return card
      },
      t('machine.downToast', { name: m.name }),
    )
  }

  return (
    <ActionDialog open={open} onClose={onClose} title={t('machine.breakdownTitle', { name: m.name })} confirmLabel={t('machine.reportBreakdown')} onConfirm={submit} pending={pending} error={error} danger>
      <p>{t('machine.breakdownBody')}</p>
      <Field label={t('machine.whatWrong')} error={err}>
        {(c) => <Textarea {...c} value={reason} onChange={(e) => setReason(e.target.value)} />}
      </Field>
    </ActionDialog>
  )
}
