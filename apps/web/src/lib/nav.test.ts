import { describe, expect, it } from 'vitest'
import { NAV, homeFor, navFor, safeNext, type Role } from './nav'

const ROLES: Role[] = ['owner', 'accountant', 'store', 'supervisor', 'qc', 'dispatch', 'buyer']

describe('navigation', () => {
  it('gives a buyer only the portal', () => {
    expect(navFor('buyer').map((i) => i.href)).toEqual(['/portal'])
  })

  it('gives the store keeper the gate and stock', () => {
    const hrefs = navFor('store').map((i) => i.href)
    expect(hrefs).toContain('/store/receive')
    expect(hrefs).toContain('/store/stock')
    expect(hrefs).not.toContain('/owner')
  })

  it('gives the owner month-end and master data', () => {
    const hrefs = navFor('owner').map((i) => i.href)
    expect(hrefs).toEqual(expect.arrayContaining(['/owner', '/owner/insights', '/admin/users', '/settings/ai']))
  })

  it("every role's home page is in its own menu", () => {
    for (const role of ROLES) {
      expect(navFor(role).map((i) => i.href)).toContain(homeFor(role))
    }
  })

  it('has no duplicate links', () => {
    const hrefs = NAV.map((i) => i.href)
    expect(new Set(hrefs).size).toBe(hrefs.length)
  })

  it('never shows a staff-only page to a buyer', () => {
    const buyerHrefs = navFor('buyer').map((i) => i.href)
    expect(buyerHrefs.every((h) => h.startsWith('/portal'))).toBe(true)
  })
})

describe('safeNext', () => {
  it('accepts local paths', () => expect(safeNext('/orders/ORD-0012')).toBe('/orders/ORD-0012'))
  it('rejects other sites', () => {
    expect(safeNext('https://evil.example')).toBeNull()
    expect(safeNext('//evil.example')).toBeNull()
    expect(safeNext('/\\evil.example')).toBeNull()
  })
  it('rejects the login page itself and empty values', () => {
    expect(safeNext('/login')).toBeNull()
    expect(safeNext('/login?next=/x')).toBeNull()
    expect(safeNext(null)).toBeNull()
    expect(safeNext('')).toBeNull()
  })
})

describe('what the owner can reach from the menu', () => {
  it('lists every screen the owner is allowed to open, not only the ones the owner uses most', () => {
    const hrefs = navFor('owner').map((i) => i.href)
    expect(hrefs).toEqual(expect.arrayContaining(['/dispatch', '/people/attendance', '/people/workers', '/people/wages']))
  })
})
