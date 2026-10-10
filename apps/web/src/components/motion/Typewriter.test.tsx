import { act, render, screen } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { TIMING } from '@/lib/typewriter'
import { Typewriter } from './Typewriter'

const PHRASES = ['from yarn to invoice.', 'from loom to buyer.']

beforeEach(() => vi.useFakeTimers())
afterEach(() => vi.useRealTimers())

const visible = (container: HTMLElement) => container.querySelector('.typewriter-line')?.textContent ?? ''

describe('Typewriter', () => {
  it('shows the whole first sentence to screen readers', () => {
    render(<Typewriter before="Every roll," phrases={PHRASES} />)
    expect(screen.getByRole('heading', { name: 'Every roll, from yarn to invoice.' })).toBeInTheDocument()
  })

  it('starts with the first phrase fully typed', () => {
    const { container } = render(<Typewriter before="Every roll," phrases={PHRASES} />)
    expect(visible(container)).toBe('from yarn to invoice.')
  })

  it('deletes it after a rest, then types the next phrase', () => {
    const { container } = render(<Typewriter before="Every roll," phrases={PHRASES} />)
    // the rest, then the first deleted letter
    act(() => void vi.advanceTimersByTime(TIMING.hold + TIMING.remove))
    expect(visible(container).length).toBeLessThan(PHRASES[0].length)
    // delete the rest, wait, and type a few letters of the next phrase
    act(() => void vi.advanceTimersByTime(PHRASES[0].length * TIMING.remove + TIMING.wait + TIMING.type * 4))
    expect(PHRASES[1].startsWith(visible(container))).toBe(true)
    expect(visible(container).length).toBeGreaterThan(0)
  })

  it('stops its timer when it goes away', () => {
    const { unmount } = render(<Typewriter before="Every roll," phrases={PHRASES} />)
    unmount()
    expect(vi.getTimerCount()).toBe(0)
  })

  it('does not animate with one phrase only', () => {
    render(<Typewriter before="Every roll," phrases={[PHRASES[0]]} />)
    expect(vi.getTimerCount()).toBe(0)
  })
})
