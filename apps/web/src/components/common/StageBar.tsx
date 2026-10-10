import { STAGE_STEPS, stepsDone } from './stageSteps'
import { ORDER_STAGE, type OrderStage } from './statusMaps'

/** Five small segments, filled up to the order's current step, with the stage named underneath. */
export function StageBar({ stage }: { stage: OrderStage }) {
  const done = stepsDone(stage)
  return (
    <div className="stage-bar" role="img" aria-label={`${ORDER_STAGE[stage].label}, step ${done} of ${STAGE_STEPS.length}`}>
      <span className="stage-segments" aria-hidden>
        {STAGE_STEPS.map((step, i) => (
          <i key={step} className={i < done ? 'is-done' : undefined} />
        ))}
      </span>
      <span className="stage-label">{ORDER_STAGE[stage].label}</span>
    </div>
  )
}

/** The key to the five steps, shown above an orders list. */
export function StageLegend() {
  return (
    <p className="stage-legend" aria-label="Order steps">
      {STAGE_STEPS.map((step) => (
        <span key={step}>
          <i aria-hidden /> {step}
        </span>
      ))}
    </p>
  )
}
