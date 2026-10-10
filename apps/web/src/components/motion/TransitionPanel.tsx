// Adapted from motion-primitives "Transition Panel" (MIT, https://motion-primitives.com).
// Changes: plain CSS, direction-aware sliding (forward slides left, back slides right), reduced-motion support.
import { AnimatePresence, motion, useReducedMotion } from 'motion/react'
import { useState, type ReactNode } from 'react'

const VARIANTS = {
  enter: (dir: number) => ({ x: dir * 40, opacity: 0, filter: 'blur(4px)' }),
  center: { x: 0, opacity: 1, filter: 'blur(0px)' },
  exit: (dir: number) => ({ x: dir * -40, opacity: 0, filter: 'blur(4px)' }),
}

/** Shows `children[activeIndex]` and slides between panels, e.g. the steps of a form or the tabs of a report. */
export function TransitionPanel({ activeIndex, children }: { activeIndex: number; children: ReactNode[] }) {
  const reduce = useReducedMotion()
  // remember which way we moved; derived while rendering, so no ref is read during render
  const [nav, setNav] = useState({ index: activeIndex, direction: 1 })
  if (nav.index !== activeIndex) setNav({ index: activeIndex, direction: activeIndex > nav.index ? 1 : -1 })
  const direction = nav.direction

  if (reduce) return <div>{children[activeIndex]}</div>
  return (
    <div className="transition-panel">
      <AnimatePresence initial={false} mode="popLayout" custom={direction}>
        <motion.div
          key={activeIndex}
          custom={direction}
          variants={VARIANTS}
          initial="enter"
          animate="center"
          exit="exit"
          transition={{ duration: 0.3, ease: [0.16, 1, 0.3, 1] }}
        >
          {children[activeIndex]}
        </motion.div>
      </AnimatePresence>
    </div>
  )
}
