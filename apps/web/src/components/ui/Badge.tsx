import type { ReactNode } from 'react'

export type Tone = 'green' | 'amber' | 'red' | 'blue' | 'violet' | 'gray'

export function Badge({ tone = 'gray', children }: { tone?: Tone; children: ReactNode }) {
  return <span className={`badge badge-${tone}`}>{children}</span>
}
