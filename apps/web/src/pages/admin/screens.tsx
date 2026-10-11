import { useQuery } from '@tanstack/react-query'
import { Badge } from '@/components/ui/Badge'
import type { Key } from '@/i18n/en'
import { useI18n } from '@/i18n/I18nContext'
import { api, call, type components } from '@/lib/api'
import { useMe } from '@/lib/auth'
import { formatKg, formatMoney } from '@/lib/format'
import { ROLE_LABEL } from '@/lib/nav'
import { MasterScreen, type Values } from './MasterScreen'
import { WorkerLoginCell } from './WorkerLogin'

type Schemas = components['schemas']
const num = (v: string) => Number(v.trim())
/** an empty optional text box means "none" */
const opt = (v: string | undefined) => (v && v.trim() ? v.trim() : null)
const dash = (v: string | null) => v ?? <span className="muted">-</span>
const time = (t: string) => t.slice(0, 5)

const STAGE_VALUES = ['spinning', 'weaving', 'dyeing'] as const
const WORKER_ROLE_VALUES = ['operator', 'inspector', 'storekeeper', 'supervisor', 'dispatch', 'helper'] as const

/** The shared words, in the chosen language. */
function useWords() {
  const { t } = useI18n()
  const stageOptions = STAGE_VALUES.map((value) => ({ value, label: t(`floor.stage.${value}` as Key) }))
  const workerRoleOptions = WORKER_ROLE_VALUES.map((value) => ({ value, label: t(`worker.role.${value}` as Key) }))
  return {
    t,
    stageOptions,
    workerRoleOptions,
    stageLabel: (s: string) => stageOptions.find((x) => x.value === s)?.label ?? s,
    workerRoleLabel: (r: string) => workerRoleOptions.find((x) => x.value === r)?.label ?? r,
    active: (a: boolean) => (a ? <Badge tone="green">{t('admin.active')}</Badge> : <Badge tone="gray">{t('admin.inactive')}</Badge>),
  }
}

export function Suppliers() {
  type Row = Schemas['SupplierOut']
  const { t } = useWords()
  return (
    <MasterScreen<Row>
      eyebrow={t('nav.group.Master data')}
      title={t('nav.suppliers')}
      description={t('admin.supplier.description')}
      singular={t('admin.supplier.noun')}
      queryKey={['master', 'suppliers']}
      load={() => call(api.GET('/api/suppliers'))}
      columns={[
        { header: t('common.name'), cell: (r) => <strong>{r.name}</strong> },
        { header: t('admin.col.phone'), cell: (r) => dash(r.phone) },
        { header: t('admin.supplier.leadTime'), cell: (r) => t('admin.days', { n: r.lead_time_days }), num: true },
      ]}
      fields={[
        { name: 'name', label: t('common.name'), required: true },
        { name: 'phone', label: t('admin.col.phone'), kind: 'tel' },
        { name: 'lead_time_days', label: t('admin.supplier.leadTimeDays'), kind: 'number', required: true },
      ]}
      initial={(r) => ({ name: r?.name ?? '', phone: r?.phone ?? '', lead_time_days: String(r?.lead_time_days ?? 7) })}
      create={(v) => call(api.POST('/api/suppliers', { body: { name: v.name.trim(), phone: opt(v.phone), lead_time_days: num(v.lead_time_days) } }))}
      update={(r, v) =>
        call(api.PATCH('/api/suppliers/{item_id}', { params: { path: { item_id: r.id } }, body: { name: v.name.trim(), phone: opt(v.phone), lead_time_days: num(v.lead_time_days) } }))
      }
      empty={{ title: t('admin.supplier.emptyTitle'), description: t('admin.supplier.emptyDescription') }}
      alsoInvalidate={[['stock']]}
    />
  )
}

