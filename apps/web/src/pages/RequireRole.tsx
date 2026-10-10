import { Link } from 'react-router-dom'
import { EmptyState } from '@/components/common/EmptyState'
import { LoadingState } from '@/components/common/LoadingState'
import { Button } from '@/components/ui/Button'
import { useMe } from '@/lib/auth'
import { homeFor, type Role } from '@/lib/nav'

/** Mirrors the backend's role rule so people see a clear message instead of a failed request. */
export function RequireRole({ roles, children }: { roles: Role[] | 'all'; children: React.ReactNode }) {
  const me = useMe()
  if (!me.data) return <LoadingState rows={2} />
  if (roles !== 'all' && !roles.includes(me.data.role)) {
    return (
      <EmptyState
        title="This page is not available for your role"
        description="Ask the owner if you need access."
        action={
          <Link to={homeFor(me.data.role)}>
            <Button variant="secondary">Go to your home page</Button>
          </Link>
        }
      />
    )
  }
  return <>{children}</>
}

export function NotFound() {
  return (
    <EmptyState
      title="Page not found"
      description="The page you opened does not exist."
      action={
        <Link to="/">
          <Button variant="secondary">Go to your home page</Button>
        </Link>
      }
    />
  )
}
