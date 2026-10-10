// Adapted from motion-primitives "Glow Effect" (MIT, https://motion-primitives.com).
// Changes: plain CSS instead of Tailwind, brand colours by default, reduced-motion support.
import { motion, useReducedMotion, type TargetAndTransition, type Transition } from 'motion/react'
import type { CSSProperties } from 'react'

type Mode = 'rotate' | 'pulse' | 'breathe' | 'colorShift' | 'flowHorizontal' | 'static'

type Props = {
  colors?: string[]
  mode?: Mode
  /** blur radius in px */
  blur?: number
  duration?: number
  scale?: number
  transition?: Transition
  style?: CSSProperties
}

const BRAND = ['#658c58', '#31694e', '#bbc863', '#658c58']

/** A soft animated glow behind its parent. The parent needs `position: relative`. */
export function GlowEffect({ colors = BRAND, mode = 'rotate', blur = 24, duration = 8, scale = 1, transition, style }: Props) {
  const reduce = useReducedMotion()
  const base: Transition = { repeat: Infinity, duration, ease: 'linear' }
  const mirror: Transition = { ...base, repeatType: 'mirror' }

  const radial = colors.map((c) => `radial-gradient(circle at 50% 50%, ${c} 0%, transparent 100%)`)
  const animations: Record<Mode, TargetAndTransition> = {
    rotate: {
      background: [
        `conic-gradient(from 0deg at 50% 50%, ${colors.join(', ')})`,
        `conic-gradient(from 360deg at 50% 50%, ${colors.join(', ')})`,
      ],
      transition: transition ?? base,
    },
    pulse: { background: radial, scale: [scale, scale * 1.1, scale], opacity: [0.5, 0.8, 0.5], transition: transition ?? mirror },
    breathe: { background: radial, scale: [scale, scale * 1.05, scale], transition: transition ?? mirror },
    colorShift: {
      background: colors.map((c, i) => `conic-gradient(from 0deg at 50% 50%, ${c} 0%, ${colors[(i + 1) % colors.length]} 50%, ${c} 100%)`),
      transition: transition ?? mirror,
    },
    flowHorizontal: {
      background: colors.map((c, i) => `linear-gradient(to right, ${c}, ${colors[(i + 1) % colors.length]})`),
      transition: transition ?? mirror,
    },
    static: { background: `linear-gradient(to right, ${colors.join(', ')})` },
  }

  const target = reduce ? animations.static : animations[mode]

  return (
    <motion.div
      aria-hidden
      className="glow-effect"
      style={{ filter: `blur(${blur}px)`, scale, ...style }}
      animate={target}
    />
  )
}
