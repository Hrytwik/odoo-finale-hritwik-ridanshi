import type { ReactNode } from 'react'

/** Inline message. `error` is announced to screen readers; `info` is not. */
export function Alert({ tone = 'info', children }: { tone?: 'error' | 'info'; children: ReactNode }) {
  return (
    <div role={tone === 'error' ? 'alert' : undefined} className={`alert alert-${tone}`}>
      {children}
    </div>
  )
}
