// Adapted from motion-primitives "Spotlight" (MIT, https://motion-primitives.com).
// Changes: plain CSS instead of Tailwind; the parent needs the `spotlight-host` class instead of being restyled by script.
import { motion, useReducedMotion, useSpring, useTransform, type SpringOptions } from 'motion/react'
import { useEffect, useRef, useState } from 'react'

type Props = {
  size?: number
  springOptions?: SpringOptions
}

/** A soft light that follows the pointer inside its parent (add class `spotlight-host` to the parent). */
export function Spotlight({ size = 260, springOptions = { bounce: 0 } }: Props) {
  const reduce = useReducedMotion()
  const ref = useRef<HTMLDivElement>(null)
  const [hovered, setHovered] = useState(false)
  const x = useSpring(0, springOptions)
  const y = useSpring(0, springOptions)
  const left = useTransform(x, (v) => `${v - size / 2}px`)
  const top = useTransform(y, (v) => `${v - size / 2}px`)

  useEffect(() => {
    const parent = ref.current?.parentElement
    if (!parent || reduce) return
    const abort = new AbortController()
    const { signal } = abort
    parent.addEventListener(
      'pointermove',
      (e) => {
        const box = parent.getBoundingClientRect()
        x.set(e.clientX - box.left)
        y.set(e.clientY - box.top)
      },
      { signal },
    )
    parent.addEventListener('pointerenter', () => setHovered(true), { signal })
    parent.addEventListener('pointerleave', () => setHovered(false), { signal })
    return () => abort.abort()
  }, [x, y, reduce])

  if (reduce) return null
  return <motion.div ref={ref} aria-hidden className={`spotlight${hovered ? ' is-on' : ''}`} style={{ width: size, height: size, left, top }} />
}
