import { useI18n } from '@/i18n/I18nContext'
import { EmptyState } from './EmptyState'
import { PageHeader } from './PageHeader'

/** Stands in for a screen that a later plan (A2 to A9) builds. */
export function RoutePlaceholder({ title, description }: { title: string; description: string }) {
  const { t } = useI18n()
  return (
    <>
      <PageHeader title={title} description={description} />
      <EmptyState title={t('placeholder.title')} description={t('placeholder.body')} />
    </>
  )
}
