import { zodResolver } from '@hookform/resolvers/zod'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import { useMemo, useState } from 'react'
import { useForm } from 'react-hook-form'
import { useNavigate } from 'react-router-dom'
import { z } from 'zod'
import { Alert } from '@/components/common/Alert'
import { PageHeader } from '@/components/common/PageHeader'
import { QueryBoundary } from '@/components/common/QueryBoundary'
import { SubmitButton } from '@/components/common/SubmitButton'
import { Card } from '@/components/ui/Card'
import { Field, Input, Select } from '@/components/ui/Field'
import { useI18n } from '@/i18n/I18nContext'
import { api, call, type components } from '@/lib/api'
import { todayIso } from '@/lib/dates'
import { applyServerErrors, useSubmitLock } from '@/lib/forms'

type T = ReturnType<typeof useI18n>['t']
const makeSchema = (t: T) =>
  z.object({
    buyer_id: z.number({ error: t('orders.err.chooseBuyer') }),
    fabric_type_id: z.number({ error: t('orders.err.chooseFabric') }),
    colour: z.string().trim().min(1, t('orders.err.enterColour')).max(60, t('store.receive.tooLong')),
    qty_metres: z.number({ error: t('orders.err.enterQty') }).positive(t('store.receive.moreThanZero')).max(1_000_000, t('store.receive.tooMuch')),
    price_per_metre: z.number({ error: t('orders.err.enterPrice') }).positive(t('store.receive.moreThanZero')).max(100_000_000, t('store.receive.tooMuch')),
    deadline: z
      .string()
      .min(1, t('orders.err.chooseDeadline'))
      .refine((d) => d >= todayIso(), t('orders.err.deadlinePast')),
  })
type Values = z.infer<ReturnType<typeof makeSchema>>

export default function NewOrder() {
  const { t } = useI18n()
  const buyers = useQuery({ queryKey: ['master', 'buyers'], queryFn: () => call(api.GET('/api/buyers')) })
  const fabrics = useQuery({ queryKey: ['master', 'fabric-types'], queryFn: () => call(api.GET('/api/fabric-types')) })
  return (
    <>
      <PageHeader title={t('orders.new')} description={t('orders.newDescription')} />
      <QueryBoundary query={buyers}>
        {(b) => <QueryBoundary query={fabrics}>{(f) => <OrderForm buyers={b} fabrics={f} />}</QueryBoundary>}
      </QueryBoundary>
    </>
  )
}

function OrderForm({ buyers, fabrics }: { buyers: components['schemas']['BuyerOut'][]; fabrics: components['schemas']['FabricTypeOut'][] }) {
  const { t } = useI18n()
  const schema = useMemo(() => makeSchema(t), [t])
  const navigate = useNavigate()
  const queryClient = useQueryClient()
  const [today] = useState(todayIso)
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
            <Field label={t('qc.col.buyer')} error={errors.buyer_id?.message}>
              {(c) => (
                <Select {...c} defaultValue="" {...form.register('buyer_id', { valueAsNumber: true })}>
                  <option value="" disabled>
                    {t('dispatch.selectBuyer')}
                  </option>
                  {buyers.map((b) => (
                    <option key={b.id} value={b.id}>
                      {b.name}
                    </option>
                  ))}
                </Select>
              )}
            </Field>
            <Field label={t('qc.col.fabric')} error={errors.fabric_type_id?.message}>
              {(c) => (
                <Select {...c} defaultValue="" {...form.register('fabric_type_id', { valueAsNumber: true })}>
                  <option value="" disabled>
                    {t('orders.selectFabric')}
                  </option>
                  {fabrics.map((f) => (
                    <option key={f.id} value={f.id}>
                      {f.name}
                    </option>
                  ))}
                </Select>
              )}
            </Field>
            <Field label={t('orders.colour')} error={errors.colour?.message}>
              {(c) => <Input {...c} autoComplete="off" {...form.register('colour')} />}
            </Field>
            <Field label={t('orders.qtyMetres')} error={errors.qty_metres?.message}>
              {(c) => <Input {...c} type="number" inputMode="decimal" step="any" {...form.register('qty_metres', { valueAsNumber: true })} />}
            </Field>
            <Field label={t('orders.pricePerMetre')} error={errors.price_per_metre?.message}>
              {(c) => <Input {...c} type="number" inputMode="decimal" step="any" {...form.register('price_per_metre', { valueAsNumber: true })} />}
            </Field>
            <Field label={t('orders.col.deadline')} error={errors.deadline?.message}>
              {(c) => <Input {...c} type="date" min={today} {...form.register('deadline')} />}
            </Field>
          </div>
          {formError && <Alert tone="error">{formError}</Alert>}
          <SubmitButton pending={pending} block>
            {t('orders.create')}
          </SubmitButton>
        </form>
      </Card>
    </div>
  )
}
