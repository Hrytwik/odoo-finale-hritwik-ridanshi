import { describe, expect, it } from 'vitest'
import { groupWarnings } from './warnings'

describe('groupWarnings', () => {
  it('reads the repeating warnings into rows', () => {
    const g = groupWarnings([
      "Run 2 (LOOM-04, 2026-10-10) has 4.65 hours not covered by its operator's attendance",
      'Run 2 (LOOM-04, 2026-10-10) is still open, so its cost is provisional',
    ])
    expect(g.attendance).toEqual([{ run: 2, machine: 'LOOM-04', date: '2026-10-10', hours: 4.65 }])
    expect(g.provisional).toEqual([{ run: 2, machine: 'LOOM-04', date: '2026-10-10' }])
    expect(g.other).toEqual([])
  })
  it('leaves out a gap of zero hours', () => {
    expect(groupWarnings(["Run 1 (SPIN-01, 2026-10-10) has 0.0 hours not covered by its operator's attendance"]).attendance).toEqual([])
  })
  it('keeps anything else exactly as it was said', () => {
    const text = 'Run 52 (Loom 5, 2026-10-08) has no attendance for its operator'
    expect(groupWarnings([text]).other).toEqual([text])
  })
  it('handles none', () => expect(groupWarnings([])).toEqual({ attendance: [], provisional: [], other: [] }))
})
