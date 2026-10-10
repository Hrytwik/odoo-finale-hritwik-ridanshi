import { describe, expect, it } from 'vitest'
import { machineUse } from './ownerReport'

const m = (running_h: number, idle_h: number, down_h: number) => ({ code: 'X', name: 'X', stage: 'weaving' as const, running_h, idle_h, down_h, output: 0, output_unit: 'm' as const, lost_capacity: 0, lost_capacity_unit: 'm' as const })

describe('machineUse', () => {
  it('is running time over all machine time', () => {
    expect(machineUse([m(180, 31, 12)])).toBeCloseTo(180 / 223)
  })
  it('adds up across machines', () => {
    expect(machineUse([m(100, 0, 0), m(0, 100, 0)])).toBe(0.5)
  })
  it('is 0 with no hours at all', () => {
    expect(machineUse([])).toBe(0)
    expect(machineUse([m(0, 0, 0)])).toBe(0)
  })
})
