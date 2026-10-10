import { zodResolver } from '@hookform/resolvers/zod'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import { useState } from 'react'
import { useForm } from 'react-hook-form'
import { useNavigate } from 'react-router-dom'
import { z } from 'zod'
import { Alert } from '@/components/common/Alert'
import { PageHeader } from '@/components/common/PageHeader'
import { QueryBoundary } from '@/components/common/QueryBoundary'
import { SubmitButton } from '@/components/common/SubmitButton'
import { Card } from '@/components/ui/Card'
import { Field, Input, Select } from '@/components/ui/Field'
import { api, call, type components } from '@/lib/api'
import { applyServerErrors, useSubmitLock } from '@/lib/forms'

/** Today as YYYY-MM-DD in the browser's own calendar, for the "not in the past" rule. */
function todayIso() {
  const d = new Date()
  const pad = (n: number) => String(n).padStart(2, '0')
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}`
}

const schema = z.object({
  buyer_id: z.number({ error: 'Choose a buyer' }),
  fabric_type_id: z.number({ error: 'Choose a fabric' }),
  colour: z.string().trim().min(1, 'Enter the colour').max(60, 'Too long'),
  qty_metres: z.number({ error: 'Enter the quantity in metres' }).positive('Must be more than 0').max(1_000_000, 'That is too much'),
  price_per_metre: z.number({ error: 'Enter the price per metre' }).positive('Must be more than 0').max(100_000_000, 'That is too much'),
  deadline: z
    .string()
    .min(1, 'Choose a deadline')
    .refine((d) => d >= todayIso(), 'The deadline cannot be in the past'),
})
type Values = z.infer<typeof schema>

export default function NewOrder() {
  const buyers = useQuery({ queryKey: ['master', 'buyers'], queryFn: () => call(api.GET('/api/buyers')) })
  const fabrics = useQuery({ queryKey: ['master', 'fabric-types'], queryFn: () => call(api.GET('/api/fabric-types')) })
  return (
    <>
      <PageHeader title="New order" description="Creates a draft. Confirm it from the order page when the buyer agrees." />
      <QueryBoundary query={buyers}>
        {(b) => <QueryBoundary query={fabrics}>{(f) => <OrderForm buyers={b} fabrics={f} />}</QueryBoundary>}
      </QueryBoundary>
    </>
  )
}

function OrderForm({ buyers, fabrics }: { buyers: components['schemas']['BuyerOut'][]; fabrics: components['schemas']['FabricTypeOut'][] }) {
  const navigate = useNavigate()
  const queryClient = useQueryClient()
  const form = useForm<Values>({ resolver: zodResolver(schema), defaultValues: { colour: '', deadline: '' } })
  const { run, pending } = useSubmitLock()
  const [formError, setFormError] = useState<string | null>(null)
  const { errors } = form.formState

  const onSubmit = form.handleSubmit((values) =>
    run(async () => {
      setFormError(null)
      try {
        const order = await call(api.POST('/api/orders', { body: values }))
        void queryClient.invalidateQueries({ queryKey: ['orders'] })
        navigate(`/orders/${order.code}`)
      } catch (err) {
        setFormError(applyServerErrors(form, err))
      }
    }),
  )

  return (
    <div style={{ maxWidth: 640 }}>
      <Card>
        <form onSubmit={onSubmit} noValidate className="stack">
          <div className="grid-fields">
            <Field label="Buyer" error={errors.buyer_id?.message}>
              {(c) => (
                <Select {...c} defaultValue="" {...form.register('buyer_id', { valueAsNumber: true })}>
                  <option value="" disabled>
                    Select a buyer
                  </option>
                  {buyers.map((b) => (
                    <option key={b.id} value={b.id}>
                      {b.name}
                    </option>
                  ))}
                </Select>
              )}
            </Field>
            <Field label="Fabric" error={errors.fabric_type_id?.message}>
              {(c) => (
                <Select {...c} defaultValue="" {...form.register('fabric_type_id', { valueAsNumber: true })}>
                  <option value="" disabled>
                    Select a fabric
                  </option>
                  {fabrics.map((f) => (
                    <option key={f.id} value={f.id}>
                      {f.name}
                    </option>
                  ))}
                </Select>
              )}
            </Field>
            <Field label="Colour" error={errors.colour?.message}>
              {(c) => <Input {...c} autoComplete="off" {...form.register('colour')} />}
            </Field>
            <Field label="Quantity (metres)" error={errors.qty_metres?.message}>
              {(c) => <Input {...c} type="number" inputMode="decimal" step="any" {...form.register('qty_metres', { valueAsNumber: true })} />}
            </Field>
            <Field label="Price per metre (₹)" error={errors.price_per_metre?.message}>
              {(c) => <Input {...c} type="number" inputMode="decimal" step="any" {...form.register('price_per_metre', { valueAsNumber: true })} />}
            </Field>
            <Field label="Deadline" error={errors.deadline?.message}>
              {(c) => <Input {...c} type="date" min={todayIso()} {...form.register('deadline')} />}
            </Field>
          </div>
          {formError && <Alert tone="error">{formError}</Alert>}
          <SubmitButton pending={pending} block>
            Create order
          </SubmitButton>
        </form>
      </Card>
    </div>
  )
}
