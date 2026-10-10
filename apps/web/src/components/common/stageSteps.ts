import type { OrderStage } from './statusMaps'

/** The five steps of making an order, in the order they happen. */
export const STAGE_STEPS = ['Spinning', 'Weaving', 'Dyeing', 'Quality check', 'Ready'] as const

/** How many of the five steps an order has reached. Drafts and cancelled orders have reached none. */
const STEPS_DONE: Record<OrderStage, number> = {
  draft: 0,
  cancelled: 0,
  waiting_to_start: 0,
  spinning: 1,
  weaving: 2,
  dyeing: 3,
  quality_check: 4,
  ready_to_ship: 5,
  partly_dispatched: 5,
  dispatched: 5,
}

export const stepsDone = (stage: OrderStage) => STEPS_DONE[stage]

