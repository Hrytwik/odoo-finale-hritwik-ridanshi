import type { ComponentProps, ReactNode } from 'react'
import { cx } from '@/lib/cx'

export function Card({ title, children, className, ...props }: ComponentProps<'section'> & { title?: ReactNode }) {
  return (
    <section className={cx('card', className)} {...props}>
      {title && (
        <header className="card-header">
          <h2 className="card-title">{title}</h2>
        </header>
      )}
      <div className="card-body">{children}</div>
    </section>
  )
}
