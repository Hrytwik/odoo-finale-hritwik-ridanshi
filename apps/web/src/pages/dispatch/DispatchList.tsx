import { useQuery, useQueryClient } from '@tanstack/react-query'
import { Plus } from 'lucide-react'
import { useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { toast } from 'sonner'
import { Alert } from '@/components/common/Alert'
import { EmptyState } from '@/components/common/EmptyState'
import { PageHeader } from '@/components/common/PageHeader'
import { QueryBoundary } from '@/components/common/QueryBoundary'
import { SubmitButton } from '@/components/common/SubmitButton'
import { Reveal } from '@/components/motion/Reveal'
import { Badge } from '@/components/ui/Badge'
import { Button } from '@/components/ui/Button'
import { Dialog } from '@/components/ui/Dialog'
import { Field, Input, Select } from '@/components/ui/Field'
import { Table } from '@/components/ui/Table'
import { useI18n } from '@/i18n/I18nContext'
import { ApiError, api, call, errorMessage, type components } from '@/lib/api'
import { useSubmitLock } from '@/lib/forms'
import { formatDateTime, formatMetres } from '@/lib/format'

type Dispatch = components['schemas']['DispatchOut']

export default function DispatchList() {
  const { t } = useI18n()
  const [creating, setCreating] = useState(false)
  const dispatches = useQuery({ queryKey: ['dispatches'], queryFn: () => call(api.GET('/api/dispatches')) })
  return (
    <>
      <PageHeader
        title={t('nav.dispatch')}
        description={t('dispatch.description')}
        actions={
          <Button onClick={() => setCreating(true)}>
            <Plus size={16} aria-hidden /> {t('dispatch.new')}
          </Button>
        }
      />
      <QueryBoundary query={dispatches}>
        {(list) =>
          list.length === 0 ? (
            <EmptyState title={t('dispatch.emptyTitle')} description={t('dispatch.emptyDescription')} />
          ) : (
            <Reveal>
              <DispatchTable list={list} />
            </Reveal>
          )
        }
      </QueryBoundary>
      {creating && <NewDispatchDialog onClose={() => setCreating(false)} />}
    </>
  )
}

function DispatchTable({ list }: { list: Dispatch[] }) {
  const { t } = useI18n()
  // trucks still being loaded come first: that is where the clerk is working
  const sorted = [...list].sort((a, b) => Number(b.state === 'loading') - Number(a.state === 'loading') || b.created_at.localeCompare(a.created_at))
  return (
    <Table>
      <thead>
        <tr>
          <th>{t('dispatch.col.dispatch')}</th>
          <th>{t('qc.col.buyer')}</th>
          <th>{t('dispatch.col.vehicle')}</th>
          <th className="num">{t('dispatch.col.rolls')}</th>
          <th className="num">{t('dispatch.col.metres')}</th>
          <th>{t('dispatch.col.state')}</th>
          <th>{t('dispatch.col.invoice')}</th>
        </tr>
      </thead>
      <tbody>
        {sorted.map((d) => (
          <tr key={d.code}>
            <td>
              <Link to={`/dispatch/${d.code}`}>{d.code}</Link>
              <div className="muted text-sm">{formatDateTime(d.dispatched_at ?? d.created_at)}</div>
            </td>
            <td>{d.buyer.name}</td>
            <td>
              {d.vehicle_no}
              {d.driver_name && <div className="muted text-sm">{d.driver_name}</div>}
            </td>
            <td className="num">
              {t(d.rolls.length === 1 ? 'dispatch.rolls.one' : 'dispatch.rolls.many', { count: d.rolls.length })}
            </td>
            <td className="num">{formatMetres(d.total_metres)}</td>
            <td>{d.state === 'loading' ? <Badge tone="amber">{t('status.roll.loading')}</Badge> : <Badge tone="green">{t('status.roll.dispatched')}</Badge>}</td>
            <td>{d.invoice_no ? <Link to={`/invoices/${d.invoice_no}`}>{d.invoice_no}</Link> : <span className="muted">-</span>}</td>
          </tr>
        ))}
      </tbody>
    </Table>
  )
}

type Form = { buyer: string; vehicle: string; driver: string }

function NewDispatchDialog({ onClose }: { onClose: () => void }) {
  const { t } = useI18n()
  const navigate = useNavigate()
  const queryClient = useQueryClient()
  const { run, pending } = useSubmitLock()
  const buyers = useQuery({ queryKey: ['master', 'buyers'], queryFn: () => call(api.GET('/api/buyers')) })
  const [form, setForm] = useState<Form>({ buyer: '', vehicle: '', driver: '' })
  const [errors, setErrors] = useState<Partial<Record<keyof Form, string>>>({})
  const [formError, setFormError] = useState<string | null>(null)
  const set = (k: keyof Form, v: string) => setForm((f) => ({ ...f, [k]: v }))

  const submit = () =>
    run(async () => {
      const next: typeof errors = {}
      if (!form.buyer) next.buyer = t('dispatch.chooseBuyer')
      if (!form.vehicle.trim()) next.vehicle = t('dispatch.enterVehicle')
      setErrors(next)
      setFormError(null)
      if (Object.keys(next).length) return
      try {
        const d = await call(
          api.POST('/api/dispatches', {
            body: { buyer_id: Number(form.buyer), vehicle_no: form.vehicle.trim(), ...(form.driver.trim() ? { driver_name: form.driver.trim() } : {}) },
          }),
        )
        toast.success(t('dispatch.created', { code: d.code }))
        void queryClient.invalidateQueries({ queryKey: ['dispatches'] })
        navigate(`/dispatch/${d.code}`)
      } catch (err) {
        // a server field error goes under its own field; anything else is shown as a message
        const fieldFor: Record<string, keyof Form> = { vehicle_no: 'vehicle', buyer_id: 'buyer', driver_name: 'driver' }
        const placed: Partial<Record<keyof Form, string>> = {}
        if (err instanceof ApiError) {
          for (const [name, message] of Object.entries(err.fields ?? (err.field ? { [err.field]: err.body.message } : {}))) {
            if (fieldFor[name]) placed[fieldFor[name]] = message
          }
        }
        if (Object.keys(placed).length) setErrors((x) => ({ ...x, ...placed }))
        else setFormError(errorMessage(err))      }
    })

  return (
    <Dialog open onClose={onClose} title={t('dispatch.new')}>
      <form
        className="stack"
        noValidate
        onSubmit={(e) => {
          e.preventDefault()
          void submit()
        }}
      >
        <Field label={t('qc.col.buyer')} error={errors.buyer}>
          {(c) => (
            <Select {...c} value={form.buyer} onChange={(e) => set('buyer', e.target.value)}>
              <option value="">{t('dispatch.selectBuyer')}</option>
              {(buyers.data ?? []).map((b) => (
                <option key={b.id} value={b.id}>
                  {b.name}
                </option>
              ))}
            </Select>
          )}
        </Field>
        <Field label={t('dispatch.vehicleNo')} error={errors.vehicle}>
          {(c) => <Input {...c} autoCapitalize="characters" autoComplete="off" value={form.vehicle} onChange={(e) => set('vehicle', e.target.value)} />}
        </Field>
        <Field label={t('dispatch.driver')} error={errors.driver}>
          {(c) => <Input {...c} autoComplete="off" value={form.driver} onChange={(e) => set('driver', e.target.value)} />}
        </Field>
        {formError && <Alert tone="error">{formError}</Alert>}
        <div className="row">
          <SubmitButton pending={pending}>{t('dispatch.createButton')}</SubmitButton>
          <Button variant="secondary" onClick={onClose}>
            {t('dispatch.cancel')}
          </Button>
        </div>
      </form>
    </Dialog>
  )
}
