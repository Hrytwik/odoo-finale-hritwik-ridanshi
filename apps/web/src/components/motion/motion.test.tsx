import { render, screen, waitFor } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import { AnimatedGroup } from './AnimatedGroup'
import { AnimatedNumber } from './AnimatedNumber'
import { BorderTrail } from './BorderTrail'
import { GlowEffect } from './GlowEffect'
import { Reveal } from './Reveal'
import { Spotlight } from './Spotlight'
import { TextEffect } from './TextEffect'
import { TextShimmer } from './TextShimmer'

describe('motion components', () => {
  it('AnimatedNumber starts on its value, with the given format', () => {
    render(<AnimatedNumber value={200000} format={(n) => `₹${Math.round(n).toLocaleString('en-IN')}`} />)
    expect(screen.getByText('₹2,00,000')).toBeInTheDocument()
  })

  it('AnimatedNumber defaults to Indian digit grouping', () => {
    render(<AnimatedNumber value={1234567} />)
    expect(screen.getByText('12,34,567')).toBeInTheDocument()
  })

  it('TextEffect keeps the whole sentence available to screen readers', () => {
    render(<TextEffect as="h2">Every roll, from yarn to invoice.</TextEffect>)
    expect(screen.getByRole('heading', { level: 2, name: 'Every roll, from yarn to invoice.' })).toBeInTheDocument()
  })

  it('TextEffect words actually become visible (regression: they stayed at opacity 0)', async () => {
    const { container } = render(<TextEffect as="h2">Every roll</TextEffect>)
    const words = container.querySelectorAll<HTMLElement>('span.text-effect-seg[aria-hidden="true"]')
    expect(words.length).toBeGreaterThan(0)
    await waitFor(() => {
      for (const w of words) expect(Number(getComputedStyle(w).opacity)).toBe(1)
    })
  })

  it('AnimatedGroup children actually become visible', async () => {
    const { container } = render(
      <AnimatedGroup>
        <p>one</p>
        <p>two</p>
      </AnimatedGroup>,
    )
    await waitFor(() => {
      for (const p of container.querySelectorAll<HTMLElement>('p')) {
        expect(Number(getComputedStyle(p.parentElement as HTMLElement).opacity)).toBe(1)
      }
    })
  })

  it('TextShimmer shows its text', () => {
    render(<TextShimmer>Thinking</TextShimmer>)
    expect(screen.getByText('Thinking')).toBeInTheDocument()
  })

  it('AnimatedGroup renders every child, in order', () => {
    render(
      <AnimatedGroup>
        <p>one</p>
        <p>two</p>
        <p>three</p>
      </AnimatedGroup>,
    )
    expect(screen.getAllByText(/one|two|three/).map((e) => e.textContent)).toEqual(['one', 'two', 'three'])
  })

  it('Reveal renders its content', () => {
    render(<Reveal>hello</Reveal>)
    expect(screen.getByText('hello')).toBeInTheDocument()
  })

  it('decorative effects are hidden from screen readers', () => {
    const { container } = render(
      <div className="spotlight-host">
        <GlowEffect />
        <BorderTrail />
        <Spotlight />
      </div>,
    )
    const decorative = container.querySelectorAll('.glow-effect, .border-trail, .spotlight')
    expect(decorative.length).toBeGreaterThan(0)
    for (const el of decorative) expect(el).toHaveAttribute('aria-hidden', 'true')
  })
})
