import { ROUTES } from '@/routes'
import { navFor, type NavItem, type Role } from './nav'

export type Jump = { label: string; href: string }

/** Whether `role` may open the screen at this route pattern (from the route table, the same one the app uses). */
function canOpen(role: Role, pattern: string): boolean {
  const route = ROUTES.find((r) => r.path === pattern)
  return !!route && (route.roles === 'all' || route.roles.includes(role))
}

const CODES: { test: RegExp; label: string; pattern: string; href: (code: string, role: Role) => string }[] = [
  { test: /^R-\d+$/, label: 'roll', pattern: 'r/:code', href: (c) => `/r/${c}` },
  { test: /^ORD-\d+$/, label: 'order', pattern: 'orders/:code', href: (c, role) => (role === 'buyer' ? `/portal/orders/${c}` : `/orders/${c}`) },
  { test: /^L-\d+$/, label: 'yarn lot', pattern: 'store/lots/:code', href: (c) => `/store/lots/${c}` },
  { test: /^DSP-\d+$/, label: 'dispatch', pattern: 'dispatch/:code', href: (c) => `/dispatch/${c}` },
  { test: /^INV-\d+$/, label: 'invoice', pattern: 'invoices/:no', href: (c) => `/invoices/${c}` },
]

/** If the text is exactly a roll, order, lot, dispatch or invoice code, where would it open for this role? Otherwise nothing. */
export function jumpTargets(text: string, role: Role): Jump[] {
  const code = text.trim().toUpperCase()
  if (!code) return []
  const out: Jump[] = []
  for (const c of CODES) {
    if (!c.test.test(code)) continue
    // a buyer opens an order in the portal, which has its own route
    const pattern = c.pattern === 'orders/:code' && role === 'buyer' ? 'portal/orders/:code' : c.pattern
    if (canOpen(role, pattern)) out.push({ label: `Open ${c.label} ${code}`, href: c.href(code, role) })
  }
  return out
}

/** The role's own menu, filtered by what was typed (matches the page name or its group). */
export function pageResults(query: string, role: Role): NavItem[] {
  const q = query.trim().toLowerCase()
  const items = navFor(role)
  if (!q) return items
  return items.filter((i) => i.label.toLowerCase().includes(q) || i.group.toLowerCase().includes(q))
}
