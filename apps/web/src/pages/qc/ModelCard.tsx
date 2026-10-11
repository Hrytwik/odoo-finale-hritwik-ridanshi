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
import { useI18n } from '@/i18n/I18nContext'
import { useDefectLabel } from '@/lib/useDefectLabel'
import { api, call, type components } from '@/lib/api'
import { DEFECT_LABEL, type DefectType } from '@/lib/defects'
import { formatDate } from '@/lib/format'

type Card_ = components['schemas']['ModelCard']

// the bar from spec section 9: holes found at least 80% of the time, and no more than 20% false alarms on clean cloth
const HOLE_RECALL_BAR = 0.8
const FALSE_ALARM_BAR = 0.2

const DEFECT_TYPES = DEFECT_LABEL
const pct = (n: number | null) => (n === null ? '-' : `${Math.round(n * 100)}%`)

function meetsBar(c: Card_) {
  const holes = c.per_class.find((p) => p.defect_type === 'hole')
  return !!holes && holes.recall !== null && holes.recall >= HOLE_RECALL_BAR && c.clean_false_alarm_rate !== null && c.clean_false_alarm_rate <= FALSE_ALARM_BAR
}

/** How the model did on photos it had never seen: the part of the Vision model page about accuracy. */
export function ModelAccuracy() {
  const card = useQuery({ queryKey: ['qc', 'model-card'], queryFn: () => call(api.GET('/api/qc/model-card')) })
  return <QueryBoundary query={card}>{(c) => (c.available ? <Evaluated c={c} /> : <NotYet />)}</QueryBoundary>
}

export default function ModelCard() {
  return (
    <>
      <PageHeader title="Vision model" description="How the defect model did on photos it had never seen. Real numbers only." />
      <ModelAccuracy />
    </>
  )
}

function NotYet() {
  const { t } = useI18n()
  return (
    <EmptyState
      title={t('mc.notYetTitle')}
      description={t('mc.notYetBody')}
    />
  )
}

function Evaluated({ c }: { c: Card_ }) {
  const { t } = useI18n()
  const defectLabel = useDefectLabel()
  const good = meetsBar(c)
  const rowLabel = (l: string) => (l === 'clean' ? t('mc.cleanLabel') : l in DEFECT_TYPES ? defectLabel(l as DefectType) : l)
  return (
    <div className="stack">
      <Alert tone={c.clean_false_alarm_rate === null || good ? 'info' : 'error'}>
        {c.clean_false_alarm_rate === null
          ? t('mc.unvalidated')
          : good
            ? t('mc.meetsBar', { recall: pct(HOLE_RECALL_BAR), alarm: pct(FALSE_ALARM_BAR) })
            : t('mc.belowBar', { recall: pct(HOLE_RECALL_BAR), alarm: pct(FALSE_ALARM_BAR) })}
      </Alert>

      <AnimatedGroup className="grid-cards">
        <div className="kpi">
          <span className="kpi-label">{t('mc.model')}</span>
          <span className="kpi-value">{c.model_version}</span>
          <span className="muted text-sm">{c.trained_at ? t('mc.trained', { date: formatDate(c.trained_at) }) : ''}</span>
        </div>
        <div className="kpi">
          <span className="kpi-label">{t('mc.heldOut')}</span>
          <span className="kpi-value">{c.test_defective + c.test_clean}</span>
          <span className="muted text-sm">
            {t('mc.heldOutHint', { defective: c.test_defective, clean: c.test_clean })}
          </span>
        </div>
        {c.clean_false_alarm_rate === null ? (
          <div className="kpi">
            <span className="kpi-label">{t('mc.falseAlarms')}</span>
            <span className="kpi-value">{t('mc.notMeasured')}</span>
            <span className="muted text-sm">{t('mc.noCleanYet')}</span>
          </div>
        ) : (
          <KpiCard
            label={t('mc.falseAlarms')}
            value={c.clean_false_alarm_rate * 100}
            format={(n) => `${Math.round(n)}%`}
            tone={c.clean_false_alarm_rate > FALSE_ALARM_BAR ? 'danger' : undefined}
          />
        )}
      </AnimatedGroup>

      <Reveal>
        <Card title={t('mc.perDefect')}>
          <Table>
            <thead>
              <tr>
                <th>{t('mc.col.defect')}</th>
                <th className="num">{t('mc.col.found')}</th>
                <th className="num">{t('mc.col.missed')}</th>
                <th className="num">{t('mc.col.falseAlarms')}</th>
                <th className="num">{t('mc.col.precision')}</th>
                <th className="num">{t('mc.col.recall')}</th>
              </tr>
            </thead>
            <tbody>
              {c.per_class.map((p) => (
                <tr key={p.defect_type}>
                  <td>{defectLabel(p.defect_type)}</td>
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
        <Card title={t('mc.confusion')}>
          <p className="muted text-sm" style={{ marginBottom: 'var(--space-3)' }}>
            {t('mc.confusionNote')}
          </p>
          <Table>
            <thead>
              <tr>
                <th>{t('mc.actualVsSaid')}</th>
                {c.confusion_labels.map((l) => (
                  <th key={l} className="num">
                    {rowLabel(l)}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {c.confusion_matrix.map((row, i) => (
                <tr key={c.confusion_labels[i] ?? i}>
                  <th scope="row">{rowLabel(c.confusion_labels[i] ?? '')}</th>
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
    </div>
  )
}
