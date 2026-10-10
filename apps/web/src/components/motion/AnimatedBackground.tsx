// Adapted from motion-primitives "Animated Background" (MIT, https://motion-primitives.com).
// Changes: plain CSS instead of Tailwind. Wrap a row of items that each have a `data-id`; a highlight slides between them.
import { AnimatePresence, motion, type Transition } from 'motion/react'
import { Children, cloneElement, useId, useState, type ReactElement } from 'react'

type Item = ReactElement<{ 'data-id': string; className?: string; children?: React.ReactNode }>

type Props = {
  children: Item | Item[]
  /** the id highlighted at the start (and whenever it changes) */
  defaultValue?: string
  onValueChange?: (id: string | null) => void
  /** class for the sliding highlight (colour, radius) */
  className?: string
  transition?: Transition
  /** highlight on hover instead of on click */
  enableHover?: boolean
}

export function AnimatedBackground({ children, defaultValue, onValueChange, className, transition, enableHover = false }: Props) {
  // `active` follows `defaultValue` when that changes, and the user's own picks in between
  const [active, setActive] = useState({ from: defaultValue, id: defaultValue ?? null })
  if (active.from !== defaultValue) setActive({ from: defaultValue, id: defaultValue ?? null })
  const activeId = active.id
  const uid = useId()

  function set(id: string | null) {
    setActive({ from: defaultValue, id })
    onValueChange?.(id)
  }

  return Children.map(children, (child, index) => {
    const id = child.props['data-id']
    const interaction = enableHover
      ? { onMouseEnter: () => set(id), onMouseLeave: () => set(null) }
      : { onClick: () => set(id) }
    return cloneElement(
      child,
      {
        key: index,
        className: ['ab-item', child.props.className].filter(Boolean).join(' '),
        'data-checked': activeId === id ? 'true' : 'false',
        ...interaction,
      } as object,
      <>
        <AnimatePresence initial={false}>
          {activeId === id && (
            <motion.div
              layoutId={`ab-${uid}`}
              className={['ab-highlight', className].filter(Boolean).join(' ')}
              transition={transition ?? { type: 'spring', bounce: 0.2, duration: 0.4 }}
              initial={{ opacity: defaultValue ? 1 : 0 }}
              animate={{ opacity: 1 }}
              exit={{ opacity: 0 }}
            />
          )}
        </AnimatePresence>
        <div className="ab-content">{child.props.children}</div>
      </>,
    )
  })
}
