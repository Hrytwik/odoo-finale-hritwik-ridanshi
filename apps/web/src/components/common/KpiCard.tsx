import type { ReactNode } from 'react'
import { AnimatedNumber } from '@/components/motion/AnimatedNumber'
import { SlidingNumber } from '@/components/motion/SlidingNumber'

type Props = {
  label: string
  value: number
  /** turns the number into text, e.g. formatMoney or formatKg */
  format?: (n: number) => string
  hint?: ReactNode
  tone?: 'danger'
  /** `count` counts up smoothly (default); `odometer` rolls each digit like a meter */
  motion?: 'count' | 'odometer'
}

/** One headline number. It animates to its value and again whenever live data changes it. */
export function KpiCard({ label, value, format, hint, tone, motion = 'count' }: Props) {
  return (
    <div className="kpi">
      <span className="kpi-label">{label}</span>
      <span className={tone === 'danger' ? 'kpi-value text-danger' : 'kpi-value'}>
        {motion === 'odometer' ? <SlidingNumber value={value} format={format} /> : <AnimatedNumber value={value} format={format} />}
      </span>
      {hint && <span className="muted text-sm">{hint}</span>}
    </div>
  )
}
