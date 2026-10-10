import { EmptyState } from './EmptyState'
import { PageHeader } from './PageHeader'

/** Stands in for a screen that a later plan (A2 to A9) builds. */
export function RoutePlaceholder({ title, description }: { title: string; description: string }) {
  return (
    <>
      <PageHeader title={title} description={description} />
      <EmptyState title="This screen is being built" description="It will appear here in an upcoming update." />
    </>
  )
}
