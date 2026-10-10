// Adapted from motion-primitives "Animated Number" (MIT, https://motion-primitives.com).
// Changes: plain CSS instead of Tailwind, a `format` prop (₹, kg, metres), and reduced-motion support.
import { motion, useReducedMotion, useSpring, useTransform, type SpringOptions } from 'motion/react'
import { useEffect } from 'react'

type Props = {
  value: number
  /** turns the animated number into text, e.g. formatMoney. Default: whole number with Indian grouping. */
  format?: (n: number) => string
  className?: string
  springOptions?: SpringOptions
}

const defaultFormat = (n: number) => Math.round(n).toLocaleString('en-IN')

/** A number that counts smoothly to its new value whenever `value` changes (live KPIs). */
export function AnimatedNumber({ value, format = defaultFormat, className, springOptions }: Props) {
  const reduce = useReducedMotion()
  const spring = useSpring(value, springOptions ?? { stiffness: 110, damping: 22 })
  const display = useTransform(spring, format)

  useEffect(() => {
    if (reduce) spring.jump(value)
    else spring.set(value)
  }, [spring, value, reduce])

  return <motion.span className={className ? `tabular ${className}` : 'tabular'}>{display}</motion.span>
}
