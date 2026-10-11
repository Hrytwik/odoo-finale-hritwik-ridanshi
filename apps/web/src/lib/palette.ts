import { ROUTES } from '@/routes'
import { navFor, type NavItem, type Role } from './nav'

export type Jump = { label: string; href: string; kind: 'roll' | 'order' | 'lot' | 'dispatch' | 'invoice'; code: string }

/** Whether `role` may open the screen at this route pattern (from the route table, the same one the app uses). */
function canOpen(role: Role, pattern: string): boolean {
  const route = ROUTES.find((r) => r.path === pattern)
  return !!route && (route.roles === 'all' || route.roles.includes(role))
}

const CODES: { test: RegExp; label: string; kind: Jump['kind']; pattern: string; href: (code: string, role: Role) => string }[] = [
  { test: /^R-\d+$/, label: 'roll', kind: 'roll', pattern: 'r/:code', href: (c) => `/r/${c}` },
  { test: /^ORD-\d+$/, label: 'order', kind: 'order', pattern: 'orders/:code', href: (c, role) => (role === 'buyer' ? `/portal/orders/${c}` : `/orders/${c}`) },
  { test: /^L-\d+$/, label: 'yarn lot', kind: 'lot', pattern: 'store/lots/:code', href: (c) => `/store/lots/${c}` },
  { test: /^DSP-\d+$/, label: 'dispatch', kind: 'dispatch', pattern: 'dispatch/:code', href: (c) => `/dispatch/${c}` },
  { test: /^INV-\d+$/, label: 'invoice', kind: 'invoice', pattern: 'invoices/:no', href: (c) => `/invoices/${c}` },
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
    if (canOpen(role, pattern)) out.push({ label: `Open ${c.label} ${code}`, href: c.href(code, role), kind: c.kind, code })
  }
  return out
}

/** The role's own menu, filtered by what was typed (matches the page name or its group). */
export function pageResults(query: string, role: Role, words: { label: (i: NavItem) => string; group: (i: NavItem) => string } = { label: (i) => i.label, group: (i) => i.group }): NavItem[] {
  const q = query.trim().toLowerCase()
  const items = navFor(role)
  if (!q) return items
  return items.filter((i) => words.label(i).toLowerCase().includes(q) || words.group(i).toLowerCase().includes(q) || i.label.toLowerCase().includes(q))
}
