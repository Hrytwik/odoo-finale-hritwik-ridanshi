import { motion, useReducedMotion } from 'motion/react'
import { Outlet, useLocation } from 'react-router-dom'
import { ErrorState } from '@/components/common/ErrorState'
import { LoadingState } from '@/components/common/LoadingState'
import { AppShell } from '@/components/shell/AppShell'
import { ApiError } from '@/lib/api'
import { useMe } from '@/lib/auth'

/** The session gate: shows the app only for a logged-in user. A 401 is handled globally (redirect to /login). */
export function AppLayout() {
  const me = useMe()
  const { pathname } = useLocation()
  const reduce = useReducedMotion()

  if (me.isPending) {
    return (
      <div style={{ padding: 'var(--space-5)' }}>
        <LoadingState />
      </div>
    )
  }
  if (me.isError) {
    // 401: the unauthorized handler is already sending the user to /login with ?next=
    if (me.error instanceof ApiError && me.error.status === 401) return <LoadingState rows={2} />
    return (
      <div style={{ padding: 'var(--space-5)' }}>
        <ErrorState error={me.error} onRetry={() => me.refetch()} />
      </div>
    )
  }

  return (
    <AppShell me={me.data}>
      <motion.div
        key={pathname}
        initial={reduce ? false : { opacity: 0, y: 8 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.28, ease: [0.16, 1, 0.3, 1] }}
      >
        <Outlet />
      </motion.div>
    </AppShell>
  )
}
