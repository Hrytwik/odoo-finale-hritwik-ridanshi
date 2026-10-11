import { useQuery } from '@tanstack/react-query'
import { ScanLine, Wrench } from 'lucide-react'
import { useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { ActionDialog } from '@/components/common/ActionDialog'
import { EmptyState } from '@/components/common/EmptyState'
import { Filtered } from '@/components/common/ListToolbar'
import type { Key } from '@/i18n/en'
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
import { useI18n } from '@/i18n/I18nContext'
import { api, call, type components } from '@/lib/api'
import { formatMetres } from '@/lib/format'
import { useAction } from '@/lib/useAction'

type Roll = components['schemas']['RollOut']

export default function QcQueue() {
  const { t } = useI18n()
  const queue = useQuery({ queryKey: ['qc', 'queue'], queryFn: () => call(api.GET('/api/qc/queue')) })
  const navigate = useNavigate()
  const [scanning, setScanning] = useState(false)
  const [reworkFor, setReworkFor] = useState<Roll | null>(null)

  return (
    <>
      <PageHeader
        title={t('qc.title')}
        description={t('qc.description')}
        actions={
          <Button variant="secondary" onClick={() => setScanning(true)}>
            <ScanLine size={16} aria-hidden /> {t('qc.scan')}
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
              <KpiCard label={t('qc.waiting')} value={q.counts.awaiting_qc} tone={q.counts.awaiting_qc > 0 ? 'danger' : undefined} />
              <KpiCard label={t('qc.needsRework')} value={q.counts.awaiting_rework} />
              <KpiCard label={t('qc.inRework')} value={q.counts.in_rework} />
              <KpiCard label={t('qc.passed')} value={q.counts.passed} />
              <KpiCard label={t('qc.rejected')} value={q.counts.rejected} />
            </AnimatedGroup>
            <Reveal>
              {q.rolls.length === 0 ? (
                <EmptyState title={t('qc.nothingWaiting')} description={t('qc.nothingWaitingDescription')} />
              ) : (
                <Filtered
                  rows={q.rolls}
                  options={{
                    text: (r) => `${r.code} ${r.order_code} ${r.buyer_name} ${r.fabric} ${r.colour}`,
                    sorts: [
                      { key: 'roll', label: t('qc.col.roll'), value: (r) => r.code },
                      { key: 'order', label: t('qc.col.order'), value: (r) => r.order_code },
                      { key: 'buyer', label: t('qc.col.buyer'), value: (r) => r.buyer_name },
                      { key: 'length', label: t('qc.col.length'), value: (r) => r.metres },
                    ],
                    filters: [
                      {
                        key: 'status',
                        label: t('qc.col.status'),
                        options: [...new Set(q.rolls.map((r) => r.status))].map((st) => ({ value: st, label: t(`status.roll.${st}` as Key) })),
                        test: (r, v) => r.status === v,
                      },
                    ],
                  }}
                >
                  {(shown) => (
                <Table>
                  <thead>
                    <tr>
                      <th>{t('qc.col.roll')}</th>
                      <th>{t('qc.col.order')}</th>
                      <th>{t('qc.col.buyer')}</th>
                      <th>{t('qc.col.fabric')}</th>
                      <th className="num">{t('qc.col.length')}</th>
                      <th>{t('qc.col.status')}</th>
                      <th />
                    </tr>
                  </thead>
                  <tbody>
                    {shown.map((r) => (
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
                              <Wrench size={16} aria-hidden /> {t('qc.startRework')}
                            </Button>
                          ) : (
                            <Link to={`/qc/${r.code}`}>
                              <Button>{t('qc.inspect')}</Button>
                            </Link>
                          )}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </Table>
                  )}
                </Filtered>
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
  const { t } = useI18n()
  const [operator, setOperator] = useState('')
  const [machine, setMachine] = useState('')
  const [err, setErr] = useState<string | undefined>()
  const { act, pending, error } = useAction({ invalidate: [['qc'], ['rolls'], ['floor'], ['orders']], onDone: onClose })
  const workers = useQuery({ queryKey: ['people', 'workers'], queryFn: () => call(api.GET('/api/workers')) })
  const machines = useQuery({ queryKey: ['master', 'machines'], queryFn: () => call(api.GET('/api/machines')) })
  const operators = (workers.data ?? []).filter((w) => w.role === 'operator' && w.active)
  const dyers = (machines.data ?? []).filter((m) => m.stage === 'dyeing' && m.active)

  function submit() {
    if (!operator) return setErr(t('qc.rework.chooseOperator'))
    setErr(undefined)
    return act(
      () => call(api.POST('/api/rework-runs', { body: { roll_code: roll.code, operator_worker_id: Number(operator), ...(machine ? { machine_code: machine } : {}) } })),
      t('qc.rework.started', { code: roll.code }),
    )
  }

  return (
    <ActionDialog open onClose={onClose} title={t('qc.rework.title', { code: roll.code })} confirmLabel={t('qc.startRework')} onConfirm={submit} pending={pending} error={error}>
      <p>{t('qc.rework.explain')}</p>
      <Field label={t('qc.rework.operator')} error={err}>
        {(c) => (
          <Select {...c} value={operator} onChange={(e) => setOperator(e.target.value)}>
            <option value="">{t('qc.rework.selectOperator')}</option>
            {operators.map((w) => (
              <option key={w.id} value={w.id}>
                {w.name}
              </option>
            ))}
          </Select>
        )}
      </Field>
      <Field label={t('qc.rework.machine')}>
        {(c) => (
          <Select {...c} value={machine} onChange={(e) => setMachine(e.target.value)}>
            <option value="">{t('qc.rework.byHand')}</option>
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
