import { useQuery } from '@tanstack/react-query'
import { ScanLine, Wrench } from 'lucide-react'
import { useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { ActionDialog } from '@/components/common/ActionDialog'
import { EmptyState } from '@/components/common/EmptyState'
import { KpiCard } from '@/components/common/KpiCard'
import { PageHeader } from '@/components/common/PageHeader'
import { QrScanner } from '@/components/common/QrScanner'
import { QueryBoundary } from '@/components/common/QueryBoundary'
import { StatusBadge } from '@/components/common/StatusBadge'
import { AnimatedGroup } from '@/components/motion/AnimatedGroup'
import { Reveal } from '@/components/motion/Reveal'
import { Button } from '@/components/ui/Button'
import { Field, Select } from '@/components/ui/Field'
import { Table } from '@/components/ui/Table'
import { api, call, type components } from '@/lib/api'
import { formatMetres } from '@/lib/format'
import { useAction } from '@/lib/useAction'

type Roll = components['schemas']['RollOut']

export default function QcQueue() {
  const queue = useQuery({ queryKey: ['qc', 'queue'], queryFn: () => call(api.GET('/api/qc/queue')) })
  const navigate = useNavigate()
  const [scanning, setScanning] = useState(false)
  const [reworkFor, setReworkFor] = useState<Roll | null>(null)

  return (
    <>
      <PageHeader
        title="Quality check"
        description="Rolls waiting to be checked. Photograph the cloth, review the suggestion, record the verdict."
        actions={
          <Button variant="secondary" onClick={() => setScanning(true)}>
            <ScanLine size={16} aria-hidden /> Scan a roll
          </Button>
        }
      />
      <QrScanner
        open={scanning}
        onClose={() => setScanning(false)}
        onCode={(code) => {
          setScanning(false)
          navigate(`/qc/${code}`)
        }}
      />
      <QueryBoundary query={queue}>
        {(q) => (
          <div className="stack">
            <AnimatedGroup className="grid-cards">
              <KpiCard label="Waiting for QC" value={q.counts.awaiting_qc} tone={q.counts.awaiting_qc > 0 ? 'danger' : undefined} />
              <KpiCard label="Needs rework" value={q.counts.awaiting_rework} />
              <KpiCard label="In rework" value={q.counts.in_rework} />
              <KpiCard label="Passed" value={q.counts.passed} />
              <KpiCard label="Rejected" value={q.counts.rejected} />
            </AnimatedGroup>
            <Reveal>
              {q.rolls.length === 0 ? (
                <EmptyState title="Nothing is waiting" description="New rolls appear here as soon as they come off dyeing." />
              ) : (
                <Table>
                  <thead>
                    <tr>
                      <th>Roll</th>
                      <th>Order</th>
                      <th>Buyer</th>
                      <th>Fabric</th>
                      <th className="num">Length</th>
                      <th>Status</th>
                      <th />
                    </tr>
                  </thead>
                  <tbody>
                    {q.rolls.map((r) => (
                      <tr key={r.code}>
                        <td>
                          <Link to={`/r/${r.code}`}>{r.code}</Link>
                        </td>
                        <td>{r.order_code}</td>
                        <td>{r.buyer_name}</td>
                        <td>
                          {r.fabric}
                          <div className="muted text-sm">{r.colour}</div>
                        </td>
                        <td className="num">{formatMetres(r.metres)}</td>
                        <td>
                          <StatusBadge kind="roll" value={r.status} />
                        </td>
                        <td>
                          {r.status === 'awaiting_rework' ? (
                            <Button variant="secondary" onClick={() => setReworkFor(r)}>
                              <Wrench size={16} aria-hidden /> Start rework
                            </Button>
                          ) : (
                            <Link to={`/qc/${r.code}`}>
                              <Button>Inspect</Button>
                            </Link>
                          )}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </Table>
              )}
            </Reveal>
          </div>
        )}
      </QueryBoundary>
      {reworkFor && <ReworkDialog roll={reworkFor} onClose={() => setReworkFor(null)} />}
    </>
  )
}

function ReworkDialog({ roll, onClose }: { roll: Roll; onClose: () => void }) {
  const [operator, setOperator] = useState('')
  const [machine, setMachine] = useState('')
  const [err, setErr] = useState<string | undefined>()
  const { act, pending, error } = useAction({ invalidate: [['qc'], ['rolls'], ['floor'], ['orders']], onDone: onClose })
  const workers = useQuery({ queryKey: ['people', 'workers'], queryFn: () => call(api.GET('/api/workers')) })
  const machines = useQuery({ queryKey: ['master', 'machines'], queryFn: () => call(api.GET('/api/machines')) })
  const operators = (workers.data ?? []).filter((w) => w.role === 'operator' && w.active)
  const dyers = (machines.data ?? []).filter((m) => m.stage === 'dyeing' && m.active)

  function submit() {
    if (!operator) return setErr('Choose who does the rework')
    setErr(undefined)
    return act(
      () => call(api.POST('/api/rework-runs', { body: { roll_code: roll.code, operator_worker_id: Number(operator), ...(machine ? { machine_code: machine } : {}) } })),
      `Rework started for ${roll.code}`,
    )
  }

  return (
    <ActionDialog open onClose={onClose} title={`Start rework for ${roll.code}`} confirmLabel="Start rework" onConfirm={submit} pending={pending} error={error}>
      <p>Re-dye it on a dyeing machine, or mend it by hand. The cost of the rework is charged to this roll.</p>
      <Field label="Operator" error={err}>
        {(c) => (
          <Select {...c} value={operator} onChange={(e) => setOperator(e.target.value)}>
            <option value="">Select an operator</option>
            {operators.map((w) => (
              <option key={w.id} value={w.id}>
                {w.name}
              </option>
            ))}
          </Select>
        )}
      </Field>
      <Field label="Machine">
        {(c) => (
          <Select {...c} value={machine} onChange={(e) => setMachine(e.target.value)}>
            <option value="">Mend by hand (no machine)</option>
            {dyers.map((m) => (
              <option key={m.code} value={m.code}>
                {m.name} ({m.code})
              </option>
            ))}
          </Select>
        )}
      </Field>
    </ActionDialog>
  )
}
