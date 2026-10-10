import { describe, expect, it } from 'vitest'
import { niceScale, yFor } from './chart'

describe('niceScale', () => {
  it('covers every value with round ticks', () => {
    const s = niceScale([145200, 246375, 412000])
    expect(s.min).toBe(0)
    expect(s.max).toBeGreaterThanOrEqual(412000)
    expect(s.ticks[0]).toBe(0)
    expect(s.ticks.at(-1)).toBe(s.max)
    // evenly spaced
    const gaps = new Set(s.ticks.slice(1).map((t, i) => t - s.ticks[i]))
    expect(gaps.size).toBe(1)
  })

  it('reaches below zero for a loss', () => {
    const s = niceScale([-101175, 145200])
    expect(s.min).toBeLessThan(-101175 + 1)
    expect(s.ticks).toContain(0)
  })

  it('does not break on no data or all zeros', () => {
    expect(niceScale([]).max).toBeGreaterThan(niceScale([]).min)
    expect(niceScale([0, 0]).max).toBeGreaterThan(0)
  })

  it('uses 1, 2 or 5 times a power of ten for the step', () => {
    for (const top of [7, 90, 1234, 560000]) {
      const [a, b] = niceScale([top]).ticks
      const step = b - a
      expect([1, 2, 5]).toContain(Number((step / 10 ** Math.floor(Math.log10(step))).toFixed(6)))
    }
  })
})

describe('yFor', () => {
  it('puts the top of the scale at 0 and the bottom at the full height', () => {
    const scale = { min: 0, max: 100 }
    expect(yFor(100, scale, 200)).toBe(0)
    expect(yFor(0, scale, 200)).toBe(200)
    expect(yFor(50, scale, 200)).toBe(100)
  })
})
