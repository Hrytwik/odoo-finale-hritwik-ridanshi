import { zodResolver } from '@hookform/resolvers/zod'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import { CheckCircle2 } from 'lucide-react'
import { useMemo, useState } from 'react'
import { useForm } from 'react-hook-form'
import { Link } from 'react-router-dom'
import { toast } from 'sonner'
import { z } from 'zod'
import { Alert } from '@/components/common/Alert'
import { PageHeader } from '@/components/common/PageHeader'
import { PhotoInput } from '@/components/common/PhotoInput'
import { QueryBoundary } from '@/components/common/QueryBoundary'
import { SubmitButton } from '@/components/common/SubmitButton'
import { Reveal } from '@/components/motion/Reveal'
import { Card } from '@/components/ui/Card'
import { Field, Input, Select } from '@/components/ui/Field'
import { useI18n } from '@/i18n/I18nContext'
import { api, call, type components } from '@/lib/api'
import { applyServerErrors, useSubmitLock } from '@/lib/forms'
import { formatKg } from '@/lib/format'

type Lot = components['schemas']['LotOut']

type T = ReturnType<typeof useI18n>['t']
const makeSchema = (t: T) =>
  z.object({
    yarn_type_id: z.number({ error: t('store.receive.chooseYarn') }),
    supplier_id: z.number({ error: t('store.receive.chooseSupplier') }),
    qty_kg: z.number({ error: t('store.receive.qtyEnter') }).positive(t('store.receive.moreThanZero')).max(1_000_000, t('store.receive.tooMuch')),
    cost_per_kg: z.number({ error: t('store.receive.costEnter') }).positive(t('store.receive.moreThanZero')).max(100_000_000, t('store.receive.tooMuch')),
    challan_no: z.string().trim().min(1, t('store.receive.challanEnter')).max(60, t('store.receive.tooLong')),
    intended_order_code: z.string().optional(),
  })
type Values = z.infer<ReturnType<typeof makeSchema>>

/** The reference lists the gate form needs. Loaded together so the form never renders half-empty. */
function useGateOptions() {
  const yarnTypes = useQuery({ queryKey: ['master', 'yarn-types'], queryFn: () => call(api.GET('/api/yarn-types')) })
  const suppliers = useQuery({ queryKey: ['master', 'suppliers'], queryFn: () => call(api.GET('/api/suppliers')) })
  const orders = useQuery({ queryKey: ['orders'], queryFn: () => call(api.GET('/api/orders', { params: { query: { state: 'confirmed' } } })) })
  return { yarnTypes, suppliers, orders }
}

export default function ReceiveYarn() {
  const { t } = useI18n()
  const { yarnTypes, suppliers, orders } = useGateOptions()
  return (
    <>
      <PageHeader title={t('nav.receive')} description={t('store.receive.description')} />
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
  const { t } = useI18n()
  const schema = useMemo(() => makeSchema(t), [t])
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
        toast.success(t('store.receive.toast', { code: lot.lot_code }))
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
              {t('store.receive.banner', { code: last.lot_code, qty: formatKg(last.qty_received_kg), yarn: last.yarn_type.name, supplier: last.supplier.name })}{' '}
              <Link to={`/store/lots/${last.lot_code}`}>{t('store.receive.viewLot')}</Link>
            </span>
          </div>
        </Reveal>
      )}

      <Card>
        <form onSubmit={onSubmit} noValidate className="stack">
          <div className="grid-fields">
            <Field label={t('store.receive.yarnType')} error={errors.yarn_type_id?.message}>
              {(c) => (
                <Select {...c} defaultValue="" {...form.register('yarn_type_id', { valueAsNumber: true })}>
                  <option value="" disabled>
                    {t('store.receive.selectYarn')}
                  </option>
                  {yarnTypes.map((t) => (
                    <option key={t.id} value={t.id}>
                      {t.name} ({t.colour})
                    </option>
                  ))}
                </Select>
              )}
            </Field>
            <Field label={t('store.receive.supplier')} error={errors.supplier_id?.message}>
              {(c) => (
                <Select {...c} defaultValue="" {...form.register('supplier_id', { valueAsNumber: true })}>
                  <option value="" disabled>
                    {t('store.receive.selectSupplier')}
                  </option>
                  {suppliers.map((s) => (
                    <option key={s.id} value={s.id}>
                      {s.name}
                    </option>
                  ))}
                </Select>
              )}
            </Field>
            <Field label={t('store.receive.qty')} error={errors.qty_kg?.message}>
              {(c) => <Input {...c} type="number" inputMode="decimal" step="any" {...form.register('qty_kg', { valueAsNumber: true })} />}
            </Field>
            <Field label={t('store.receive.cost')} error={errors.cost_per_kg?.message}>
              {(c) => <Input {...c} type="number" inputMode="decimal" step="any" {...form.register('cost_per_kg', { valueAsNumber: true })} />}
            </Field>
            <Field label={t('store.receive.challan')} error={errors.challan_no?.message}>
              {(c) => <Input {...c} autoComplete="off" {...form.register('challan_no')} />}
            </Field>
            <Field label={t('store.receive.forOrder')} hint={t('store.receive.forOrderHint')}>
              {(c) => (
                <Select {...c} {...form.register('intended_order_code')}>
                  <option value="">{t('store.receive.noOrder')}</option>
                  {orders.map((o) => (
                    <option key={o.code} value={o.code}>
                      {o.code} · {o.buyer.name}
                    </option>
                  ))}
                </Select>
              )}
            </Field>
          </div>

          <Field label={t('store.receive.photo')} hint={photo ? photo.name : t('store.receive.photoHint')}>
            {(c) => <PhotoInput {...c} onFile={setPhoto} />}
          </Field>

          {formError && <Alert tone="error">{formError}</Alert>}
          <SubmitButton pending={pending} block>
            {t('store.receive.submit')}
          </SubmitButton>
        </form>
      </Card>
    </div>
  )
}
