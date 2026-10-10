import { Bot, Boxes, ClipboardCheck, ClipboardList, Factory, FileText, Gauge, IdCard, Layers, LineChart, PackageCheck, PackagePlus, Ruler, Settings, ShieldCheck, ShoppingBag, Ticket, Truck, Users, Wallet, Warehouse, type LucideIcon } from 'lucide-react'
import type { components } from '@contracts/types'

export type Role = components['schemas']['Me']['role']

export type NavItem = { href: string; label: string; group: string; roles: Role[]; icon: LucideIcon }

export const NAV: NavItem[] = [
  { href: '/store/receive', label: 'Receive yarn', group: 'Store', roles: ['store'], icon: PackagePlus },
  { href: '/store/stock', label: 'Yarn stock', group: 'Store', roles: ['store', 'owner'], icon: Warehouse },
  { href: '/orders', label: 'Orders', group: 'Production', roles: ['owner', 'accountant', 'supervisor'], icon: ClipboardList },
  { href: '/floor', label: 'Floor board', group: 'Production', roles: ['supervisor', 'owner'], icon: Factory },
  { href: '/qc', label: 'Quality check', group: 'Quality', roles: ['qc'], icon: ClipboardCheck },
  { href: '/qc/model', label: 'Vision model', group: 'Quality', roles: ['qc', 'owner'], icon: ShieldCheck },
  { href: '/dispatch', label: 'Dispatch', group: 'Dispatch', roles: ['dispatch', 'owner'], icon: Truck },
  { href: '/money/receivables', label: 'Receivables', group: 'Money', roles: ['accountant', 'owner'], icon: Wallet },
  { href: '/money/payables', label: 'Payables', group: 'Money', roles: ['accountant', 'owner'], icon: FileText },
  { href: '/people/attendance', label: 'Attendance', group: 'People', roles: ['supervisor', 'owner'], icon: IdCard },
  { href: '/people/workers', label: 'Workers', group: 'People', roles: ['accountant', 'owner'], icon: Users },
  { href: '/people/wages', label: 'Wages', group: 'People', roles: ['accountant', 'owner'], icon: Wallet },
  { href: '/owner', label: 'Month-end', group: 'Owner', roles: ['owner'], icon: Gauge },
  { href: '/owner/insights', label: 'Insights', group: 'Owner', roles: ['owner'], icon: LineChart },
  { href: '/copilot', label: 'Copilot', group: 'AI', roles: ['owner', 'accountant', 'supervisor'], icon: Bot },
  { href: '/settings/ai', label: 'AI settings', group: 'AI', roles: ['owner'], icon: Settings },
  { href: '/admin/suppliers', label: 'Suppliers', group: 'Master data', roles: ['owner'], icon: Truck },
  { href: '/admin/buyers', label: 'Buyers', group: 'Master data', roles: ['owner'], icon: ShoppingBag },
  { href: '/admin/buyer-invites', label: 'Buyer invites', group: 'Master data', roles: ['owner'], icon: Ticket },
  { href: '/admin/yarn-types', label: 'Yarn types', group: 'Master data', roles: ['owner'], icon: Boxes },
  { href: '/admin/fabric-types', label: 'Fabric types', group: 'Master data', roles: ['owner'], icon: Layers },
  { href: '/admin/machines', label: 'Machines', group: 'Master data', roles: ['owner'], icon: Factory },
  { href: '/admin/shifts', label: 'Shifts', group: 'Master data', roles: ['owner'], icon: Ruler },
  { href: '/admin/users', label: 'Users', group: 'Master data', roles: ['owner'], icon: Users },
  { href: '/portal', label: 'My orders', group: 'Orders', roles: ['buyer'], icon: PackageCheck },
]

export const navFor = (role: Role) => NAV.filter((item) => item.roles.includes(role))

const HOME: Record<Role, string> = {
  owner: '/owner',
  accountant: '/money/receivables',
  store: '/store/receive',
  supervisor: '/floor',
  qc: '/qc',
  dispatch: '/dispatch',
  buyer: '/portal',
}
export const homeFor = (role: Role) => HOME[role]

export const ROLE_LABEL: Record<Role, string> = {
  owner: 'Owner',
  accountant: 'Accountant',
  store: 'Store',
  supervisor: 'Supervisor',
  qc: 'QC inspector',
  dispatch: 'Dispatch',
  buyer: 'Buyer',
}

/** Only ever returns a path on this site, so a crafted `?next=` can never send someone elsewhere. */
export function safeNext(next: string | null): string | null {
  if (!next || !next.startsWith('/') || next.startsWith('//') || next.startsWith('/\\')) return null
  if (next === '/login' || next.startsWith('/login?')) return null
  return next
}
