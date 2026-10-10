import { useQuery } from '@tanstack/react-query'
import { AlertTriangle, Factory } from 'lucide-react'
import { Link } from 'react-router-dom'
import { EmptyState } from '@/components/common/EmptyState'
import { KpiCard } from '@/components/common/KpiCard'
import { PageHeader } from '@/components/common/PageHeader'
import { QueryBoundary } from '@/components/common/QueryBoundary'
import { StatusBadge } from '@/components/common/StatusBadge'
import { AnimatedGroup } from '@/components/motion/AnimatedGroup'
import { Reveal } from '@/components/motion/Reveal'
import { ProgressBar } from '@/components/ui/ProgressBar'
import { api, call, type components } from '@/lib/api'
import { formatDateTime, formatQty } from '@/lib/format'

type Machine = components['schemas']['MachineCard']

const STAGES = [
  { stage: 'spinning', title: 'Spinning' },
  { stage: 'weaving', title: 'Weaving' },
  { stage: 'dyeing', title: 'Dyeing' },
] as const

export default function FloorBoard() {
  // the key starts with "floor", so machine and run events from the live stream refetch the board
  const board = useQuery({ queryKey: ['floor'], queryFn: () => call(api.GET('/api/floor')) })
  return (
    <>
      <PageHeader title="Floor board" description="Every machine, live. A breakdown on the phone shows here within a second." />
      <QueryBoundary query={board}>
        {(b) =>
          b.machines.length === 0 ? (
            <EmptyState title="No machines yet" description="The owner adds machines under Master data." />
          ) : (
            <div className="stack">
              <AnimatedGroup className="grid-cards">
                <KpiCard label="Running" value={b.running} />
                <KpiCard label="Idle" value={b.idle} hint="could be earning" />
                <KpiCard label="Down" value={b.down} tone={b.down > 0 ? 'danger' : undefined} hint={b.down > 0 ? 'needs repair' : 'none'} />
              </AnimatedGroup>
              {STAGES.map(({ stage, title }) => {
                const machines = b.machines.filter((m) => m.stage === stage)
                if (machines.length === 0) return null
                return (
                  <Reveal key={stage}>
                    <section className="stack-sm" aria-label={title}>
                      <h2>{title}</h2>
                      <div className="grid-cards">
                        {machines.map((m) => (
                          <MachineTile key={m.code} machine={m} />
                        ))}
                      </div>
                    </section>
                  </Reveal>
                )
              })}
            </div>
          )
        }
      </QueryBoundary>
    </>
  )
}

function MachineTile({ machine: m }: { machine: Machine }) {
  return (
    <article className={`machine machine-${m.status}`}>
      <header className="machine-head">
        <Link to={`/floor/machines/${m.code}`} className="machine-name">
          <Factory size={16} aria-hidden /> {m.name}
        </Link>
        <StatusBadge kind="machine" value={m.status} />
      </header>
      <p className="muted text-sm">{m.code}</p>

      {m.status === 'down' && m.downtime && (
        <div className="machine-note machine-note-down">
          <AlertTriangle size={16} aria-hidden />
          <span>
            <strong>{m.downtime.reason}</strong>
            <br />
            <span className="text-sm">Down since {formatDateTime(m.downtime.started_at)}</span>
          </span>
        </div>
      )}

      {m.current_run && (
        <div className="stack-sm">
          <p className="text-sm">
            <strong>{m.current_run.order_code}</strong> · {m.current_run.operator.name}
          </p>
          <ProgressBar label="Order progress" value={m.current_run.order_progress_pct} max={100} tone="blue" unit="%" />
        </div>
      )}

      {m.status === 'idle' && <p className="muted text-sm">Waiting for a job.</p>}

      <p className="machine-output">
        <span className="muted text-sm">Today</span> <strong>{formatQty(m.output_today, m.output_unit)}</strong>
      </p>
    </article>
  )
}
