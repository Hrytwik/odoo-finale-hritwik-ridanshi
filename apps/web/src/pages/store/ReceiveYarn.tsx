import { zodResolver } from '@hookform/resolvers/zod'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import { Camera, CheckCircle2 } from 'lucide-react'
import { useState } from 'react'
import { useForm } from 'react-hook-form'
import { Link } from 'react-router-dom'
import { toast } from 'sonner'
import { z } from 'zod'
import { Alert } from '@/components/common/Alert'
import { PageHeader } from '@/components/common/PageHeader'
import { QueryBoundary } from '@/components/common/QueryBoundary'
import { SubmitButton } from '@/components/common/SubmitButton'
import { Reveal } from '@/components/motion/Reveal'
import { Card } from '@/components/ui/Card'
import { Field, Input, Select } from '@/components/ui/Field'
import { api, call, type components } from '@/lib/api'
import { applyServerErrors, useSubmitLock } from '@/lib/forms'
import { formatKg } from '@/lib/format'

type Lot = components['schemas']['LotOut']

const schema = z.object({
  yarn_type_id: z.number({ error: 'Choose a yarn type' }),
  supplier_id: z.number({ error: 'Choose a supplier' }),
  qty_kg: z.number({ error: 'Enter the quantity in kg' }).positive('Must be more than 0').max(1_000_000, 'That is too much'),
  cost_per_kg: z.number({ error: 'Enter the cost per kg' }).positive('Must be more than 0').max(100_000_000, 'That is too much'),
  challan_no: z.string().trim().min(1, 'Enter the challan number').max(60, 'Too long'),
  intended_order_code: z.string().optional(),
})
type Values = z.infer<typeof schema>

/** The reference lists the gate form needs. Loaded together so the form never renders half-empty. */
function useGateOptions() {
  const yarnTypes = useQuery({ queryKey: ['master', 'yarn-types'], queryFn: () => call(api.GET('/api/yarn-types')) })
  const suppliers = useQuery({ queryKey: ['master', 'suppliers'], queryFn: () => call(api.GET('/api/suppliers')) })
  const orders = useQuery({ queryKey: ['orders'], queryFn: () => call(api.GET('/api/orders', { params: { query: { state: 'confirmed' } } })) })
  return { yarnTypes, suppliers, orders }
}

export default function ReceiveYarn() {
  const { yarnTypes, suppliers, orders } = useGateOptions()
  return (
    <>
      <PageHeader title="Receive yarn" description="Log a delivery at the gate. Stock updates for everyone straight away." />
      <QueryBoundary query={yarnTypes}>
        {(types) => (
          <QueryBoundary query={suppliers}>
            {(sups) => <ReceiveForm yarnTypes={types} suppliers={sups} orders={orders.data ?? []} />}
          </QueryBoundary>
        )}
      </QueryBoundary>
    </>
  )
}

type FormProps = {
  yarnTypes: components['schemas']['YarnTypeOut'][]
  suppliers: components['schemas']['SupplierOut'][]
  orders: components['schemas']['OrderOut'][]
}

