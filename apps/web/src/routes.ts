import type { Role } from '@/lib/nav'

export type RouteDef = {
  /** React Router path, relative to the app root */
  path: string
  title: string
  description: string
  /** who may open it (spec section 11). The backend enforces this too; the UI only mirrors it. */
  roles: Role[] | 'all'
}

const OWNER: Role[] = ['owner']

/** Every screen in spec section 11. Plans A2 to A9 replace the placeholder behind each entry with the real screen. */
export const ROUTES: RouteDef[] = [
  { path: 'store/receive', title: 'Receive yarn', description: 'Log a yarn delivery at the gate.', roles: ['store'] },
  { path: 'store/stock', title: 'Yarn stock', description: 'Stock per yarn type, what open orders need, and what is free.', roles: ['store', 'owner'] },
  { path: 'store/lots/:code', title: 'Yarn lot', description: 'Lot ledger, blocking and recall.', roles: ['store', 'owner'] },
  { path: 'orders', title: 'Orders', description: 'Every buyer order with progress, yarn and delivery status.', roles: ['owner', 'accountant', 'supervisor'] },
  { path: 'orders/new', title: 'New order', description: 'Create a draft order for a buyer.', roles: ['owner', 'accountant'] },
  { path: 'orders/:code', title: 'Order', description: 'Progress, delivery date, cost and profit.', roles: ['owner', 'accountant', 'supervisor'] },
  { path: 'floor', title: 'Floor board', description: 'Every machine, live.', roles: ['supervisor', 'owner'] },
  { path: 'floor/machines/:code', title: 'Machine', description: 'Start, hand over, roll off, breakdown and repair.', roles: ['supervisor', 'owner'] },
  { path: 'qc', title: 'Quality check', description: 'Rolls waiting to be checked.', roles: ['qc'] },
  { path: 'qc/model', title: 'Vision model', description: 'How the defect model performed on held-out photos.', roles: ['qc', 'owner'] },
  { path: 'qc/:rollCode', title: 'Inspect roll', description: 'Photograph, review the AI suggestion, record the verdict.', roles: ['qc'] },
  { path: 'r/:code', title: 'Roll passport', description: 'The full life of one roll.', roles: 'all' },
  { path: 'dispatch', title: 'Dispatch', description: 'Trucks being loaded and sent.', roles: ['dispatch', 'owner'] },
  { path: 'dispatch/:code', title: 'Load truck', description: 'Scan rolls onto the truck, then confirm.', roles: ['dispatch', 'owner'] },
  { path: 'invoices/:no', title: 'Invoice', description: 'Printable invoice.', roles: ['dispatch', 'accountant', 'owner', 'buyer'] },
  { path: 'money/receivables', title: 'Receivables', description: 'Invoices and payments from buyers.', roles: ['accountant', 'owner'] },
  { path: 'money/payables', title: 'Payables', description: 'Supplier bills and payments.', roles: ['accountant', 'owner'] },
  { path: 'people/workers', title: 'Workers', description: 'Everyone on the payroll.', roles: ['accountant', 'supervisor', 'owner'] },
  { path: 'people/attendance', title: 'Attendance', description: 'Mark attendance for a shift.', roles: ['supervisor', 'owner'] },
  { path: 'people/wages', title: 'Wages', description: 'Wages earned, paid and owed.', roles: ['accountant', 'owner'] },
  { path: 'owner', title: 'Month-end', description: 'Profit, cash, machines and idle labour for the month.', roles: OWNER },
  { path: 'owner/insights', title: 'Insights', description: 'Late orders, reorder suggestions and defect causes.', roles: OWNER },
  { path: 'copilot', title: 'Copilot', description: 'Ask questions about the mill in plain language.', roles: ['owner', 'accountant', 'supervisor'] },
  { path: 'settings/ai', title: 'AI settings', description: 'Choose the language model provider and model.', roles: OWNER },
  { path: 'settings/ai/report-card', title: 'AI report card', description: 'How the configured model scores on known questions.', roles: OWNER },
  { path: 'admin/suppliers', title: 'Suppliers', description: 'Yarn suppliers and lead times.', roles: OWNER },
  { path: 'admin/buyers', title: 'Buyers', description: 'Buyers and their contacts.', roles: OWNER },
  { path: 'admin/buyer-invites', title: 'Buyer invites', description: 'Invite codes buyers use to create their own login.', roles: OWNER },
  { path: 'admin/yarn-types', title: 'Yarn types', description: 'Yarn types and reorder levels.', roles: OWNER },
  { path: 'admin/fabric-types', title: 'Fabric types', description: 'Fabric types and their yarn recipes.', roles: OWNER },
  { path: 'admin/machines', title: 'Machines', description: 'Machines, stages, speeds and running costs.', roles: OWNER },
  { path: 'admin/shifts', title: 'Shifts', description: 'Shift names and times.', roles: OWNER },
  { path: 'admin/users', title: 'Users', description: 'Logins and roles.', roles: OWNER },
  { path: 'portal', title: 'My orders', description: 'Where each of your orders stands.', roles: ['buyer'] },
  { path: 'portal/orders/:code', title: 'Order status', description: 'Timeline, delivery date and dispatches.', roles: ['buyer'] },
]
