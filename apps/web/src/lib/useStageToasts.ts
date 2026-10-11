import { useEffect, useRef } from 'react'
import { toast } from 'sonner'
import type { Key } from '@/i18n/en'
import { useI18n } from '@/i18n/I18nContext'
import { changedStages } from '@/lib/stageChanges'

/** Tells the buyer, with a toast, when one of their orders moves to a new stage while the page is open. */
export function useStageToasts(orders: { code: string; stage: string }[] | undefined) {
  const { t } = useI18n()
  const last = useRef<Map<string, string> | null>(null)
  useEffect(() => {
    if (!orders) return
    for (const c of changedStages(last.current, orders)) {
      toast.success(t('portal.stageMoved', { code: c.code, stage: t(`status.order.${c.to}` as Key) }))
    }
    last.current = new Map(orders.map((o) => [o.code, o.stage]))
  }, [orders, t])
}
