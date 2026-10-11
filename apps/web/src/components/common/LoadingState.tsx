import { useI18n } from '@/i18n/I18nContext'

export function LoadingState({ rows = 4 }: { rows?: number }) {
  const { t } = useI18n()
  return (
    <div className="stack-sm" aria-busy="true" aria-label={t('common.loading')}>
      {Array.from({ length: rows }, (_, i) => (
        <div key={i} className="skeleton" />
      ))}
    </div>
  )
}
