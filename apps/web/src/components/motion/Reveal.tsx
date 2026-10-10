import { motion, useReducedMotion } from 'motion/react'
import type { ReactNode } from 'react'

type Props = {
  children: ReactNode
  /** seconds to wait before starting, to stagger a list */
  delay?: number
  /** how far it rises from, in px */
  y?: number
  className?: string
}

/** Fades and lifts its content in once, when it first scrolls into view. Does nothing if the user prefers reduced motion. */
export function Reveal({ children, delay = 0, y = 14, className }: Props) {
  const reduce = useReducedMotion()
  if (reduce) return <div className={className}>{children}</div>
  return (
    <motion.div
      className={className}
      initial={{ opacity: 0, y }}
      whileInView={{ opacity: 1, y: 0 }}
      viewport={{ once: true, margin: '0px 0px -40px 0px' }}
      transition={{ duration: 0.45, delay, ease: [0.16, 1, 0.3, 1] }}
    >
      {children}
    </motion.div>
  )
}
