// Adapted from motion-primitives "Tilt" (MIT, https://motion-primitives.com).
// Changes: plain CSS, reduced-motion support, pointer events (works with a pen or touch as well as a mouse).
import { motion, useMotionTemplate, useMotionValue, useReducedMotion, useSpring, useTransform, type SpringOptions } from 'motion/react'
import { useRef, type PointerEvent, type ReactNode } from 'react'

type Props = {
  children: ReactNode
  className?: string
  /** maximum tilt in degrees */
  rotationFactor?: number
  springOptions?: SpringOptions
}

/** Tilts its content towards the pointer. Use on one hero card, such as the Roll Passport header. */
export function Tilt({ children, className, rotationFactor = 8, springOptions }: Props) {
  const reduce = useReducedMotion()
  const ref = useRef<HTMLDivElement>(null)
  const x = useMotionValue(0)
  const y = useMotionValue(0)
  const xSpring = useSpring(x, springOptions)
  const ySpring = useSpring(y, springOptions)
  const rotateX = useTransform(ySpring, [-0.5, 0.5], [-rotationFactor, rotationFactor])
  const rotateY = useTransform(xSpring, [-0.5, 0.5], [rotationFactor, -rotationFactor])
  const transform = useMotionTemplate`perspective(1000px) rotateX(${rotateX}deg) rotateY(${rotateY}deg)`

  if (reduce) return <div className={className}>{children}</div>

  function onMove(e: PointerEvent<HTMLDivElement>) {
    const box = ref.current?.getBoundingClientRect()
    if (!box) return
    x.set((e.clientX - box.left) / box.width - 0.5)
    y.set((e.clientY - box.top) / box.height - 0.5)
  }
  function onLeave() {
    x.set(0)
    y.set(0)
  }

  return (
    <motion.div ref={ref} className={className} style={{ transformStyle: 'preserve-3d', transform }} onPointerMove={onMove} onPointerLeave={onLeave}>
      {children}
    </motion.div>
  )
}
