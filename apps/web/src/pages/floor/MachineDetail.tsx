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
  return (
    <>
      <PageHeader title={m.name} description={`${m.code} · ${m.stage} machine`} actions={<Actions m={m} />} />
      <div className="stack">
        <div className="row">
          <StatusBadge kind="machine" value={m.status} />
          <span className="muted text-sm">
            Today: <strong>{m.output_unit === 'kg' ? formatKg(m.output_today) : formatMetres(m.output_today)}</strong>
          </span>
        </div>

        {m.status === 'down' && m.downtime && (
          <div className="machine-note machine-note-down">
            <AlertTriangle size={18} aria-hidden />
            <span>
              <strong>{m.downtime.reason}</strong>
              <br />
              <span className="text-sm">Down since {formatDateTime(m.downtime.started_at)}</span>
            </span>
          </div>
        )}

        {m.current_run && (
          <Reveal>
            <Card title="Running now">
              <div className="stack-sm">
                <p>
                  <strong>{m.current_run.order_code}</strong> · {m.current_run.operator.name}, since {formatDateTime(m.current_run.started_at)}
                </p>
                <ProgressBar label="Order progress" value={m.current_run.order_progress_pct} max={100} tone="blue" unit="%" />
              </div>
            </Card>
          </Reveal>
        )}

        <Reveal>
          <Card title="Recent runs">
            <RecentRuns runs={m.recent_runs} />
          </Card>
        </Reveal>
      </div>
    </>
  )
}

