import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { useEffect, useState, type ReactNode } from 'react'
import { Toaster } from 'sonner'
import { I18nProvider } from '@/i18n/I18nProvider'
import { ApiError, setUnauthorizedHandler } from '@/lib/api'

/** Do not retry client mistakes (4xx); retry network and server hiccups twice. */
function shouldRetry(failureCount: number, error: unknown) {
  if (error instanceof ApiError && error.status >= 400 && error.status < 500) return false
  return failureCount < 2
}

export function Providers({ children }: { children: ReactNode }) {
  const [client] = useState(
    () => new QueryClient({ defaultOptions: { queries: { retry: shouldRetry, staleTime: 10_000 } } }),
  )

  // Any 401 (session expired mid-use) sends the user to the login page and back to where they were afterwards.
  useEffect(() => {
    setUnauthorizedHandler(() => {
      const { pathname, search } = window.location
      if (pathname === '/' || pathname.startsWith('/login') || pathname.startsWith('/signup')) return
      window.location.assign(`/login?next=${encodeURIComponent(pathname + search)}`)
    })
    return () => setUnauthorizedHandler(null)
  }, [])

  return (
    <QueryClientProvider client={client}>
      <I18nProvider>
        {children}
        <Toaster position="top-center" richColors closeButton />
      </I18nProvider>
    </QueryClientProvider>
  )
}
