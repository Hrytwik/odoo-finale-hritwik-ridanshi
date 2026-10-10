// Adapted from motion-primitives "Animated Group" (MIT, https://motion-primitives.com).
// Changes: plain CSS (no Tailwind), no dynamic element creation during render, reduced-motion support.
import { motion, useReducedMotion, type Variants } from 'motion/react'
import { Children, type ReactNode } from 'react'

export type GroupPreset = 'fade' | 'slide' | 'scale' | 'blur' | 'blur-slide' | 'zoom'

const PRESETS: Record<GroupPreset, Variants> = {
  fade: {},
  slide: { hidden: { y: 20 }, visible: { y: 0 } },
  scale: { hidden: { scale: 0.92 }, visible: { scale: 1 } },
  blur: { hidden: { filter: 'blur(4px)' }, visible: { filter: 'blur(0px)' } },
  'blur-slide': { hidden: { filter: 'blur(4px)', y: 20 }, visible: { filter: 'blur(0px)', y: 0 } },
  zoom: { hidden: { scale: 0.6 }, visible: { scale: 1, transition: { type: 'spring', stiffness: 300, damping: 20 } } },
}

type Props = {
  children: ReactNode
  className?: string
  preset?: GroupPreset
  /** seconds between one child appearing and the next */
  stagger?: number
}

/** Brings its children in one after another. Wrap a card grid, a KPI row or a list. */
export function AnimatedGroup({ children, className, preset = 'blur-slide', stagger = 0.08 }: Props) {
  const reduce = useReducedMotion()
  if (reduce) return <div className={className}>{children}</div>

  const item: Variants = {
    hidden: { opacity: 0, ...(PRESETS[preset].hidden as object) },
    visible: { opacity: 1, ...(PRESETS[preset].visible as object) },
  }
  return (
    // the container must animate a real value (opacity), otherwise Motion never starts its children
    <motion.div
      className={className}
      initial="hidden"
      animate="visible"
      variants={{ hidden: { opacity: 0 }, visible: { opacity: 1, transition: { staggerChildren: stagger } } }}
    >
      {Children.map(children, (child, i) => (
        <motion.div key={i} variants={item} style={{ minWidth: 0 }}>
          {child}
        </motion.div>
      ))}
    </motion.div>
  )
}
