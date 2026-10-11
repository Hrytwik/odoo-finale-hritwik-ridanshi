import { useQuery } from '@tanstack/react-query'
import { AlertTriangle } from 'lucide-react'
import { Link } from 'react-router-dom'
import { EmptyState } from '@/components/common/EmptyState'
import { PageHeader } from '@/components/common/PageHeader'
import { QueryBoundary } from '@/components/common/QueryBoundary'
import { StatusBadge } from '@/components/common/StatusBadge'
import { AnimatedNumber } from '@/components/motion/AnimatedNumber'
import { Reveal } from '@/components/motion/Reveal'
import { useI18n } from '@/i18n/I18nContext'
import type { Key } from '@/i18n/en'
import { api, call, type components } from '@/lib/api'
import { formatDateTime, formatQty } from '@/lib/format'
import { SPEED, useLiveSpeed } from '@/lib/liveReading'

type Machine = components['schemas']['MachineCard']

const STAGES = ['spinning', 'weaving', 'dyeing'] as const

export default function FloorBoard() {
  // the key starts with "floor", so machine and run events from the live stream refetch the board
  const { t } = useI18n()
  const board = useQuery({ queryKey: ['floor'], queryFn: () => call(api.GET('/api/floor')) })
  return (
    <>
      <PageHeader eyebrow={t('floor.eyebrow')} title={t('floor.title')} description={t('floor.description')} />
      <QueryBoundary query={board}>
        {(b) =>
          b.machines.length === 0 ? (
            <EmptyState title={t('floor.emptyTitle')} description={t('floor.emptyDescription')} />
          ) : (
            <div className="stack">
              <div className="live-strip" aria-label={t('floor.machinesNow')}>
                <span className="live-tag">
                  <i className="live-dot" aria-hidden /> {t('floor.live')}
                </span>
                <LiveCount label={t('floor.running')} value={b.running} />
                <LiveCount label={t('floor.idle')} value={b.idle} />
                <LiveCount label={t('floor.down')} value={b.down} />
              </div>
              {STAGES.map((stage) => {
                const title = t(`floor.stage.${stage}` as Key)
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

function LiveCount({ label, value }: { label: string; value: number }) {
  return (
    <span className="live-count">
      <strong>
        <AnimatedNumber value={value} />
      </strong>{' '}
      {label}
    </span>
  )
}

function MachineTile({ machine: m }: { machine: Machine }) {
  const { t } = useI18n()
  const running = m.status === 'running'
  const speed = useLiveSpeed(m.code, m.stage, running)
  const run = m.current_run
  const pct = run ? Math.min(100, Math.max(0, run.order_progress_pct)) : 0

  return (
    <article className={`machine machine-${m.status}`}>
      <header className="machine-head">
        <Link to={`/floor/machines/${m.code}`} className="machine-name">
          {m.name}
        </Link>
        <StatusBadge kind="machine" value={m.status} />
      </header>
      <p className="machine-operator">
        {m.code}
        {run ? ` · ${run.operator.name}` : ''}
      </p>

      <p className="machine-speed" title={running ? t('floor.simulated') : undefined}>
        <strong>{speed === null ? '—' : speed.toLocaleString('en-IN')}</strong>
        <small>{SPEED[m.stage].unit}</small>
      </p>
      <div
        className="machine-thread"
        role={run ? 'progressbar' : undefined}
        aria-label={run ? t('floor.orderProgress') : undefined}
        aria-valuemin={run ? 0 : undefined}
        aria-valuemax={run ? 100 : undefined}
        aria-valuenow={run ? Math.round(pct) : undefined}
      >
        <i style={{ width: `${pct}%` }} />
      </div>

      {m.status === 'down' && m.downtime && (
        <div className="machine-note machine-note-down">
          <AlertTriangle size={16} aria-hidden />
          <span>
            <strong>{m.downtime.reason}</strong>
            <br />
            <span className="text-sm">{t('floor.downSince', { time: formatDateTime(m.downtime.started_at) })}</span>
          </span>
        </div>
      )}

      <p className="machine-foot">
        <span>{run ? run.order_code : m.status === 'idle' ? t('floor.waitingForJob') : t('floor.stopped')}</span>
        <span>
          {t('floor.today')} <strong>{formatQty(m.output_today, m.output_unit)}</strong>
        </span>
      </p>
    </article>
  )
}
