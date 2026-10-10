import { zodResolver } from '@hookform/resolvers/zod'
import { ArrowRight } from 'lucide-react'
import { useMemo, useState } from 'react'
import { useForm } from 'react-hook-form'
import { z } from 'zod'
import { Alert } from '@/components/common/Alert'
import { SubmitButton } from '@/components/common/SubmitButton'
import { Field, Input } from '@/components/ui/Field'
import { PasswordInput } from '@/components/ui/PasswordInput'
import { useI18n } from '@/i18n/I18nContext'
import { api, call, type components } from '@/lib/api'
import { applyServerErrors, useSubmitLock } from '@/lib/forms'
import { passwordIssue } from '@/lib/passwordRules'

type Me = components['schemas']['Me']

type T = ReturnType<typeof useI18n>['t']
const makeSchema = (t: T) =>
  z
    .object({
      email: z.string().trim().min(1, t('signup.emailEnter')).max(60, t('signup.emailLong')).regex(/^[^@\s]+@[^@\s]+\.[^@\s]+$/, t('signup.emailBad')),
      invite_code: z.string().trim().min(1, t('signup.inviteEnter')).max(30),
      password: z.string().min(1, t('signup.choosePassword')).max(72, t('signup.passwordLong')),
      again: z.string().min(1, t('signup.againEnter')),
    })
    .superRefine((v, ctx) => {
      const problem = v.password ? passwordIssue(v.password, v.email.split('@')[0] ?? '') : null
      if (problem) ctx.addIssue({ code: 'custom', path: ['password'], message: t(problem.key, problem.vars) })
      if (v.again && v.password !== v.again) ctx.addIssue({ code: 'custom', path: ['again'], message: t('signup.mismatch') })
    })
type Values = z.infer<ReturnType<typeof makeSchema>>

/** A buyer makes their own login with the email the mill holds for them and the invite code the mill gave them. */
export function SignupForm({ onSuccess }: { onSuccess: (me: Me) => void }) {
  const { t } = useI18n()
  const schema = useMemo(() => makeSchema(t), [t])
  const form = useForm<Values>({ resolver: zodResolver(schema), defaultValues: { email: '', invite_code: '', password: '', again: '' } })
  const { run, pending } = useSubmitLock()
  const [formError, setFormError] = useState<string | null>(null)
  const { errors } = form.formState

  const onSubmit = form.handleSubmit((values) =>
    run(async () => {
      setFormError(null)
      try {
        onSuccess(await call(api.POST('/api/auth/signup', { body: { email: values.email, invite_code: values.invite_code, password: values.password } })))
      } catch (err) {
        setFormError(applyServerErrors(form, err))
      }
    }),
  )

  return (
    <form onSubmit={onSubmit} noValidate className="stack">
      <Field label={t('signup.email')} error={errors.email?.message} hint={t('signup.emailHint')}>
        {(c) => <Input {...c} type="email" autoComplete="email" autoCapitalize="none" autoFocus {...form.register('email')} />}
      </Field>
      <Field label={t('signup.invite')} error={errors.invite_code?.message} hint={t('signup.inviteHint')}>
        {(c) => <Input {...c} autoComplete="off" autoCapitalize="characters" {...form.register('invite_code')} />}
      </Field>
      <Field label={t('signup.choosePassword')} error={errors.password?.message} hint={t('signup.passwordHint')}>
        {(c) => <PasswordInput {...c} autoComplete="new-password" {...form.register('password')} />}
      </Field>
      <Field label={t('signup.again')} error={errors.again?.message}>
        {(c) => <PasswordInput {...c} autoComplete="new-password" {...form.register('again')} />}
      </Field>
      {formError && <Alert tone="error">{formError}</Alert>}
      <SubmitButton pending={pending} block>
        {t('signup.submit')} <ArrowRight size={16} aria-hidden />
      </SubmitButton>
    </form>
  )
}
