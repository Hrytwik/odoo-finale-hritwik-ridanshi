// Adapted from motion-primitives "Border Trail" (MIT, https://motion-primitives.com).
// Changes: plain CSS instead of Tailwind. Put it inside an element with `position: relative` and a border radius.
import { motion, useReducedMotion, type Transition } from 'motion/react'
import type { CSSProperties } from 'react'

type Props = {
  /** length of the glowing trail in px */
  size?: number
  /** seconds for one lap */
  duration?: number
  transition?: Transition
  style?: CSSProperties
}

/** A light that runs around the border of its parent. Use sparingly: one hero card per page. */
export function BorderTrail({ size = 70, duration = 6, transition, style }: Props) {
  const reduce = useReducedMotion()
  if (reduce) return null
  return (
    <div className="border-trail" aria-hidden>
      <motion.div
        className="border-trail-dot"
        style={{ width: size, offsetPath: `rect(0 auto auto 0 round ${size}px)`, ...style }}
        animate={{ offsetDistance: ['0%', '100%'] }}
        transition={transition ?? { repeat: Infinity, duration, ease: 'linear' }}
      />
    </div>
  )
}
