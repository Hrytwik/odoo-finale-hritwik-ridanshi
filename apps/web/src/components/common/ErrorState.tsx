import { AlertTriangle } from 'lucide-react'
import { errorMessage } from '@/lib/api/errors'
import { Button } from '@/components/ui/Button'
import { useI18n } from '@/i18n/I18nContext'

/** Shown when a page's data could not be loaded. Never leave a blank page. */
export function ErrorState({ error, onRetry }: { error: unknown; onRetry?: () => void }) {
  const { t } = useI18n()
  return (
    <div role="alert" className="state-box state-box-error">
      <AlertTriangle size={24} className="text-danger" aria-hidden />
      <p className="text-sm">{errorMessage(error)}</p>
      {onRetry && (
        <Button variant="secondary" onClick={onRetry}>
          {t('store.stock.retry')}
        </Button>
      )}
    </div>
  )
}
