import { zodResolver } from '@hookform/resolvers/zod'
import { useState } from 'react'
import { useForm } from 'react-hook-form'
import { z } from 'zod'
import { Alert } from '@/components/common/Alert'
import { SubmitButton } from '@/components/common/SubmitButton'
import { Field, Input } from '@/components/ui/Field'
import { api, call, type components } from '@/lib/api'
import { applyServerErrors, useSubmitLock } from '@/lib/forms'

type Me = components['schemas']['Me']

const schema = z.object({
  username: z.string().trim().min(1, 'Enter your username').max(60),
  password: z.string().min(1, 'Enter your password').max(72, 'Password is too long'),
})
type Values = z.infer<typeof schema>

export function LoginForm({ onSuccess }: { onSuccess: (me: Me) => void }) {
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
      <Field label="Username" error={errors.username?.message}>
        {(c) => <Input {...c} autoComplete="username" autoCapitalize="none" autoFocus {...form.register('username')} />}
      </Field>
      <Field label="Password" error={errors.password?.message}>
        {(c) => <Input {...c} type="password" autoComplete="current-password" {...form.register('password')} />}
      </Field>
      {formError && <Alert tone="error">{formError}</Alert>}
      <SubmitButton pending={pending} block>
        Log in
      </SubmitButton>
    </form>
  )
}
