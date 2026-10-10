import { zodResolver } from '@hookform/resolvers/zod'
import { useQueryClient } from '@tanstack/react-query'
import { useState } from 'react'
import { useForm } from 'react-hook-form'
import { toast } from 'sonner'
import { z } from 'zod'
import { ActionDialog } from '@/components/common/ActionDialog'
import { Field, Input } from '@/components/ui/Field'
import { applyServerErrors, useSubmitLock } from '@/lib/forms'
import { todayIso } from '@/lib/dates'
import { formatMoney } from '@/lib/format'

export type PaymentValues = { amount: number; date: string; reference?: string }

const schemaFor = (balance: number) =>
  z.object({
    amount: z
      .string()
      .trim()
      .min(1, 'Enter the amount')
      .refine((v) => Number.isFinite(Number(v)) && Number(v) > 0, 'Enter an amount above zero')
      .refine((v) => Number(v) <= balance + 0.005, `It cannot be more than the balance of ${formatMoney(balance)}`),
    date: z
      .string()
      .min(1, 'Choose the date')
      .refine((v) => v <= todayIso(), 'The date cannot be in the future'),
    reference: z.string().trim().max(60, 'Keep it under 60 characters').optional(),
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
  const form = useForm<Values>({
    resolver: zodResolver(schemaFor(balance)),
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
    <ActionDialog open onClose={onClose} title={title} confirmLabel="Record payment" onConfirm={() => void submit()} pending={pending} error={error}>
      <p className="muted text-sm">
        {subject}. Balance {formatMoney(balance)}.
      </p>
      <Field label="Amount (₹)" error={errors.amount?.message}>
        {(c) => <Input {...c} inputMode="decimal" autoComplete="off" autoFocus {...form.register('amount')} />}
      </Field>
      <Field label={dateLabel} error={errors.date?.message}>
        {(c) => <Input {...c} type="date" max={todayIso()} {...form.register('date')} />}
      </Field>
      <Field label="Reference (optional)" hint="A cheque, UTR or transfer number" error={errors.reference?.message}>
        {(c) => <Input {...c} autoComplete="off" {...form.register('reference')} />}
      </Field>
    </ActionDialog>
  )
}
