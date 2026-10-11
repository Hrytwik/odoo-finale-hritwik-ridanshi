import { Bot, Boxes, ClipboardCheck, ClipboardList, Factory, FileText, Gauge, IdCard, Layers, LineChart, PackageCheck, PackagePlus, Ruler, Settings, ShieldCheck, ShoppingBag, Ticket, Truck, Users, Wallet, Warehouse, type LucideIcon } from 'lucide-react'
import type { components } from '@contracts/types'
import type { Key } from '@/i18n/en'

export type Role = components['schemas']['Me']['role']

export type NavItem = { labelKey: Key; href: string; label: string; group: string; roles: Role[]; icon: LucideIcon }

export const NAV: NavItem[] = [
  { labelKey: 'nav.receive', href: '/store/receive', label: 'Receive yarn', group: 'Store', roles: ['store'], icon: PackagePlus },
  { labelKey: 'nav.stock', href: '/store/stock', label: 'Yarn stock', group: 'Store', roles: ['store', 'owner'], icon: Warehouse },
  { labelKey: 'nav.orders', href: '/orders', label: 'Orders', group: 'Production', roles: ['owner', 'accountant', 'supervisor'], icon: ClipboardList },
  { labelKey: 'nav.floor', href: '/floor', label: 'Floor board', group: 'Production', roles: ['supervisor', 'owner'], icon: Factory },
  { labelKey: 'nav.qc', href: '/qc', label: 'Quality check', group: 'Quality', roles: ['qc'], icon: ClipboardCheck },
  { labelKey: 'nav.visionModel', href: '/qc/model', label: 'Vision model', group: 'Quality', roles: ['qc', 'owner'], icon: ShieldCheck },
  { labelKey: 'nav.dispatch', href: '/dispatch', label: 'Dispatch', group: 'Dispatch', roles: ['dispatch', 'owner'], icon: Truck },
  { labelKey: 'nav.receivables', href: '/money/receivables', label: 'Receivables', group: 'Money', roles: ['accountant', 'owner'], icon: Wallet },
  { labelKey: 'nav.payables', href: '/money/payables', label: 'Payables', group: 'Money', roles: ['accountant', 'owner'], icon: FileText },
  { labelKey: 'nav.attendance', href: '/people/attendance', label: 'Attendance', group: 'People', roles: ['supervisor', 'owner'], icon: IdCard },
  { labelKey: 'nav.workers', href: '/people/workers', label: 'Workers', group: 'People', roles: ['accountant', 'owner'], icon: Users },
  { labelKey: 'nav.wages', href: '/people/wages', label: 'Wages', group: 'People', roles: ['accountant', 'owner'], icon: Wallet },
  { labelKey: 'nav.monthEnd', href: '/owner', label: 'Month-end', group: 'Owner', roles: ['owner'], icon: Gauge },
  { labelKey: 'nav.insights', href: '/owner/insights', label: 'Insights', group: 'Owner', roles: ['owner'], icon: LineChart },
  { labelKey: 'nav.copilot', href: '/copilot', label: 'Copilot', group: 'AI', roles: ['owner', 'accountant', 'supervisor'], icon: Bot },
  { labelKey: 'nav.aiSettings', href: '/settings/ai', label: 'AI settings', group: 'AI', roles: ['owner'], icon: Settings },
  { labelKey: 'nav.suppliers', href: '/admin/suppliers', label: 'Suppliers', group: 'Master data', roles: ['owner'], icon: Truck },
  { labelKey: 'nav.buyers', href: '/admin/buyers', label: 'Buyers', group: 'Master data', roles: ['owner'], icon: ShoppingBag },
  { labelKey: 'nav.buyerInvites', href: '/admin/buyer-invites', label: 'Buyer invites', group: 'Master data', roles: ['owner'], icon: Ticket },
  { labelKey: 'nav.yarnTypes', href: '/admin/yarn-types', label: 'Yarn types', group: 'Master data', roles: ['owner'], icon: Boxes },
  { labelKey: 'nav.fabricTypes', href: '/admin/fabric-types', label: 'Fabric types', group: 'Master data', roles: ['owner'], icon: Layers },
  { labelKey: 'nav.machines', href: '/admin/machines', label: 'Machines', group: 'Master data', roles: ['owner'], icon: Factory },
  { labelKey: 'nav.shifts', href: '/admin/shifts', label: 'Shifts', group: 'Master data', roles: ['owner'], icon: Ruler },
  { labelKey: 'nav.users', href: '/admin/users', label: 'Users', group: 'Master data', roles: ['owner'], icon: Users },
  { labelKey: 'nav.myOrders', href: '/portal', label: 'My orders', group: 'Orders', roles: ['buyer'], icon: PackageCheck },
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
