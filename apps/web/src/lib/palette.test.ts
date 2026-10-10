import { describe, expect, it } from 'vitest'
import { jumpTargets, pageResults } from './palette'

const hrefs = (text: string, role: Parameters<typeof jumpTargets>[1]) => jumpTargets(text, role).map((t) => t.href)

describe('jumpTargets: typing a code', () => {
  it('opens a roll for anyone, by its code, in any case', () => {
    expect(hrefs('R-0142', 'owner')).toEqual(['/r/R-0142'])
    expect(hrefs('r-0142', 'buyer')).toEqual(['/r/R-0142'])
  })

  it('opens an order, in the portal for a buyer and in the orders area for staff', () => {
    expect(hrefs('ORD-0012', 'owner')).toEqual(['/orders/ORD-0012'])
    expect(hrefs('ORD-0012', 'supervisor')).toEqual(['/orders/ORD-0012'])
    expect(hrefs('ORD-0012', 'buyer')).toEqual(['/portal/orders/ORD-0012'])
  })

  it('opens a yarn lot only for the roles that may see lots', () => {
    expect(hrefs('L-0017', 'store')).toEqual(['/store/lots/L-0017'])
    expect(hrefs('L-0017', 'owner')).toEqual(['/store/lots/L-0017'])
    expect(hrefs('L-0017', 'qc')).toEqual([])
    expect(hrefs('L-0017', 'buyer')).toEqual([])
  })

  it('opens a dispatch only for dispatch and the owner', () => {
    expect(hrefs('DSP-0007', 'dispatch')).toEqual(['/dispatch/DSP-0007'])
    expect(hrefs('DSP-0007', 'supervisor')).toEqual([])
  })

  it('opens an invoice for finance, dispatch and the buyer', () => {
    expect(hrefs('INV-0007', 'accountant')).toEqual(['/invoices/INV-0007'])
    expect(hrefs('INV-0007', 'buyer')).toEqual(['/invoices/INV-0007'])
    expect(hrefs('INV-0007', 'store')).toEqual([])
  })

  it('never offers a jump for text that is not exactly a code', () => {
    expect(hrefs('', 'owner')).toEqual([])
    expect(hrefs('hello', 'owner')).toEqual([])
    expect(hrefs('R-', 'owner')).toEqual([])
    expect(hrefs('R-0142 and more', 'owner')).toEqual([])
    expect(hrefs('https://evil.example/r/R-0142', 'owner')).toEqual([])
  })

  it('labels the jump in plain words', () => {
    expect(jumpTargets('R-0142', 'owner')[0].label).toBe('Open roll R-0142')
    expect(jumpTargets('ORD-0012', 'owner')[0].label).toBe('Open order ORD-0012')
  })
})

describe('pageResults: searching the menu', () => {
  it('lists only the pages the role has in its own menu', () => {
    const labels = pageResults('', 'buyer').map((p) => p.label)
    expect(labels).toEqual(['My orders'])
  })

  it('finds a page by part of its name, ignoring case', () => {
    expect(pageResults('floor', 'supervisor').map((p) => p.label)).toContain('Floor board')
    expect(pageResults('FLOOR', 'supervisor').map((p) => p.label)).toContain('Floor board')
  })

  it('also matches the group a page is in', () => {
    const labels = pageResults('money', 'accountant').map((p) => p.label)
    expect(labels).toEqual(expect.arrayContaining(['Receivables', 'Payables']))
  })

  it('never shows a page the role cannot use', () => {
    expect(pageResults('month', 'supervisor').map((p) => p.label)).not.toContain('Month-end')
    expect(pageResults('users', 'store')).toEqual([])
  })

  it('returns nothing when nothing matches', () => {
    expect(pageResults('zzzz', 'owner')).toEqual([])
  })
})
