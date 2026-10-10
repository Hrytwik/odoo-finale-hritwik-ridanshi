import type { Tone } from '@/components/ui/Badge'
import type { components } from '@/lib/api'

export type MachineStatus = components['schemas']['MachineCard']['status']
export type RollStatus = components['schemas']['RollOut']['status']
export type OrderStage = components['schemas']['OrderOut']['stage']
export type Style = { label: string; tone: Tone }

// `satisfies Record<...>` makes these exhaustive: if the backend adds a status, the build fails here until it gets a label.
export const MACHINE_STATUS = {
  running: { label: 'Running', tone: 'green' },
  idle: { label: 'Idle', tone: 'amber' },
  down: { label: 'Down', tone: 'red' },
} satisfies Record<MachineStatus, Style>

export const ROLL_STATUS = {
  woven: { label: 'Woven', tone: 'blue' },
  dyeing: { label: 'Dyeing', tone: 'violet' },
  awaiting_qc: { label: 'Awaiting QC', tone: 'amber' },
  awaiting_rework: { label: 'Needs rework', tone: 'amber' },
  in_rework: { label: 'In rework', tone: 'violet' },
  in_store: { label: 'In store', tone: 'green' },
  rejected: { label: 'Rejected', tone: 'red' },
  loading: { label: 'Loading', tone: 'blue' },
  dispatched: { label: 'Dispatched', tone: 'gray' },
} satisfies Record<RollStatus, Style>

export const ORDER_STAGE = {
  draft: { label: 'Draft', tone: 'gray' },
  cancelled: { label: 'Cancelled', tone: 'gray' },
  waiting_to_start: { label: 'Waiting to start', tone: 'amber' },
  spinning: { label: 'Spinning', tone: 'blue' },
  weaving: { label: 'Weaving', tone: 'blue' },
  dyeing: { label: 'Dyeing', tone: 'violet' },
  quality_check: { label: 'Quality check', tone: 'amber' },
  ready_to_ship: { label: 'Ready to ship', tone: 'green' },
  partly_dispatched: { label: 'Partly dispatched', tone: 'blue' },
  dispatched: { label: 'Dispatched', tone: 'gray' },
} satisfies Record<OrderStage, Style>
