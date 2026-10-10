import { describe, expect, it } from 'vitest'
import { NAV, navFor, type Role } from '@/lib/nav'
import { ROUTES } from './routes'

const ROLES: Role[] = ['owner', 'accountant', 'store', 'supervisor', 'qc', 'dispatch', 'buyer']

describe('route table', () => {
  it('has one route for every screen in spec section 11 (34)', () => {
    expect(ROUTES).toHaveLength(34)
  })

  it('has no duplicate paths', () => {
    const paths = ROUTES.map((r) => r.path)
    expect(new Set(paths).size).toBe(paths.length)
  })

  it('every menu link points at a real route', () => {
    const paths = new Set(ROUTES.map((r) => `/${r.path}`))
    for (const item of NAV) expect(paths.has(item.href), item.href).toBe(true)
  })

  it('every role can open every page that is in its own menu', () => {
    for (const role of ROLES) {
      for (const item of navFor(role)) {
        const route = ROUTES.find((r) => `/${r.path}` === item.href)!
        const allowed = route.roles === 'all' || route.roles.includes(role)
        expect(allowed, `${role} -> ${item.href}`).toBe(true)
      }
    }
  })

  it('keeps buyers out of every staff page except their own invoice, passport and portal', () => {
    const buyerPaths = ROUTES.filter((r) => r.roles === 'all' || r.roles.includes('buyer')).map((r) => r.path)
    expect(buyerPaths.sort()).toEqual(['invoices/:no', 'portal', 'portal/orders/:code', 'r/:code'].sort())
  })

  it('every route has a title and a description', () => {
    for (const r of ROUTES) {
      expect(r.title.length).toBeGreaterThan(0)
      expect(r.description.length).toBeGreaterThan(0)
    }
  })
})
