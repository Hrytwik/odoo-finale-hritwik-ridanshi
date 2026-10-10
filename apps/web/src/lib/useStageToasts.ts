import { useEffect, useRef } from 'react'
import { toast } from 'sonner'
import { ORDER_STAGE, type OrderStage } from '@/components/common/statusMaps'
import { changedStages } from '@/lib/stageChanges'

/** Tells the buyer, with a toast, when one of their orders moves to a new stage while the page is open. */
export function useStageToasts(orders: { code: string; stage: string }[] | undefined) {
  const last = useRef<Map<string, string> | null>(null)
  useEffect(() => {
    if (!orders) return
    for (const c of changedStages(last.current, orders)) {
      const label = ORDER_STAGE[c.to as OrderStage]?.label ?? c.to
      toast.success(`${c.code} moved to ${label}`)
    }
    last.current = new Map(orders.map((o) => [o.code, o.stage]))
  }, [orders])
}
