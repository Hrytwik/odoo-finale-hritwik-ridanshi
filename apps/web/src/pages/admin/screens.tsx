import { useQuery } from '@tanstack/react-query'
import { Badge } from '@/components/ui/Badge'
import { api, call, type components } from '@/lib/api'
import { useMe } from '@/lib/auth'
import { formatKg, formatMoney } from '@/lib/format'
import { ROLE_LABEL } from '@/lib/nav'
import { MasterScreen, type Values } from './MasterScreen'

type Schemas = components['schemas']
const num = (v: string) => Number(v.trim())
/** an empty optional text box means "none" */
const opt = (v: string | undefined) => (v && v.trim() ? v.trim() : null)
const dash = (v: string | null) => v ?? <span className="muted">-</span>
const time = (t: string) => t.slice(0, 5)

const STAGES = [
  { value: 'spinning', label: 'Spinning' },
  { value: 'weaving', label: 'Weaving' },
  { value: 'dyeing', label: 'Dyeing' },
]
const WORKER_ROLES = [
  { value: 'operator', label: 'Operator' },
  { value: 'inspector', label: 'Inspector' },
  { value: 'storekeeper', label: 'Storekeeper' },
  { value: 'supervisor', label: 'Supervisor' },
  { value: 'dispatch', label: 'Dispatch' },
  { value: 'helper', label: 'Helper' },
]
const stageLabel = (s: string) => STAGES.find((x) => x.value === s)?.label ?? s
const workerRoleLabel = (r: string) => WORKER_ROLES.find((x) => x.value === r)?.label ?? r
const active = (a: boolean) => (a ? <Badge tone="green">Active</Badge> : <Badge tone="gray">Inactive</Badge>)

export function Suppliers() {
  type Row = Schemas['SupplierOut']
  return (
    <MasterScreen<Row>
      eyebrow="Master data"
      title="Suppliers"
      description="Yarn suppliers and how many days they take to deliver."
      singular="supplier"
      queryKey={['master', 'suppliers']}
      load={() => call(api.GET('/api/suppliers'))}
      columns={[
        { header: 'Name', cell: (r) => <strong>{r.name}</strong> },
        { header: 'Phone', cell: (r) => dash(r.phone) },
        { header: 'Lead time', cell: (r) => `${r.lead_time_days} days`, num: true },
      ]}
      fields={[
        { name: 'name', label: 'Name', required: true },
        { name: 'phone', label: 'Phone', kind: 'tel' },
        { name: 'lead_time_days', label: 'Lead time (days)', kind: 'number', required: true },
      ]}
      initial={(r) => ({ name: r?.name ?? '', phone: r?.phone ?? '', lead_time_days: String(r?.lead_time_days ?? 7) })}
      create={(v) => call(api.POST('/api/suppliers', { body: { name: v.name.trim(), phone: opt(v.phone), lead_time_days: num(v.lead_time_days) } }))}
      update={(r, v) =>
        call(api.PATCH('/api/suppliers/{item_id}', { params: { path: { item_id: r.id } }, body: { name: v.name.trim(), phone: opt(v.phone), lead_time_days: num(v.lead_time_days) } }))
      }
      empty={{ title: 'No suppliers yet', description: 'Add the mills you buy yarn from.' }}
      alsoInvalidate={[['stock']]}
    />
  )
}

