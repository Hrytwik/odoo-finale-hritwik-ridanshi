import { describe, expect, it } from 'vitest'
import { SPEED, baseSpeed, nextReading } from './liveReading'

describe('simulated machine speed', () => {
  it('gives the same machine the same base speed every time', () => {
    expect(baseSpeed('LOOM-04', 'weaving')).toBe(baseSpeed('LOOM-04', 'weaving'))
  })

  it('keeps each stage in a believable range', () => {
    for (const code of ['LOOM-01', 'LOOM-02', 'LOOM-03', 'LOOM-12', 'X']) {
      const s = baseSpeed(code, 'weaving')
      expect(s).toBeGreaterThanOrEqual(SPEED.weaving.low)
      expect(s).toBeLessThanOrEqual(SPEED.weaving.high)
    }
    expect(baseSpeed('SPIN-01', 'spinning')).toBeGreaterThan(10000)
    expect(baseSpeed('DYE-01', 'dyeing')).toBeLessThan(40)
  })

  it('moves a little around the base, never further than the spread', () => {
    expect(nextReading(500, 12, () => 0)).toBe(488)
    expect(nextReading(500, 12, () => 1)).toBe(512)
    expect(nextReading(500, 12, () => 0.5)).toBe(500)
  })
})
