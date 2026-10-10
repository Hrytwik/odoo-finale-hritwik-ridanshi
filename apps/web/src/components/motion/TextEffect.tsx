// Adapted from motion-primitives "Text Effect" (MIT, https://motion-primitives.com).
// Changes: plain CSS (no Tailwind), a fixed set of tags, reduced-motion support. Screen readers read the whole text once.
import { motion, useReducedMotion, type Variants } from 'motion/react'
import { memo, type CSSProperties } from 'react'

export type TextPreset = 'fade' | 'blur' | 'fade-in-blur' | 'scale' | 'slide'
export type TextPer = 'word' | 'char' | 'line'

const TAGS = { h1: motion.h1, h2: motion.h2, h3: motion.h3, p: motion.p, span: motion.span, div: motion.div } as const

const ITEMS: Record<TextPreset, Variants> = {
  fade: { hidden: { opacity: 0 }, visible: { opacity: 1 } },
  blur: { hidden: { opacity: 0, filter: 'blur(12px)' }, visible: { opacity: 1, filter: 'blur(0px)' } },
  'fade-in-blur': { hidden: { opacity: 0, y: 20, filter: 'blur(12px)' }, visible: { opacity: 1, y: 0, filter: 'blur(0px)' } },
  scale: { hidden: { opacity: 0, scale: 0 }, visible: { opacity: 1, scale: 1 } },
  slide: { hidden: { opacity: 0, y: 20 }, visible: { opacity: 1, y: 0 } },
}

const STAGGER: Record<TextPer, number> = { char: 0.03, word: 0.05, line: 0.1 }

type Props = {
  children: string
  per?: TextPer
  as?: keyof typeof TAGS
  preset?: TextPreset
  /** seconds before the first segment appears */
  delay?: number
  className?: string
  style?: CSSProperties
}

const Segment = memo(function Segment({ text, per, variants }: { text: string; per: TextPer; variants: Variants }) {
  if (per === 'line') {
    return (
      <motion.span variants={variants} className="text-effect-line">
        {text}
      </motion.span>
    )
  }
  if (per === 'word') {
    return (
      <motion.span aria-hidden="true" variants={variants} className="text-effect-seg">
        {text}
      </motion.span>
    )
  }
  return (
    <span className="text-effect-seg" aria-hidden="true">
      {text.split('').map((ch, i) => (
        <motion.span key={i} variants={variants} className="text-effect-seg">
          {ch}
        </motion.span>
      ))}
    </span>
  )
})

/** Reveals a heading or sentence word by word (or letter by letter). Use it once per screen, on the main headline. */
export function TextEffect({ children, per = 'word', as = 'p', preset = 'fade', delay = 0, className, style }: Props) {
  const reduce = useReducedMotion()
  const Tag = TAGS[as]
  if (reduce) {
    const Plain = as
    return (
      <Plain className={className} style={style}>
        {children}
      </Plain>
    )
  }
  const segments = per === 'line' ? children.split('\n') : children.split(/(\s+)/)
  return (
    <Tag
      className={className}
      style={style}
      initial="hidden"
      animate="visible"
      // the container must animate a real value (opacity), otherwise Motion never starts its children
      variants={{ hidden: { opacity: 0 }, visible: { opacity: 1, transition: { staggerChildren: STAGGER[per], delayChildren: delay } } }}
    >
      {per !== 'line' && <span className="sr-only">{children}</span>}
      {segments.map((seg, i) => (
        <Segment key={`${i}-${seg}`} text={seg} per={per} variants={ITEMS[preset]} />
      ))}
    </Tag>
  )
}