export function Buyers() {
  type Row = Schemas['BuyerOut']
  const body = (v: Values) => ({ name: v.name.trim(), contact_name: opt(v.contact_name), phone: opt(v.phone), email: opt(v.email) })
  return (
    <MasterScreen<Row>
      eyebrow="Master data"
      title="Buyers"
      description="The companies you sell cloth to, and who to call there."
      singular="buyer"
      queryKey={['master', 'buyers']}
      load={() => call(api.GET('/api/buyers'))}
      columns={[
        { header: 'Name', cell: (r) => <strong>{r.name}</strong> },
        { header: 'Contact', cell: (r) => dash(r.contact_name) },
        { header: 'Phone', cell: (r) => dash(r.phone) },
        { header: 'Email', cell: (r) => dash(r.email) },
      ]}
      fields={[
        { name: 'name', label: 'Name', required: true },
        { name: 'contact_name', label: 'Contact person' },
        { name: 'phone', label: 'Phone', kind: 'tel' },
        { name: 'email', label: 'Email', kind: 'email' },
      ]}
      initial={(r) => ({ name: r?.name ?? '', contact_name: r?.contact_name ?? '', phone: r?.phone ?? '', email: r?.email ?? '' })}
      create={(v) => call(api.POST('/api/buyers', { body: body(v) }))}
      update={(r, v) => call(api.PATCH('/api/buyers/{item_id}', { params: { path: { item_id: r.id } }, body: body(v) }))}
      empty={{ title: 'No buyers yet', description: 'Add a buyer before creating an order for them.' }}
    />
  )
}

export function YarnTypes() {
  type Row = Schemas['YarnTypeOut']
  const body = (v: Values) => ({ code: v.code.trim(), name: v.name.trim(), colour: v.colour.trim(), reorder_level_kg: num(v.reorder_level_kg || '0') })
  return (
    <MasterScreen<Row>
      eyebrow="Master data"
      title="Yarn types"
      description="Each kind of yarn, and the stock level at which the system suggests reordering."
      singular="yarn type"
      queryKey={['master', 'yarn-types']}
      load={() => call(api.GET('/api/yarn-types'))}
      columns={[
        { header: 'Code', cell: (r) => <span className="code-text">{r.code}</span> },
        { header: 'Name', cell: (r) => r.name },
        { header: 'Colour', cell: (r) => r.colour },
        { header: 'Reorder at', cell: (r) => formatKg(r.reorder_level_kg), num: true },
      ]}
      fields={[
        { name: 'code', label: 'Code', required: true },
        { name: 'name', label: 'Name', required: true },
        { name: 'colour', label: 'Colour', required: true },
        { name: 'reorder_level_kg', label: 'Reorder level (kg)', kind: 'number', hint: 'Suggest a reorder when free stock falls below this' },
      ]}
      initial={(r) => ({ code: r?.code ?? '', name: r?.name ?? '', colour: r?.colour ?? '', reorder_level_kg: String(r?.reorder_level_kg ?? 0) })}
      create={(v) => call(api.POST('/api/yarn-types', { body: body(v) }))}
      update={(r, v) => call(api.PATCH('/api/yarn-types/{item_id}', { params: { path: { item_id: r.id } }, body: body(v) }))}
      empty={{ title: 'No yarn types yet', description: 'Add the yarns you spin and weave with.' }}
      alsoInvalidate={[['stock'], ['master', 'fabric-types']]}
    />
  )
}

export function Machines() {
  type Row = Schemas['MachineOut']
  const common = (v: Values) => ({
    code: v.code.trim(),
    name: v.name.trim(),
    rated_output_per_hour: num(v.rated_output_per_hour),
    running_cost_per_hour: num(v.running_cost_per_hour || '0'),
    active: v.active === 'true',
  })
  return (
    <MasterScreen<Row>
      eyebrow="Master data"
      title="Machines"
      description="Every spinning frame, loom and jigger, with its rated speed and what it costs to run."
      singular="machine"
      queryKey={['master', 'machines']}
      load={() => call(api.GET('/api/machines'))}
      columns={[
        { header: 'Code', cell: (r) => <span className="code-text">{r.code}</span> },
        { header: 'Name', cell: (r) => r.name },
        { header: 'Stage', cell: (r) => stageLabel(r.stage) },
        { header: 'Rated output', cell: (r) => `${r.rated_output_per_hour} / hour`, num: true },
        { header: 'Running cost', cell: (r) => `${formatMoney(r.running_cost_per_hour)} / hour`, num: true },
        { header: 'Status', cell: (r) => active(r.active) },
      ]}
      fields={[
        { name: 'code', label: 'Code', required: true },
        { name: 'name', label: 'Name', required: true },
        { name: 'stage', label: 'Stage', kind: 'select', required: true, options: STAGES, only: 'create', hint: 'A machine keeps its stage for life' },
        { name: 'rated_output_per_hour', label: 'Rated output per hour', kind: 'number', required: true, hint: 'kg for spinning, metres for weaving and dyeing' },
        { name: 'running_cost_per_hour', label: 'Running cost per hour (₹)', kind: 'number' },
        { name: 'active', label: 'In use', kind: 'checkbox' },
      ]}
      initial={(r) => ({
        code: r?.code ?? '',
        name: r?.name ?? '',
        stage: r?.stage ?? '',
        rated_output_per_hour: String(r?.rated_output_per_hour ?? ''),
        running_cost_per_hour: String(r?.running_cost_per_hour ?? 0),
        active: String(r?.active ?? true),
      })}
      create={(v) => call(api.POST('/api/machines', { body: { ...common(v), stage: v.stage as Row['stage'] } }))}
      update={(r, v) => call(api.PATCH('/api/machines/{item_id}', { params: { path: { item_id: r.id } }, body: common(v) }))}
      empty={{ title: 'No machines yet', description: 'Add the machines on the floor.' }}
      alsoInvalidate={[['floor']]}
    />
  )
}