export function Buyers() {
  type Row = Schemas['BuyerOut']
  const { t } = useWords()
  const body = (v: Values) => ({ name: v.name.trim(), contact_name: opt(v.contact_name), phone: opt(v.phone), email: opt(v.email) })
  return (
    <MasterScreen<Row>
      eyebrow={t('nav.group.Master data')}
      title={t('nav.buyers')}
      description={t('admin.buyer.description')}
      singular={t('admin.buyer.noun')}
      queryKey={['master', 'buyers']}
      load={() => call(api.GET('/api/buyers'))}
      columns={[
        { header: t('common.name'), cell: (r) => <strong>{r.name}</strong> },
        { header: t('admin.buyer.contact'), cell: (r) => dash(r.contact_name) },
        { header: t('admin.col.phone'), cell: (r) => dash(r.phone) },
        { header: t('admin.col.email'), cell: (r) => dash(r.email) },
      ]}
      fields={[
        { name: 'name', label: t('common.name'), required: true },
        { name: 'contact_name', label: t('admin.buyer.contactPerson') },
        { name: 'phone', label: t('admin.col.phone'), kind: 'tel' },
        { name: 'email', label: t('admin.col.email'), kind: 'email' },
      ]}
      initial={(r) => ({ name: r?.name ?? '', contact_name: r?.contact_name ?? '', phone: r?.phone ?? '', email: r?.email ?? '' })}
      create={(v) => call(api.POST('/api/buyers', { body: body(v) }))}
      update={(r, v) => call(api.PATCH('/api/buyers/{item_id}', { params: { path: { item_id: r.id } }, body: body(v) }))}
      empty={{ title: t('admin.buyer.emptyTitle'), description: t('admin.buyer.emptyDescription') }}
    />
  )
}

export function YarnTypes() {
  type Row = Schemas['YarnTypeOut']
  const { t } = useWords()
  const body = (v: Values) => ({ code: v.code.trim(), name: v.name.trim(), colour: v.colour.trim(), reorder_level_kg: num(v.reorder_level_kg || '0') })
  return (
    <MasterScreen<Row>
      eyebrow={t('nav.group.Master data')}
      title={t('nav.yarnTypes')}
      description={t('admin.yarn.description')}
      singular={t('admin.yarn.noun')}
      queryKey={['master', 'yarn-types']}
      load={() => call(api.GET('/api/yarn-types'))}
      columns={[
        { header: t('admin.col.code'), cell: (r) => <span className="code-text">{r.code}</span> },
        { header: t('common.name'), cell: (r) => r.name },
        { header: t('admin.col.colour'), cell: (r) => r.colour },
        { header: t('admin.yarn.reorderAt'), cell: (r) => formatKg(r.reorder_level_kg), num: true },
      ]}
      fields={[
        { name: 'code', label: t('admin.col.code'), required: true },
        { name: 'name', label: t('common.name'), required: true },
        { name: 'colour', label: t('admin.col.colour'), required: true },
        { name: 'reorder_level_kg', label: t('admin.yarn.reorderLevel'), kind: 'number', hint: t('admin.yarn.reorderHint') },
      ]}
      initial={(r) => ({ code: r?.code ?? '', name: r?.name ?? '', colour: r?.colour ?? '', reorder_level_kg: String(r?.reorder_level_kg ?? 0) })}
      create={(v) => call(api.POST('/api/yarn-types', { body: body(v) }))}
      update={(r, v) => call(api.PATCH('/api/yarn-types/{item_id}', { params: { path: { item_id: r.id } }, body: body(v) }))}
      empty={{ title: t('admin.yarn.emptyTitle'), description: t('admin.yarn.emptyDescription') }}
      alsoInvalidate={[['stock'], ['master', 'fabric-types']]}
    />
  )
}

