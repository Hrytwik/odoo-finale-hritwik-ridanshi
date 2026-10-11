import { Link } from 'react-router-dom'
import { EmptyState } from '@/components/common/EmptyState'
import { LoadingState } from '@/components/common/LoadingState'
import { Button } from '@/components/ui/Button'
import { useI18n } from '@/i18n/I18nContext'
import { useMe } from '@/lib/auth'
import { homeFor, type Role } from '@/lib/nav'

/** Mirrors the backend's role rule so people see a clear message instead of a failed request. */
export function RequireRole({ roles, children }: { roles: Role[] | 'all'; children: React.ReactNode }) {
  const me = useMe()
  const { t } = useI18n()
  if (!me.data) return <LoadingState rows={2} />
  if (roles !== 'all' && !roles.includes(me.data.role)) {
    return (
      <EmptyState
        title={t('role.deniedTitle')}
        description={t('role.deniedBody')}
        action={
          <Link to={homeFor(me.data.role)}>
            <Button variant="secondary">{t('role.goHome')}</Button>
          </Link>
        }
      />
    )
  }
  return <>{children}</>
}

export function NotFound() {
  const { t } = useI18n()
  return (
    <EmptyState
      title={t('notFound.title')}
      description={t('notFound.body')}
      action={
        <Link to="/">
          <Button variant="secondary">{t('role.goHome')}</Button>
        </Link>
      }
    />
  )
}
