import type { ReactNode } from 'react'

export function PageHeader({
  title,
  description,
  actions,
  eyebrow,
}: {
  title: string
  description?: string
  actions?: ReactNode
  /** a small line above the title, usually the menu group the page belongs to */
  eyebrow?: string
}) {
  return (
    <div className="page-header">
      <div style={{ minWidth: 0 }}>
        {eyebrow && <p className="eyebrow">{eyebrow}</p>}
        <h1>{title}</h1>
        {description && <p className="muted text-sm">{description}</p>}
      </div>
      {actions && <div className="page-header-actions">{actions}</div>}
    </div>
  )
}
