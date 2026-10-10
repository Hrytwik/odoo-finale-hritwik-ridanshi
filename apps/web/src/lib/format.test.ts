import { describe, expect, it } from 'vitest'
import { formatDate, formatDateTime, formatKg, formatLakh, formatMetres, formatMoney, formatPercent, formatQty } from './format'

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

  it('says big amounts in lakhs and crores, as an owner would', () => {
    expect(formatLakh(4280000)).toBe('₹42.8 L')
    expect(formatLakh(53500)).toBe('₹53,500')
    expect(formatLakh(10000000)).toBe('₹1 Cr')
    expect(formatLakh(12500000)).toBe('₹1.3 Cr')
    expect(formatLakh(-250000)).toBe('-₹2.5 L')
    expect(formatLakh(0)).toBe('₹0')
  })

  it('shows a fraction as a whole percent', () => {
    expect(formatPercent(0.456)).toBe('46%')
    expect(formatPercent(1)).toBe('100%')
    expect(formatPercent(0)).toBe('0%')
  })
})
