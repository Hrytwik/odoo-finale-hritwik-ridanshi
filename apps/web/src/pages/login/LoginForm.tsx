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

type Me = components['schemas']['Me']

const makeSchema = (t: ReturnType<typeof useI18n>['t']) =>
  z.object({
    username: z.string().trim().min(1, t('login.enterUsername')).max(60),
    password: z.string().min(1, t('login.enterPassword')).max(72, 'Password is too long'),
  })
type Values = z.infer<ReturnType<typeof makeSchema>>

export function LoginForm({ onSuccess }: { onSuccess: (me: Me) => void }) {
  const { t } = useI18n()
  const schema = useMemo(() => makeSchema(t), [t])
  const form = useForm<Values>({ resolver: zodResolver(schema), defaultValues: { username: '', password: '' } })
  const { run, pending } = useSubmitLock()
  const [formError, setFormError] = useState<string | null>(null)
  const { errors } = form.formState

  const onSubmit = form.handleSubmit((values) =>
    run(async () => {
      setFormError(null)
      try {
        onSuccess(await call(api.POST('/api/auth/login', { body: values })))
      } catch (err) {
        setFormError(applyServerErrors(form, err))
      }
    }),
  )

  return (
    <form onSubmit={onSubmit} noValidate className="stack">
      <Field label={t('login.username')} error={errors.username?.message}>
        {(c) => <Input {...c} autoComplete="username" autoCapitalize="none" autoFocus {...form.register('username')} />}
      </Field>
      <Field label={t('login.password')} error={errors.password?.message}>
        {(c) => <PasswordInput {...c} autoComplete="current-password" {...form.register('password')} />}
      </Field>
      {formError && <Alert tone="error">{formError}</Alert>}
      <SubmitButton pending={pending} block>
        {t('login.submit')} <ArrowRight size={16} aria-hidden />
      </SubmitButton>
    </form>
  )
}