export function Machines() {
  type Row = Schemas['MachineOut']
  const { t, stageOptions, stageLabel, active } = useWords()
  const common = (v: Values) => ({
    code: v.code.trim(),
    name: v.name.trim(),
    rated_output_per_hour: num(v.rated_output_per_hour),
    running_cost_per_hour: num(v.running_cost_per_hour || '0'),
    active: v.active === 'true',
  })
  return (
    <MasterScreen<Row>
      eyebrow={t('nav.group.Master data')}
      title={t('nav.machines')}
      description={t('admin.machine.description')}
      singular={t('admin.machine.noun')}
      queryKey={['master', 'machines']}
      load={() => call(api.GET('/api/machines'))}
      columns={[
        { header: t('admin.col.code'), cell: (r) => <span className="code-text">{r.code}</span> },
        { header: t('common.name'), cell: (r) => r.name },
        { header: t('common.stage'), cell: (r) => stageLabel(r.stage) },
        { header: t('admin.machine.ratedOutput'), cell: (r) => t('admin.perHour', { n: r.rated_output_per_hour }), num: true },
        { header: t('admin.machine.runningCost'), cell: (r) => t('admin.perHour', { n: formatMoney(r.running_cost_per_hour) }), num: true },
        { header: t('qc.col.status'), cell: (r) => active(r.active) },
      ]}
      fields={[
        { name: 'code', label: t('admin.col.code'), required: true },
        { name: 'name', label: t('common.name'), required: true },
        { name: 'stage', label: t('common.stage'), kind: 'select', required: true, options: stageOptions, only: 'create', hint: t('admin.machine.stageHint') },
        { name: 'rated_output_per_hour', label: t('admin.machine.ratedPerHour'), kind: 'number', required: true, hint: t('admin.machine.ratedHint') },
        { name: 'running_cost_per_hour', label: t('admin.machine.costPerHour'), kind: 'number' },
        { name: 'active', label: t('admin.machine.inUse'), kind: 'checkbox' },
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
      empty={{ title: t('admin.machine.emptyTitle'), description: t('admin.machine.emptyDescription') }}
      alsoInvalidate={[['floor']]}
    />
  )
}

export function Shifts() {
  type Row = Schemas['ShiftOut']
  const { t } = useWords()
  return (
    <MasterScreen<Row>
      eyebrow={t('nav.group.Master data')}
      title={t('nav.shifts')}
      description={t('admin.shift.description')}
      singular={t('admin.shift.noun')}
      queryKey={['master', 'shifts']}
      load={() => call(api.GET('/api/shifts'))}
      columns={[
        { header: t('attendance.shift'), cell: (r) => <span className="code-text">{r.name}</span> },
        { header: t('admin.shift.starts'), cell: (r) => time(r.start_time) },
        { header: t('admin.shift.ends'), cell: (r) => time(r.end_time) },
      ]}
      fields={[
        { name: 'name', label: t('common.name'), required: true, only: 'create', hint: t('admin.shift.nameHint') },
        { name: 'start_time', label: t('admin.shift.startsAt'), kind: 'time', required: true },
        { name: 'end_time', label: t('admin.shift.endsAt'), kind: 'time', required: true },
      ]}
      initial={(r) => ({ name: r?.name ?? '', start_time: r ? time(r.start_time) : '', end_time: r ? time(r.end_time) : '' })}
      create={(v) => call(api.POST('/api/shifts', { body: { name: v.name.trim(), start_time: v.start_time, end_time: v.end_time } }))}
      update={(r, v) => call(api.PATCH('/api/shifts/{item_id}', { params: { path: { item_id: r.id } }, body: { start_time: v.start_time, end_time: v.end_time } }))}
      empty={{ title: t('admin.shift.emptyTitle'), description: t('admin.shift.emptyDescription') }}
    />
  )
}

export function Workers() {
  type Row = Schemas['WorkerOut']
  const me = useMe()
  const { t, workerRoleOptions, workerRoleLabel, active } = useWords()
  const common = (v: Values) => ({ name: v.name.trim(), role: v.role as Row['role'], daily_wage: num(v.daily_wage), active: v.active === 'true' })
  return (
    <MasterScreen<Row>
      eyebrow={t('attendance.eyebrow')}
      title={t('nav.workers')}
      description={t('admin.worker.description')}
      singular={t('admin.worker.noun')}
      queryKey={['master', 'workers']}
      load={() => call(api.GET('/api/workers'))}
      // supervisors and accountants can look; only the owner changes the payroll
      canEdit={me.data?.role === 'owner'}
      columns={[
        { header: t('admin.col.code'), cell: (r) => <span className="code-text">{r.code}</span> },
        { header: t('common.name'), cell: (r) => r.name },
        { header: t('admin.col.role'), cell: (r) => workerRoleLabel(r.role) },
        { header: t('wages.col.dailyWage'), cell: (r) => formatMoney(r.daily_wage), num: true },
        { header: t('qc.col.status'), cell: (r) => active(r.active) },
      ]}
      fields={[
        { name: 'code', label: t('admin.col.code'), required: true, only: 'create' },
        { name: 'name', label: t('common.name'), required: true },
        { name: 'role', label: t('admin.col.role'), kind: 'select', required: true, options: workerRoleOptions },
        { name: 'daily_wage', label: t('admin.worker.dailyWageRupees'), kind: 'number', required: true },
        { name: 'active', label: t('admin.worker.onPayroll'), kind: 'checkbox' },
      ]}
      initial={(r) => ({ code: r?.code ?? '', name: r?.name ?? '', role: r?.role ?? '', daily_wage: String(r?.daily_wage ?? ''), active: String(r?.active ?? true) })}
      create={(v) => call(api.POST('/api/workers', { body: { code: v.code.trim(), ...common(v) } }))}
      update={(r, v) => call(api.PATCH('/api/workers/{item_id}', { params: { path: { item_id: r.id } }, body: common(v) }))}
      empty={{ title: t('admin.worker.emptyTitle'), description: t('admin.worker.emptyDescription') }}
      alsoInvalidate={[['people']]}
      rowActions={(r) => <WorkerLoginCell worker={r} />}
    />
  )
}

export function Users() {
  type Row = Schemas['UserOut']
  const { t } = useWords()
  const workers = useQuery({ queryKey: ['master', 'workers'], queryFn: () => call(api.GET('/api/workers')) })
  const buyers = useQuery({ queryKey: ['master', 'buyers'], queryFn: () => call(api.GET('/api/buyers')) })
  const workerName = (id: number | null) => workers.data?.find((w) => w.id === id)?.name ?? (id ? `#${id}` : null)
  const buyerName = (id: number | null) => buyers.data?.find((b) => b.id === id)?.name ?? (id ? `#${id}` : null)
  const roleOptions = (Object.keys(ROLE_LABEL) as (keyof typeof ROLE_LABEL)[]).map((value) => ({ value, label: t(`role.${value}` as Key) }))
  return (
    <MasterScreen<Row>
      eyebrow={t('nav.group.Master data')}
      title={t('nav.users')}
      description={t('admin.user.description')}
      singular={t('admin.user.noun')}
      queryKey={['master', 'users']}
      load={() => call(api.GET('/api/users'))}
      columns={[
        { header: t('admin.col.username'), cell: (r) => <span className="code-text">{r.username}</span> },
        { header: t('admin.col.role'), cell: (r) => t(`role.${r.role}` as Key) },
        { header: t('admin.col.linked'), cell: (r) => dash(r.buyer_id ? buyerName(r.buyer_id) : workerName(r.worker_id)) },
      ]}
      fields={[
        { name: 'username', label: t('admin.col.username'), required: true, only: 'create' },
        { name: 'role', label: t('admin.col.role'), kind: 'select', required: true, options: roleOptions, only: 'create' },
        { name: 'password', label: t('login.password'), kind: 'password', required: true, only: 'create', hint: t('admin.user.passwordHint') },
        { name: 'new_password', label: t('admin.user.newPassword'), kind: 'password', only: 'edit', hint: t('admin.user.newPasswordHint') },
        { name: 'worker_id', label: t('admin.user.linkedWorker'), kind: 'select', options: (workers.data ?? []).map((w) => ({ value: String(w.id), label: `${w.name} (${w.code})` })) },
        { name: 'buyer_id', label: t('admin.user.linkedBuyer'), kind: 'select', only: 'create', options: (buyers.data ?? []).map((b) => ({ value: String(b.id), label: b.name })) },
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
      empty={{ title: t('admin.user.emptyTitle'), description: t('admin.user.emptyDescription') }}
    />
  )
}
