import type { ReactNode } from 'react'

export function EmptyState({ title, description, action }: { title: string; description?: string; action?: ReactNode }) {
  return (
    <div className="state-box">
      <p style={{ fontWeight: 600 }}>{title}</p>
      {description && <p className="muted text-sm">{description}</p>}
      {action}
    </div>
  )
}
