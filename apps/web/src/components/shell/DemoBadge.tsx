import { useQuery } from '@tanstack/react-query'
import { Badge } from '@/components/ui/Badge'
import { api, call } from '@/lib/api'

/** Shown whenever the database holds seeded demo data, so nobody mistakes it for real records. */
export function DemoBadge() {
  const health = useQuery({ queryKey: ['health'], queryFn: () => call(api.GET('/api/health')), staleTime: 60_000 })
  if (!health.data?.demo_data) return null
  return <Badge tone="amber">Demo data</Badge>
}
