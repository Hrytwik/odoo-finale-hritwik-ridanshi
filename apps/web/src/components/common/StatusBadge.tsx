import { Badge } from '@/components/ui/Badge'
import { MACHINE_STATUS, ORDER_STAGE, ROLL_STATUS, type MachineStatus, type OrderStage, type RollStatus, type Style } from './statusMaps'

type Props =
  | { kind: 'machine'; value: MachineStatus }
  | { kind: 'roll'; value: RollStatus }
  | { kind: 'order'; value: OrderStage }

/** A coloured pill with the human label for a machine, roll or order status. Labels live in statusMaps.ts. */
export function StatusBadge(props: Props) {
  const style: Style =
    props.kind === 'machine' ? MACHINE_STATUS[props.value] : props.kind === 'roll' ? ROLL_STATUS[props.value] : ORDER_STAGE[props.value]
  return <Badge tone={style.tone}>{style.label}</Badge>
}
