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
import { ApiError, api, call, errorMessage, type components } from '@/lib/api'
import { useSubmitLock } from '@/lib/forms'
import { formatDateTime, formatMetres } from '@/lib/format'

type Dispatch = components['schemas']['DispatchOut']

export default function DispatchList() {
  const [creating, setCreating] = useState(false)
  const dispatches = useQuery({ queryKey: ['dispatches'], queryFn: () => call(api.GET('/api/dispatches')) })
  return (
    <>
      <PageHeader
        title="Dispatch"
        description="Trucks being loaded and sent. A roll can leave only once, and only to its own buyer."
        actions={
          <Button onClick={() => setCreating(true)}>
            <Plus size={16} aria-hidden /> New dispatch
          </Button>
        }
      />
      <QueryBoundary query={dispatches}>
        {(list) =>
          list.length === 0 ? (
            <EmptyState title="No dispatches yet" description="Create one when a truck arrives, then scan the rolls onto it." />
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
  // trucks still being loaded come first: that is where the clerk is working
  const sorted = [...list].sort((a, b) => Number(b.state === 'loading') - Number(a.state === 'loading') || b.created_at.localeCompare(a.created_at))
  return (
    <Table>
      <thead>
        <tr>
          <th>Dispatch</th>
          <th>Buyer</th>
          <th>Vehicle</th>
          <th className="num">Rolls</th>
          <th className="num">Metres</th>
          <th>State</th>
          <th>Invoice</th>
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
              {d.rolls.length} {d.rolls.length === 1 ? 'roll' : 'rolls'}
            </td>
            <td className="num">{formatMetres(d.total_metres)}</td>
            <td>{d.state === 'loading' ? <Badge tone="amber">Loading</Badge> : <Badge tone="green">Dispatched</Badge>}</td>
            <td>{d.invoice_no ? <Link to={`/invoices/${d.invoice_no}`}>{d.invoice_no}</Link> : <span className="muted">-</span>}</td>
          </tr>
        ))}
      </tbody>
    </Table>
  )
}

type Form = { buyer: string; vehicle: string; driver: string }

function NewDispatchDialog({ onClose }: { onClose: () => void }) {
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
      if (!form.buyer) next.buyer = 'Choose the buyer'
      if (!form.vehicle.trim()) next.vehicle = 'Enter the vehicle number'
      setErrors(next)
      setFormError(null)
      if (Object.keys(next).length) return
      try {
        const d = await call(
          api.POST('/api/dispatches', {
            body: { buyer_id: Number(form.buyer), vehicle_no: form.vehicle.trim(), ...(form.driver.trim() ? { driver_name: form.driver.trim() } : {}) },
          }),
        )
        toast.success(`${d.code} created`)
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
    <Dialog open onClose={onClose} title="New dispatch">
      <form
        className="stack"
        noValidate
        onSubmit={(e) => {
          e.preventDefault()
          void submit()
        }}
      >
        <Field label="Buyer" error={errors.buyer}>
          {(c) => (
            <Select {...c} value={form.buyer} onChange={(e) => set('buyer', e.target.value)}>
              <option value="">Select a buyer</option>
              {(buyers.data ?? []).map((b) => (
                <option key={b.id} value={b.id}>
                  {b.name}
                </option>
              ))}
            </Select>
          )}
        </Field>
        <Field label="Vehicle number" error={errors.vehicle}>
          {(c) => <Input {...c} autoCapitalize="characters" autoComplete="off" value={form.vehicle} onChange={(e) => set('vehicle', e.target.value)} />}
        </Field>
        <Field label="Driver (optional)" error={errors.driver}>
          {(c) => <Input {...c} autoComplete="off" value={form.driver} onChange={(e) => set('driver', e.target.value)} />}
        </Field>
        {formError && <Alert tone="error">{formError}</Alert>}
        <div className="row">
          <SubmitButton pending={pending}>Create dispatch</SubmitButton>
          <Button variant="secondary" onClick={onClose}>
            Cancel
          </Button>
        </div>
      </form>
    </Dialog>
  )
}
