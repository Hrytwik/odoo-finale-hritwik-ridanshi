// Adapted from motion-primitives "Text Shimmer" (MIT, https://motion-primitives.com).
// Changes: plain CSS variables instead of Tailwind classes, reduced-motion support.
import { motion, useReducedMotion } from 'motion/react'
import type { CSSProperties } from 'react'

type Props = {
  children: string
  /** seconds per sweep */
  duration?: number
  className?: string
}

/** Text with a light sweeping across it. Good for "the assistant is thinking" and other waiting states. */
export function TextShimmer({ children, duration = 2, className }: Props) {
  const reduce = useReducedMotion()
  const spread = children.length * 2
  const style = { '--spread': `${spread}px` } as CSSProperties
  if (reduce) return <span className={className}>{children}</span>
  return (
    <motion.span
      className={className ? `text-shimmer ${className}` : 'text-shimmer'}
      style={style}
      initial={{ backgroundPosition: '100% center' }}
      animate={{ backgroundPosition: '0% center' }}
      transition={{ repeat: Infinity, duration, ease: 'linear' }}
    >
      {children}
    </motion.span>
  )
}