function ReceiveForm({ yarnTypes, suppliers, orders }: FormProps) {
  const queryClient = useQueryClient()
  const form = useForm<Values>({ resolver: zodResolver(schema), defaultValues: { challan_no: '', intended_order_code: '' } })
  const { run, pending } = useSubmitLock()
  const [formError, setFormError] = useState<string | null>(null)
  const [photo, setPhoto] = useState<File | null>(null)
  const [last, setLast] = useState<Lot | null>(null)
  const { errors } = form.formState

  const onSubmit = form.handleSubmit((values) =>
    run(async () => {
      setFormError(null)
      try {
        let challan_photo_path: string | undefined
        if (photo) {
          const data = new FormData()
          data.append('file', photo)
          const uploaded = await call(
            api.POST('/api/uploads', { body: { file: photo as unknown as string }, bodySerializer: () => data }),
          )
          challan_photo_path = uploaded.path
        }
        const lot = await call(
          api.POST('/api/lots', {
            body: {
              yarn_type_id: values.yarn_type_id,
              supplier_id: values.supplier_id,
              qty_kg: values.qty_kg,
              cost_per_kg: values.cost_per_kg,
              challan_no: values.challan_no,
              ...(values.intended_order_code ? { intended_order_code: values.intended_order_code } : {}),
              ...(challan_photo_path ? { challan_photo_path } : {}),
            },
          }),
        )
        setLast(lot)
        toast.success(`Lot ${lot.lot_code} received`)
        form.reset({ challan_no: '', intended_order_code: '' })
        setPhoto(null)
        void queryClient.invalidateQueries({ queryKey: ['stock'] })
        void queryClient.invalidateQueries({ queryKey: ['lots'] })
      } catch (err) {
        setFormError(applyServerErrors(form, err))
      }
    }),
  )

  return (
    <div className="stack" style={{ maxWidth: 640 }}>
      {last && (
        <Reveal>
          <div className="alert alert-success" role="status">
            <CheckCircle2 size={18} aria-hidden />
            <span>
              Received <strong>{last.lot_code}</strong>: {formatKg(last.qty_received_kg)} of {last.yarn_type.name} from {last.supplier.name}.{' '}
              <Link to={`/store/lots/${last.lot_code}`}>View lot</Link>
            </span>
          </div>
        </Reveal>
      )}

      <Card>
        <form onSubmit={onSubmit} noValidate className="stack">
          <div className="grid-fields">
            <Field label="Yarn type" error={errors.yarn_type_id?.message}>
              {(c) => (
                <Select {...c} defaultValue="" {...form.register('yarn_type_id', { valueAsNumber: true })}>
                  <option value="" disabled>
                    Select a yarn type
                  </option>
                  {yarnTypes.map((t) => (
                    <option key={t.id} value={t.id}>
                      {t.name} ({t.colour})
                    </option>
                  ))}
                </Select>
              )}
            </Field>
            <Field label="Supplier" error={errors.supplier_id?.message}>
              {(c) => (
                <Select {...c} defaultValue="" {...form.register('supplier_id', { valueAsNumber: true })}>
                  <option value="" disabled>
                    Select a supplier
                  </option>
                  {suppliers.map((s) => (
                    <option key={s.id} value={s.id}>
                      {s.name}
                    </option>
                  ))}
                </Select>
              )}
            </Field>
            <Field label="Quantity (kg)" error={errors.qty_kg?.message}>
              {(c) => <Input {...c} type="number" inputMode="decimal" step="any" {...form.register('qty_kg', { valueAsNumber: true })} />}
            </Field>
            <Field label="Cost per kg (₹)" error={errors.cost_per_kg?.message}>
              {(c) => <Input {...c} type="number" inputMode="decimal" step="any" {...form.register('cost_per_kg', { valueAsNumber: true })} />}
            </Field>
            <Field label="Challan number" error={errors.challan_no?.message}>
              {(c) => <Input {...c} autoComplete="off" {...form.register('challan_no')} />}
            </Field>
            <Field label="For order (optional)" hint="Information only. It does not reserve the yarn.">
              {(c) => (
                <Select {...c} {...form.register('intended_order_code')}>
                  <option value="">Not for a particular order</option>
                  {orders.map((o) => (
                    <option key={o.code} value={o.code}>
                      {o.code} · {o.buyer.name}
                    </option>
                  ))}
                </Select>
              )}
            </Field>
          </div>

          <Field label="Challan photo (optional)" hint={photo ? photo.name : 'Take a photo of the paper challan'}>
            {(c) => (
              <label className="file-pick">
                <Camera size={18} aria-hidden />
                <span>{photo ? 'Change photo' : 'Take or choose a photo'}</span>
                <input {...c} type="file" accept="image/*" capture="environment" className="sr-only" onChange={(e) => setPhoto(e.target.files?.[0] ?? null)} />
              </label>
            )}
          </Field>

          {formError && <Alert tone="error">{formError}</Alert>}
          <SubmitButton pending={pending} block>
            Receive lot
          </SubmitButton>
        </form>
      </Card>
    </div>
  )
}
