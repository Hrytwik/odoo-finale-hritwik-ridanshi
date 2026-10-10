// Inspired by motion-primitives "Sliding Number" (MIT, https://motion-primitives.com).
// Rewritten without react-use-measure: each digit is a column of 0 to 9 that slides by whole em, so no measuring is needed.
import { motion, useReducedMotion, useSpring, useTransform } from 'motion/react'
import { useEffect } from 'react'

const SPRING = { stiffness: 260, damping: 22, mass: 0.4 }

function Digit({ digit }: { digit: number }) {
  const reduce = useReducedMotion()
  const spring = useSpring(digit, SPRING)
  const y = useTransform(spring, (v) => `${-v}em`)
  useEffect(() => {
    if (reduce) spring.jump(digit)
    else spring.set(digit)
  }, [digit, spring, reduce])
  return (
    <span className="sn-digit" aria-hidden="true">
      <motion.span className="sn-column" style={{ y }}>
        {[0, 1, 2, 3, 4, 5, 6, 7, 8, 9].map((n) => (
          <span key={n}>{n}</span>
        ))}
      </motion.span>
    </span>
  )
}

/** A number whose digits roll like an odometer when `value` changes. Pass `format` for ₹ or units; digits roll, other characters stay. */
export function SlidingNumber({ value, format = (n: number) => Math.round(n).toLocaleString('en-IN') }: { value: number; format?: (n: number) => string }) {
  const text = format(value)
  // key digits by their place counted from the right, so the units digit stays the units digit when the number grows
  let place = text.replace(/\D/g, '').length
  return (
    <span className="sn" role="text" aria-label={text}>
      {[...text].map((ch, i) => {
        if (/\d/.test(ch)) {
          place -= 1
          return <Digit key={`d${place}`} digit={Number(ch)} />
        }
        return (
          <span key={`s${i}`} aria-hidden="true">
            {ch}
          </span>
        )
      })}
    </span>
  )
}
