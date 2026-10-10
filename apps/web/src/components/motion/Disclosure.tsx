// Inspired by motion-primitives "Disclosure" (MIT, https://motion-primitives.com).
// Simplified to one component with a built-in header button, proper aria attributes and reduced-motion support.
import { AnimatePresence, motion, useReducedMotion } from 'motion/react'
import { ChevronDown } from 'lucide-react'
import { useId, useState, type ReactNode } from 'react'

type Props = {
  title: ReactNode
  children: ReactNode
  defaultOpen?: boolean
  /** small text on the right of the header, e.g. a count */
  meta?: ReactNode
}

/** A collapsible section with a smooth height animation. Use for ledgers, long lists and secondary details. */
export function Disclosure({ title, children, defaultOpen = false, meta }: Props) {
  const [open, setOpen] = useState(defaultOpen)
  const reduce = useReducedMotion()
  const id = useId()
  return (
    <section className="disclosure">
      <button type="button" className="disclosure-head" aria-expanded={open} aria-controls={id} onClick={() => setOpen((o) => !o)}>
        <span className="disclosure-title">{title}</span>
        {meta && <span className="muted text-sm">{meta}</span>}
        <ChevronDown size={18} aria-hidden className={open ? 'disclosure-chevron is-open' : 'disclosure-chevron'} />
      </button>
      <AnimatePresence initial={false}>
        {open && (
          <motion.div
            id={id}
            key="content"
            style={{ overflow: 'hidden' }}
            initial={reduce ? false : { height: 0, opacity: 0 }}
            animate={{ height: 'auto', opacity: 1 }}
            exit={reduce ? { opacity: 0 } : { height: 0, opacity: 0 }}
            transition={{ duration: 0.28, ease: [0.16, 1, 0.3, 1] }}
          >
            <div className="disclosure-body">{children}</div>
          </motion.div>
        )}
      </AnimatePresence>
    </section>
  )
}
