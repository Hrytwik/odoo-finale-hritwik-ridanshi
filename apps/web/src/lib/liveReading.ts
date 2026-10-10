import { useReducedMotion } from 'motion/react'
import { useEffect, useState } from 'react'

type Stage = 'spinning' | 'weaving' | 'dyeing'

/**
 * A machine speed reading for the floor board. The mill has no sensors connected yet, so this is a simulated
 * reading that drifts around a steady value for each machine. When the API starts sending real speeds, pass
 * them in and this stops being used.
 */
export const SPEED: Record<Stage, { low: number; high: number; spread: number; unit: string }> = {
  weaving: { low: 505, high: 555, spread: 12, unit: 'RPM' },
  spinning: { low: 10800, high: 11600, spread: 90, unit: 'RPM' },
  dyeing: { low: 28, high: 36, spread: 1.4, unit: 'm/min' },
}

/** The same machine always settles around the same speed: a number from its code. */
export function baseSpeed(code: string, stage: Stage): number {
  let h = 0
  for (const ch of code) h = (h * 31 + ch.charCodeAt(0)) >>> 0
  const { low, high } = SPEED[stage]
  return Math.round(low + (h % (high - low + 1)))
}

/** The next reading: a small random step around the base, never far from it. */
export function nextReading(base: number, spread: number, random: () => number = Math.random): number {
  return Math.round(base + (random() * 2 - 1) * spread)
}

/** A speed that keeps moving while `active`. `null` when the machine is not running. Still, at its base value, if the user prefers reduced motion. */
export function useLiveSpeed(code: string, stage: Stage, active: boolean): number | null {
  const reduce = useReducedMotion()
  const base = baseSpeed(code, stage)
  const [value, setValue] = useState(base)

  useEffect(() => {
    if (!active || reduce) return
    const id = window.setInterval(() => setValue(nextReading(base, SPEED[stage].spread)), 1100)
    return () => window.clearInterval(id)
  }, [active, reduce, base, stage])

  if (!active) return null
  return reduce ? base : value
}