export function Shifts() {
  type Row = Schemas['ShiftOut']
  return (
    <MasterScreen<Row>
      eyebrow="Master data"
      title="Shifts"
      description="The names and hours of your shifts. Wages and machine hours are split by shift."
      singular="shift"
      queryKey={['master', 'shifts']}
      load={() => call(api.GET('/api/shifts'))}
      columns={[
        { header: 'Shift', cell: (r) => <span className="code-text">{r.name}</span> },
        { header: 'Starts', cell: (r) => time(r.start_time) },
        { header: 'Ends', cell: (r) => time(r.end_time) },
      ]}
      fields={[
        { name: 'name', label: 'Name', required: true, only: 'create', hint: 'Up to 10 characters, e.g. A or Night' },
        { name: 'start_time', label: 'Starts at', kind: 'time', required: true },
        { name: 'end_time', label: 'Ends at', kind: 'time', required: true },
      ]}
      initial={(r) => ({ name: r?.name ?? '', start_time: r ? time(r.start_time) : '', end_time: r ? time(r.end_time) : '' })}
      create={(v) => call(api.POST('/api/shifts', { body: { name: v.name.trim(), start_time: v.start_time, end_time: v.end_time } }))}
      update={(r, v) => call(api.PATCH('/api/shifts/{item_id}', { params: { path: { item_id: r.id } }, body: { start_time: v.start_time, end_time: v.end_time } }))}
      empty={{ title: 'No shifts yet', description: 'Add the shifts your mill runs.' }}
    />
  )
}

export function Workers() {
  type Row = Schemas['WorkerOut']
  const me = useMe()
  const common = (v: Values) => ({ name: v.name.trim(), role: v.role as Row['role'], daily_wage: num(v.daily_wage), active: v.active === 'true' })
  return (
    <MasterScreen<Row>
      eyebrow="People"
      title="Workers"
      description="Everyone on the payroll, with the daily wage used to work out what each roll really cost."
      singular="worker"
      queryKey={['master', 'workers']}
      load={() => call(api.GET('/api/workers'))}
      // supervisors and accountants can look; only the owner changes the payroll
      canEdit={me.data?.role === 'owner'}
      columns={[
        { header: 'Code', cell: (r) => <span className="code-text">{r.code}</span> },
        { header: 'Name', cell: (r) => r.name },
        { header: 'Role', cell: (r) => workerRoleLabel(r.role) },
        { header: 'Daily wage', cell: (r) => formatMoney(r.daily_wage), num: true },
        { header: 'Status', cell: (r) => active(r.active) },
      ]}
      fields={[
        { name: 'code', label: 'Code', required: true, only: 'create' },
        { name: 'name', label: 'Name', required: true },
        { name: 'role', label: 'Role', kind: 'select', required: true, options: WORKER_ROLES },
        { name: 'daily_wage', label: 'Daily wage (₹)', kind: 'number', required: true },
        { name: 'active', label: 'On the payroll', kind: 'checkbox' },
      ]}
      initial={(r) => ({ code: r?.code ?? '', name: r?.name ?? '', role: r?.role ?? '', daily_wage: String(r?.daily_wage ?? ''), active: String(r?.active ?? true) })}
      create={(v) => call(api.POST('/api/workers', { body: { code: v.code.trim(), ...common(v) } }))}
      update={(r, v) => call(api.PATCH('/api/workers/{item_id}', { params: { path: { item_id: r.id } }, body: common(v) }))}
      empty={{ title: 'No workers yet', description: 'Add the people who work on the floor.' }}
      alsoInvalidate={[['people']]}
    />
  )
}