function RecentRuns({ runs }: { runs: Run[] }) {
  if (runs.length === 0) return <EmptyState title="No runs on this machine yet" />
  return (
    <Table>
      <thead>
        <tr>
          <th>Run</th>
          <th>Order</th>
          <th>Operator</th>
          <th>Started</th>
          <th>Ended</th>
          <th className="num">Output</th>
        </tr>
      </thead>
      <tbody>
        {runs.map((r) => (
          <tr key={r.id}>
            <td>#{r.id}</td>
            <td>{r.order_code}</td>
            <td>{r.operator.name}</td>
            <td className="nowrap">{formatDateTime(r.started_at)}</td>
            <td className="nowrap">{r.ended_at ? formatDateTime(r.ended_at) : <Badge tone="green">running</Badge>}</td>
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
  const [open, setOpen] = useState<Kind>(null)
  const close = () => setOpen(null)
  const run = m.current_run
  const repair = useAction({ invalidate: REFRESH })

  if (m.status === 'down') {
    return (
      <Button
        onClick={() =>
          repair.act(() => call(api.POST('/api/machines/{machine_code}/repair', { params: { path: { machine_code: m.code } } })), `${m.name} is back in service`)
        }
        aria-busy={repair.pending}
      >
        <Wrench size={16} aria-hidden /> Mark repaired
      </Button>
    )
  }

  return (
    <>
      {!run && (
        <Button onClick={() => setOpen('start')}>
          <Play size={16} aria-hidden /> Start run
        </Button>
      )}
      {run && m.stage === 'weaving' && (
        <Button onClick={() => setOpen('rolloff')}>
          <Scissors size={16} aria-hidden /> Roll off
        </Button>
      )}
      {run && m.stage === 'dyeing' && (
        <Button onClick={() => setOpen('load')}>
          <Layers size={16} aria-hidden /> Load rolls
        </Button>
      )}
      {run && m.stage === 'spinning' && (
        <Button onClick={() => setOpen('issue')}>
          <Hammer size={16} aria-hidden /> Issue yarn
        </Button>
      )}
      {run && (
        <Button variant="secondary" onClick={() => setOpen('handover')}>
          <ArrowRightLeft size={16} aria-hidden /> Hand over
        </Button>
      )}
      {run && (
        <Button variant="secondary" onClick={() => setOpen('end')}>
          <CircleStop size={16} aria-hidden /> End run
        </Button>
      )}
      <Button variant="secondary" onClick={() => setOpen('breakdown')}>
        <AlertTriangle size={16} aria-hidden /> Report breakdown
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
  const operators = useOperators(enabled)
  return (
    <Field label={label} error={error}>
      {(c) => (
        <Select {...c} value={value} onChange={(e) => onChange(e.target.value)}>
          <option value="">Select an operator</option>
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
    if (!order) next.order = 'Choose an order'
    if (!operator) next.operator = 'Choose an operator'
    if (needsInput && !(Number.isInteger(Number(inputRun)) && Number(inputRun) > 0)) next.input = 'Enter the spinning run number that supplies the yarn'
    setErrors(next)
    if (Object.keys(next).length) return
    return act(
      () =>
        call(
          api.POST('/api/runs', {
            body: { order_code: order, machine_code: m.code, operator_worker_id: Number(operator), ...(needsInput ? { input_run_id: Number(inputRun) } : {}) },
          }),
        ),
      `Run started on ${m.name}`,
    )
  }

  return (
    <ActionDialog open={open} onClose={onClose} title={`Start a run on ${m.name}`} confirmLabel="Start run" onConfirm={submit} pending={pending} error={error}>
      <Field label="Order" error={errors.order}>
        {(c) => (
          <Select {...c} value={order} onChange={(e) => setOrder(e.target.value)}>
            <option value="">Select an order</option>
            {(orders.data ?? []).map((o) => (
              <option key={o.code} value={o.code}>
                {o.code} · {o.buyer.name}
              </option>
            ))}
          </Select>
        )}
      </Field>
      <OperatorSelect label="Operator" value={operator} onChange={setOperator} error={errors.operator} enabled={open} />
      {needsInput && (
        <Field label="Spinning run number" error={errors.input} hint="The spinning run whose yarn this loom uses.">
          {(c) => <Input {...c} inputMode="numeric" value={inputRun} onChange={(e) => setInputRun(e.target.value)} />}
        </Field>
      )}
      {needsInput && candidates.length > 0 && (
        <div className="row">
          {candidates.map((x) => (
            <Button key={x.code} variant="secondary" onClick={() => setInputRun(String(x.current_run!.id))}>
              #{x.current_run!.id} on {x.code}
            </Button>
          ))}
        </div>
      )}
    </ActionDialog>
  )
}

function EndRunDialog({ m, runId, open, onClose }: { m: Detail; runId: number } & DialogProps) {
  const [kg, setKg] = useState('')
  const [err, setErr] = useState<string | undefined>()
  const { act, pending, error } = useAction({ invalidate: REFRESH, onDone: onClose })
  const spinning = m.stage === 'spinning'

  function submit() {
    if (spinning && (kg.trim() === '' || !(Number(kg) >= 0))) return setErr('Enter the kilos spun')
    setErr(undefined)
    return act(
      () => call(api.POST('/api/runs/{run_id}/end', { params: { path: { run_id: runId } }, body: spinning ? { output_kg: Number(kg) } : {} })),
      'Run ended',
    )
  }

  return (
    <ActionDialog open={open} onClose={onClose} title="End this run?" confirmLabel="End run" onConfirm={submit} pending={pending} error={error}>
      <p>The machine becomes free for the next job.</p>
      {spinning && (
        <Field label="Kilos spun" error={err}>
          {(c) => <Input {...c} type="number" inputMode="decimal" step="any" value={kg} onChange={(e) => setKg(e.target.value)} />}
        </Field>
      )}
    </ActionDialog>
  )
}

function HandoverDialog({ m, runId, currentOperatorId, open, onClose }: { m: Detail; runId: number; currentOperatorId: number } & DialogProps) {
  const [operator, setOperator] = useState('')
  const [err, setErr] = useState<string | undefined>()
  const { act, pending, error } = useAction({ invalidate: REFRESH, onDone: onClose })

  function submit() {
    if (!operator) return setErr('Choose the new operator')
    setErr(undefined)
    return act(() => call(api.POST('/api/runs/{run_id}/handover', { params: { path: { run_id: runId } }, body: { operator_worker_id: Number(operator) } })), `${m.name} handed over`)
  }

  return (
    <ActionDialog open={open} onClose={onClose} title="Hand over the machine" confirmLabel="Hand over" onConfirm={submit} pending={pending} error={error}>
      <p>The current run ends now and a new one starts for the same order with the new operator.</p>
      <OperatorSelect label="New operator" value={operator} onChange={setOperator} exclude={currentOperatorId} error={err} enabled={open} />
    </ActionDialog>
  )
}

function RollOffDialog({ runId, open, onClose }: { runId: number } & DialogProps) {
  const [metres, setMetres] = useState('')
  const [err, setErr] = useState<string | undefined>()
  const { act, pending, error } = useAction({ invalidate: REFRESH, onDone: onClose })

  function submit() {
    const n = Number(metres)
    if (metres.trim() === '' || !(n > 0)) return setErr('Enter the metres, more than 0')
    setErr(undefined)
    return act(
      async () => {
        const roll = await call(api.POST('/api/runs/{run_id}/rolls', { params: { path: { run_id: runId } }, body: { metres: n } }))
        setMetres('')
        return roll
      },
      (roll) => `Roll ${roll.code} created, ${formatMetres(roll.metres)}`,
    )
  }

  return (
    <ActionDialog open={open} onClose={onClose} title="Roll off a roll" confirmLabel="Roll off" onConfirm={submit} pending={pending} error={error}>
      <p>Measure the finished roll, then enter its length. It gets its own code and QR.</p>
      <Field label="Metres" error={err}>
        {(c) => <Input {...c} type="number" inputMode="decimal" step="any" value={metres} onChange={(e) => setMetres(e.target.value)} />}
      </Field>
    </ActionDialog>
  )
}

function LoadRollsDialog({ runId, open, onClose }: { runId: number } & DialogProps) {
  const [text, setText] = useState('')
  const [err, setErr] = useState<string | undefined>()
  const { act, pending, error } = useAction({ invalidate: REFRESH, onDone: onClose })

  function submit() {
    const codes = text.split(/[\s,;]+/).map((c) => c.trim().toUpperCase()).filter(Boolean)
    if (codes.length === 0) return setErr('Enter at least one roll code')
    setErr(undefined)
    return act(() => call(api.POST('/api/runs/{run_id}/load-rolls', { params: { path: { run_id: runId } }, body: { roll_codes: codes } })), `${codes.length} ${codes.length === 1 ? 'roll' : 'rolls'} loaded`)
  }

  return (
    <ActionDialog open={open} onClose={onClose} title="Load rolls into the dyeing machine" confirmLabel="Load rolls" onConfirm={submit} pending={pending} error={error}>
      <Field label="Roll codes" error={err} hint="Separate with spaces or commas. Only woven rolls of this order can be loaded.">
        {(c) => <Textarea {...c} value={text} onChange={(e) => setText(e.target.value)} />}
      </Field>
    </ActionDialog>
  )
}

function IssueYarnDialog({ runId, open, onClose }: { runId: number } & DialogProps) {
  const [lot, setLot] = useState('')
  const [qty, setQty] = useState('')
  const [errors, setErrors] = useState<Record<string, string>>({})
  const { act, pending, error } = useAction({ invalidate: REFRESH, onDone: onClose })
  const lots = useQuery({ queryKey: ['lots'], queryFn: () => call(api.GET('/api/lots')), enabled: open })
  const usable = (lots.data ?? []).filter((l) => !l.is_blocked)

  function submit() {
    const next: Record<string, string> = {}
    if (!lot) next.lot = 'Choose a lot'
    if (!(Number(qty) > 0)) next.qty = 'Enter the quantity in kg, more than 0'
    setErrors(next)
    if (Object.keys(next).length) return
    return act(() => call(api.POST('/api/movements/issue', { body: { lot_code: lot, run_id: runId, qty_kg: Number(qty) } })), `${formatKg(Number(qty))} issued from ${lot}`)
  }

  return (
    <ActionDialog open={open} onClose={onClose} title="Issue yarn to this run" confirmLabel="Issue yarn" onConfirm={submit} pending={pending} error={error}>
      <Field label="Lot" error={errors.lot}>
        {(c) => (
          <Select {...c} value={lot} onChange={(e) => setLot(e.target.value)}>
            <option value="">Select a lot</option>
            {usable.map((l) => (
              <option key={l.lot_code} value={l.lot_code}>
                {l.lot_code} · {l.yarn_type.name} · {formatKg(l.on_hand_kg)} on hand
              </option>
            ))}
          </Select>
        )}
      </Field>
      <Field label="Quantity (kg)" error={errors.qty}>
        {(c) => <Input {...c} type="number" inputMode="decimal" step="any" value={qty} onChange={(e) => setQty(e.target.value)} />}
      </Field>
    </ActionDialog>
  )
}

function BreakdownDialog({ m, open, onClose }: { m: Detail } & DialogProps) {
  const [reason, setReason] = useState('')
  const [err, setErr] = useState<string | undefined>()
  const { act, pending, error } = useAction({ invalidate: REFRESH, onDone: onClose })

  function submit() {
    if (!reason.trim()) return setErr('Say what went wrong')
    setErr(undefined)
    return act(
      async () => {
        const card = await call(api.POST('/api/machines/{machine_code}/breakdown', { params: { path: { machine_code: m.code } }, body: { reason: reason.trim() } }))
        setReason('')
        return card
      },
      `${m.name} marked down`,
    )
  }

  return (
    <ActionDialog open={open} onClose={onClose} title={`Report a breakdown on ${m.name}`} confirmLabel="Report breakdown" onConfirm={submit} pending={pending} error={error} danger>
      <p>Any run on this machine ends at the same moment. The board and the order delivery dates update for everyone.</p>
      <Field label="What went wrong" error={err}>
        {(c) => <Textarea {...c} value={reason} onChange={(e) => setReason(e.target.value)} />}
      </Field>
    </ActionDialog>
  )
}
