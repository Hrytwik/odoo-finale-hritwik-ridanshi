import type { Key } from '@/i18n/en'
import { useI18n } from '@/i18n/I18nContext'
import { STAGE_STEPS, stepsDone } from './stageSteps'
import type { OrderStage } from './statusMaps'

/** Five small segments, filled up to the order's current step, with the stage named underneath. */
export function StageBar({ stage }: { stage: OrderStage }) {
  const { t } = useI18n()
  const done = stepsDone(stage)
  const label = t(`status.order.${stage}` as Key)
  return (
    <div className="stage-bar" role="img" aria-label={t('portal.stageAria', { stage: label, done, total: STAGE_STEPS.length })}>
      <span className="stage-segments" aria-hidden>
        {STAGE_STEPS.map((step, i) => (
          <i key={step} className={i < done ? 'is-done' : undefined} />
        ))}
      </span>
      <span className="stage-label">{label}</span>
    </div>
  )
}

/** The key to the five steps, shown above an orders list. */
export function StageLegend() {
  const { t } = useI18n()
  return (
    <p className="stage-legend" aria-label={t('portal.stepsLegend')}>
      {STAGE_STEPS.map((step) => (
        <span key={step}>
          <i aria-hidden /> {t(step)}
        </span>
      ))}
    </p>
  )
}
