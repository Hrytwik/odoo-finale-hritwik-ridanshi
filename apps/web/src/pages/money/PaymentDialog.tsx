import { zodResolver } from '@hookform/resolvers/zod'
import { useQueryClient } from '@tanstack/react-query'
import { useState } from 'react'
import { useForm } from 'react-hook-form'
import { toast } from 'sonner'
import { z } from 'zod'
import { ActionDialog } from '@/components/common/ActionDialog'
import { Field, Input } from '@/components/ui/Field'
import { useI18n } from '@/i18n/I18nContext'
import { applyServerErrors, useSubmitLock } from '@/lib/forms'
import { todayIso } from '@/lib/dates'
import { formatMoney } from '@/lib/format'

export type PaymentValues = { amount: number; date: string; reference?: string }

type T = ReturnType<typeof useI18n>['t']
const schemaFor = (balance: number, t: T) =>
  z.object({
    amount: z
      .string()
      .trim()
      .min(1, t('money.enterAmount'))
      .refine((v) => Number.isFinite(Number(v)) && Number(v) > 0, t('money.amountAboveZero'))
      .refine((v) => Number(v) <= balance + 0.005, t('money.amountTooMuch', { balance: formatMoney(balance) })),
    date: z
      .string()
      .min(1, t('money.chooseDate'))
      .refine((v) => v <= todayIso(), t('money.dateFuture')),
    reference: z.string().trim().max(60, t('money.referenceLong')).optional(),
  })
type Values = z.infer<ReturnType<typeof schemaFor>>

/** Records one payment against an invoice or a bill. The amount starts as the full balance, the usual case. */
export function PaymentDialog({
  title,
  subject,
  balance,
  dateLabel,
  invalidate,
  send,
  successMessage,
  onClose,
}: {
  title: string
  /** what is being paid, e.g. "INV-0007 · Sharma Fabrics" */
  subject: string
  balance: number
  dateLabel: string
  invalidate: string[][]
  send: (values: PaymentValues) => Promise<unknown>
  successMessage: (values: PaymentValues) => string
  onClose: () => void
}) {
  const { t } = useI18n()
  const form = useForm<Values>({
    resolver: zodResolver(schemaFor(balance, t)),
    defaultValues: { amount: String(Math.round(balance * 100) / 100), date: todayIso(), reference: '' },
  })
  const queryClient = useQueryClient()
  const { run, pending } = useSubmitLock()
  const [error, setError] = useState<string | null>(null)
  const { errors } = form.formState

  const submit = form.handleSubmit((v) => {
    const values: PaymentValues = { amount: Number(v.amount), date: v.date, ...(v.reference ? { reference: v.reference } : {}) }
    return run(async () => {
      setError(null)
      try {
        await send(values)
        toast.success(successMessage(values))
        for (const queryKey of invalidate) void queryClient.invalidateQueries({ queryKey })
        onClose()
      } catch (err) {
        // a server message about one field goes under that field; anything else is shown in the dialog
        setError(applyServerErrors(form, err))
      }
    })
  })

  return (
    <ActionDialog open onClose={onClose} title={title} confirmLabel={t('money.recordPayment')} onConfirm={() => void submit()} pending={pending} error={error}>
      <p className="muted text-sm">
        {t('money.subject', { subject, balance: formatMoney(balance) })}
      </p>
      <Field label={t('money.amountRupees')} error={errors.amount?.message}>
        {(c) => <Input {...c} inputMode="decimal" autoComplete="off" autoFocus {...form.register('amount')} />}
      </Field>
      <Field label={dateLabel} error={errors.date?.message}>
        {(c) => <Input {...c} type="date" max={todayIso()} {...form.register('date')} />}
      </Field>
      <Field label={t('money.reference')} hint={t('money.referenceHint')} error={errors.reference?.message}>
        {(c) => <Input {...c} autoComplete="off" {...form.register('reference')} />}
      </Field>
    </ActionDialog>
  )
}
