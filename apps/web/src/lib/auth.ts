import { useQuery, useQueryClient } from '@tanstack/react-query'
import { useNavigate } from 'react-router-dom'
import { api, call } from '@/lib/api'

export function useMe() {
  return useQuery({
    queryKey: ['me'],
    queryFn: () => call(api.GET('/api/auth/me')),
    retry: false,
    staleTime: 60_000,
  })
}

export function useLogout() {
  const queryClient = useQueryClient()
  const navigate = useNavigate()
  return async () => {
    await call(api.POST('/api/auth/logout')).catch(() => undefined)
    queryClient.clear()
    navigate('/login', { replace: true })
  }
}
