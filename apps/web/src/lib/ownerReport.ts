import type { components } from '@/lib/api'

type Machines = components['schemas']['MonthReport']['machines']

/** Share of the machines' time spent running: running hours over running, idle and down hours together. 0 when there are no hours. */
export function machineUse(machines: Machines): number {
  const running = machines.reduce((t, m) => t + m.running_h, 0)
  const total = machines.reduce((t, m) => t + m.running_h + m.idle_h + m.down_h, 0)
  return total > 0 ? running / total : 0
}
