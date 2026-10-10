import { describe, expect, it } from 'vitest'
import { formatDate, formatDateTime, formatKg, formatMetres, formatMoney, formatQty } from './format'

describe('format', () => {
  it('formats rupees with Indian grouping and no decimals', () => {
    expect(formatMoney(200000)).toBe('₹2,00,000')
    expect(formatMoney(-101175)).toBe('-₹1,01,175')
  })

  it('formats quantities with units and at most one decimal', () => {
    expect(formatKg(587.54)).toBe('587.5 kg')
    expect(formatMetres(5000)).toBe('5,000 m')
    expect(formatQty(12.25, 'kg')).toBe('12.3 kg')
    expect(formatQty(12, 'm')).toBe('12 m')
  })

  it('shows dates in IST', () => {
    // 20:00 UTC on 10 Oct is 01:30 IST on 11 Oct
    expect(formatDate('2026-10-10T20:00:00Z')).toContain('11')
    expect(formatDate('2026-10-10T20:00:00Z')).toContain('Oct')
    expect(formatDate('2026-10-20')).toContain('20')
    expect(formatDateTime('2026-10-10T20:00:00Z')).toMatch(/1:30/)
  })
})
