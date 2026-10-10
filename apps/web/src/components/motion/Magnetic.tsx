// Adapted from motion-primitives "Magnetic" (MIT, https://motion-primitives.com).
// Changes: reduced-motion support, and the pointer listener only exists while the pointer is near.
import { motion, useMotionValue, useReducedMotion, useSpring, type SpringOptions } from 'motion/react'
import { useEffect, useRef, useState, type ReactNode } from 'react'

const SPRING: SpringOptions = { stiffness: 150, damping: 15, mass: 0.2 }

type Props = {
  children: ReactNode
  /** how strongly it follows the pointer (0 to 1) */
  intensity?: number
  /** px from its centre at which it starts to follow */
  range?: number
}

/** Pulls its content slightly towards the pointer when it is close. Use on one primary button. */
export function Magnetic({ children, intensity = 0.4, range = 90 }: Props) {
  const reduce = useReducedMotion()
  const ref = useRef<HTMLDivElement>(null)
  const [near, setNear] = useState(false)
  const x = useMotionValue(0)
  const y = useMotionValue(0)
  const sx = useSpring(x, SPRING)
  const sy = useSpring(y, SPRING)

  useEffect(() => {
    if (!near) {
      x.set(0)
      y.set(0)
      return
    }
    const move = (e: PointerEvent) => {
      const box = ref.current?.getBoundingClientRect()
      if (!box) return
      const dx = e.clientX - (box.left + box.width / 2)
      const dy = e.clientY - (box.top + box.height / 2)
      const distance = Math.hypot(dx, dy)
      if (distance > range) {
        x.set(0)
        y.set(0)
        return
      }
      const strength = 1 - distance / range
      x.set(dx * intensity * strength)
      y.set(dy * intensity * strength)
    }
    document.addEventListener('pointermove', move)
    return () => document.removeEventListener('pointermove', move)
  }, [near, intensity, range, x, y])

  if (reduce) return <div style={{ display: 'inline-block' }}>{children}</div>
  return (
    <motion.div ref={ref} style={{ display: 'inline-block', x: sx, y: sy }} onPointerEnter={() => setNear(true)} onPointerLeave={() => setNear(false)}>
      {children}
    </motion.div>
  )
}
