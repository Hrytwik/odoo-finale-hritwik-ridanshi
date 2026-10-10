import { useQueryClient, type QueryClient } from '@tanstack/react-query'
import { useEffect } from 'react'

/** Backend event type -> query-key prefixes to refetch. Query keys start with the area name (see plan A1). */
export const EVENT_KEYS: Record<string, string[][]> = {
  'lot.changed': [['lots'], ['stock']],
  'stock.changed': [['stock'], ['orders'], ['insights']],
  'order.changed': [['orders'], ['portal'], ['insights']],
  'machine.changed': [['floor'], ['machine'], ['insights']],
  'run.changed': [['floor'], ['machine'], ['orders'], ['portal']],
  'roll.changed': [['qc'], ['rolls'], ['orders'], ['dispatches'], ['portal']],
  'qc.changed': [['qc'], ['rolls'], ['orders'], ['insights']],
  'dispatch.changed': [['dispatches'], ['orders'], ['portal'], ['money']],
  'payment.changed': [['money'], ['owner']],
  'attendance.changed': [['people'], ['owner']],
  'notice.changed': [['notices']],
}

export const keysFor = (eventType: string) => EVENT_KEYS[eventType] ?? []

export function handleLiveMessage(queryClient: QueryClient, rawData: string) {
  let type: unknown
  try {
    type = (JSON.parse(rawData) as { type?: unknown }).type
  } catch {
    return
  }
  if (typeof type !== 'string') return
  for (const queryKey of keysFor(type)) void queryClient.invalidateQueries({ queryKey })
}

/** Opens the server's live event stream once and refetches whatever the event says changed. The browser reconnects by itself. */
export function useLiveEvents() {
  const queryClient = useQueryClient()
  useEffect(() => {
    const source = new EventSource('/api/events')
    source.onmessage = (event) => handleLiveMessage(queryClient, event.data)
    return () => source.close()
  }, [queryClient])
}
