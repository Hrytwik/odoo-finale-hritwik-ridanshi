import { useQuery } from '@tanstack/react-query'
import { Fragment } from 'react'
import { Alert } from '@/components/common/Alert'
import { EmptyState } from '@/components/common/EmptyState'
import { KpiCard } from '@/components/common/KpiCard'

import { PageHeader } from '@/components/common/PageHeader'
import { QueryBoundary } from '@/components/common/QueryBoundary'
import { AnimatedGroup } from '@/components/motion/AnimatedGroup'
import { Reveal } from '@/components/motion/Reveal'
import { Card } from '@/components/ui/Card'
import { Table } from '@/components/ui/Table'
import { DEFECT_LABEL } from '@/lib/defects'
import { api, call, type components } from '@/lib/api'
import { formatDate } from '@/lib/format'

type Card_ = components['schemas']['ModelCard']

// the bar from spec section 9: holes found at least 80% of the time, and no more than 20% false alarms on clean cloth
const HOLE_RECALL_BAR = 0.8
const FALSE_ALARM_BAR = 0.2

const pct = (n: number | null) => (n === null ? '-' : `${Math.round(n * 100)}%`)
const safeHref = (url: string) => (/^https?:\/\//i.test(url) ? url : null)

function meetsBar(c: Card_) {
  const holes = c.per_class.find((p) => p.defect_type === 'hole')
  return !!holes && holes.recall !== null && holes.recall >= HOLE_RECALL_BAR && c.clean_false_alarm_rate !== null && c.clean_false_alarm_rate <= FALSE_ALARM_BAR
}

export default function ModelCard() {
  const card = useQuery({ queryKey: ['qc', 'model-card'], queryFn: () => call(api.GET('/api/qc/model-card')) })
  return (
    <>
      <PageHeader title="Vision model" description="How the defect model did on photos it had never seen. Real numbers only." />
      <QueryBoundary query={card}>{(c) => (c.available ? <Evaluated c={c} /> : <NotYet />)}</QueryBoundary>
    </>
  )
}

function NotYet() {
  return (
    <EmptyState
      title="No vision model has been evaluated yet"
      description="Quality checking works fully without it: the inspector looks at the cloth and records the verdict. When a model is trained and tested, its results appear here."
    />
  )
}

function Evaluated({ c }: { c: Card_ }) {
  const good = meetsBar(c)
  return (
    <div className="stack">
      <Alert tone={good ? 'info' : 'error'}>
        {good
          ? `This model meets the bar: it finds at least ${pct(HOLE_RECALL_BAR)} of holes with no more than ${pct(FALSE_ALARM_BAR)} false alarms on clean cloth.`
          : `This model is below the bar (holes found at least ${pct(HOLE_RECALL_BAR)}, false alarms at most ${pct(FALSE_ALARM_BAR)}), so it is offered as a supporting suggestion only.`}
      </Alert>

      <AnimatedGroup className="grid-cards">
        <div className="kpi">
          <span className="kpi-label">Model</span>
          <span className="kpi-value">{c.model_version}</span>
          <span className="muted text-sm">{c.trained_at ? `trained ${formatDate(c.trained_at)}` : ''}</span>
        </div>
        <div className="kpi">
          <span className="kpi-label">Held-out test photos</span>
          <span className="kpi-value">{c.test_defective + c.test_clean}</span>
          <span className="muted text-sm">
            {c.test_defective} defective and {c.test_clean} clean, never seen in training
          </span>
        </div>
        <KpiCard
          label="False alarms on clean cloth"
          value={(c.clean_false_alarm_rate ?? 0) * 100}
          format={(n) => `${Math.round(n)}%`}
          tone={c.clean_false_alarm_rate !== null && c.clean_false_alarm_rate > FALSE_ALARM_BAR ? 'danger' : undefined}
        />
      </AnimatedGroup>

      <Reveal>
        <Card title="Per defect type">
          <Table>
            <thead>
              <tr>
                <th>Defect</th>
                <th className="num">Found</th>
                <th className="num">Missed</th>
                <th className="num">False alarms</th>
                <th className="num">Precision</th>
                <th className="num">Recall</th>
              </tr>
            </thead>
            <tbody>
              {c.per_class.map((p) => (
                <tr key={p.defect_type}>
                  <td>{DEFECT_LABEL[p.defect_type]}</td>
                  <td className="num">{p.found}</td>
                  <td className="num">{p.missed}</td>
                  <td className="num">{p.false_alarms}</td>
                  <td className="num">{pct(p.precision)}</td>
                  <td className="num">{pct(p.recall)}</td>
                </tr>
              ))}
            </tbody>
          </Table>
        </Card>
      </Reveal>

      <Reveal>
        <Card title="Confusion matrix">
          <p className="muted text-sm" style={{ marginBottom: 'var(--space-3)' }}>
            Rows are what was really on the photo; columns are what the model said.
          </p>
          <Table>
            <thead>
              <tr>
                <th>Actual \ Model said</th>
                {c.confusion_labels.map((l) => (
                  <th key={l} className="num">
                    {l}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {c.confusion_matrix.map((row, i) => (
                <tr key={c.confusion_labels[i] ?? i}>
                  <th scope="row">{c.confusion_labels[i]}</th>
                  {row.map((n, j) => (
                    <Fragment key={j}>
                      <td className={i === j ? 'num matrix-hit' : 'num'}>{n}</td>
                    </Fragment>
                  ))}
                </tr>
              ))}
            </tbody>
          </Table>
        </Card>
      </Reveal>

      <Reveal>
        <Card title="Where the training photos came from">
          <ul className="plain-list">
            {c.datasets.map((d) => {
              const href = safeHref(d.url)
              return (
                <li key={d.name}>
                  {href ? (
                    <a href={href} target="_blank" rel="noopener noreferrer">
                      {d.name}
                    </a>
                  ) : (
                    <span>{d.name}</span>
                  )}{' '}
                  <span className="muted text-sm">({d.licence})</span>
                </li>
              )
            })}
          </ul>
        </Card>
      </Reveal>
    </div>
  )
}
