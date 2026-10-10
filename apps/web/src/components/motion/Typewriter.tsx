import { useReducedMotion } from 'motion/react'
import { useEffect, useState } from 'react'
import { startState, step, type TypeState } from '@/lib/typewriter'

type Props = {
  /** the fixed first line */
  before: string
  /** the second line: each phrase is typed out, held, deleted, and the next one typed */
  phrases: string[]
  as?: 'h1' | 'h2'
}

/** A headline whose last line types itself with a blinking caret. Screen readers get the whole first sentence; reduced motion gets it still. */
export function Typewriter({ before, phrases, as: Tag = 'h2' }: Props) {
  const reduce = useReducedMotion()
  const [state, setState] = useState<TypeState>(() => startState(phrases))

  useEffect(() => {
    if (reduce || phrases.length < 2) return
    let timer: number
    let current = state
    const tick = (delay: number) => {
      timer = window.setTimeout(() => {
        const { next, delay: nextDelay } = step(current, phrases)
        current = next
        setState(next)
        tick(nextDelay)
      }, delay)
    }
    tick(step(current, phrases).delay)
    return () => window.clearTimeout(timer)
    // the loop owns its own state after the first render
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [reduce, phrases])

  const text = phrases[state.index].slice(0, state.length)
  const typing = state.phase === 'typing' || state.phase === 'deleting'
  return (
    <Tag aria-label={`${before} ${phrases[0]}`}>
      <span aria-hidden="true">
        {before}
        <span className="typewriter-line">
          {text}
          <span className={typing ? 'typewriter-caret is-typing' : 'typewriter-caret'} />
        </span>
      </span>
    </Tag>
  )
}