const USER_ROLES = (Object.keys(ROLE_LABEL) as (keyof typeof ROLE_LABEL)[]).map((value) => ({ value, label: ROLE_LABEL[value] }))

export function Users() {
  type Row = Schemas['UserOut']
  const workers = useQuery({ queryKey: ['master', 'workers'], queryFn: () => call(api.GET('/api/workers')) })
  const buyers = useQuery({ queryKey: ['master', 'buyers'], queryFn: () => call(api.GET('/api/buyers')) })
  const workerName = (id: number | null) => workers.data?.find((w) => w.id === id)?.name ?? (id ? `#${id}` : null)
  const buyerName = (id: number | null) => buyers.data?.find((b) => b.id === id)?.name ?? (id ? `#${id}` : null)
  return (
    <MasterScreen<Row>
      eyebrow="Master data"
      title="Users"
      description="Who can log in, and what each login can see. A buyer login belongs to one buyer; a QC login to one inspector."
      singular="user"
      queryKey={['master', 'users']}
      load={() => call(api.GET('/api/users'))}
      columns={[
        { header: 'Username', cell: (r) => <span className="code-text">{r.username}</span> },
        { header: 'Role', cell: (r) => ROLE_LABEL[r.role] },
        { header: 'Linked to', cell: (r) => dash(r.buyer_id ? buyerName(r.buyer_id) : workerName(r.worker_id)) },
      ]}
      fields={[
        { name: 'username', label: 'Username', required: true, only: 'create' },
        { name: 'role', label: 'Role', kind: 'select', required: true, options: USER_ROLES, only: 'create' },
        { name: 'password', label: 'Password', kind: 'password', required: true, only: 'create', hint: 'At least 6 characters' },
        { name: 'new_password', label: 'New password', kind: 'password', only: 'edit', hint: 'Leave empty to keep the current one' },
        { name: 'worker_id', label: 'Linked worker', kind: 'select', options: (workers.data ?? []).map((w) => ({ value: String(w.id), label: `${w.name} (${w.code})` })) },
        { name: 'buyer_id', label: 'Linked buyer', kind: 'select', only: 'create', options: (buyers.data ?? []).map((b) => ({ value: String(b.id), label: b.name })) },
      ]}
      initial={(r) => ({ username: r?.username ?? '', role: r?.role ?? '', password: '', new_password: '', worker_id: r?.worker_id ? String(r.worker_id) : '', buyer_id: '' })}
      create={(v) =>
        call(
          api.POST('/api/users', {
            body: {
              username: v.username.trim(),
              password: v.password,
              role: v.role as Row['role'],
              worker_id: v.worker_id ? Number(v.worker_id) : null,
              buyer_id: v.buyer_id ? Number(v.buyer_id) : null,
            },
          }),
        )
      }
      update={(r, v) =>
        call(
          api.PATCH('/api/users/{item_id}', {
            params: { path: { item_id: r.id } },
            body: { ...(v.new_password ? { password: v.new_password } : {}), worker_id: v.worker_id ? Number(v.worker_id) : null },
          }),
        )
      }
      empty={{ title: 'No users yet', description: 'Add a login for each person who uses the system.' }}
    />
  )
}
