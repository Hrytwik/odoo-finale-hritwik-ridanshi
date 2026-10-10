import { zodResolver } from '@hookform/resolvers/zod'
import { ArrowRight } from 'lucide-react'
import { useState } from 'react'
import { useForm } from 'react-hook-form'
import { z } from 'zod'
import { Alert } from '@/components/common/Alert'
import { SubmitButton } from '@/components/common/SubmitButton'
import { Field, Input } from '@/components/ui/Field'
import { PasswordInput } from '@/components/ui/PasswordInput'
import { api, call, type components } from '@/lib/api'
import { applyServerErrors, useSubmitLock } from '@/lib/forms'
import { passwordProblem } from '@/lib/passwordRules'

type Me = components['schemas']['Me']

const schema = z
  .object({
    email: z.string().trim().min(1, 'Enter your email').max(60, 'That email is too long').regex(/^[^@\s]+@[^@\s]+\.[^@\s]+$/, 'Enter a full email address, like name@company.com'),
    invite_code: z.string().trim().min(1, 'Enter the invite code the mill gave you').max(30),
    password: z.string().min(1, 'Choose a password').max(72, 'Password is too long'),
    again: z.string().min(1, 'Type the password again'),
  })
  .superRefine((v, ctx) => {
    const problem = v.password ? passwordProblem(v.password, v.email.split('@')[0] ?? '') : null
    if (problem) ctx.addIssue({ code: 'custom', path: ['password'], message: problem })
    if (v.again && v.password !== v.again) ctx.addIssue({ code: 'custom', path: ['again'], message: 'The two passwords are not the same' })
  })
type Values = z.infer<typeof schema>

/** A buyer makes their own login with the email the mill holds for them and the invite code the mill gave them. */
export function SignupForm({ onSuccess }: { onSuccess: (me: Me) => void }) {
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
      <Field label="Your email" error={errors.email?.message} hint="The email the mill has on record for your company.">
        {(c) => <Input {...c} type="email" autoComplete="email" autoCapitalize="none" autoFocus {...form.register('email')} />}
      </Field>
      <Field label="Invite code" error={errors.invite_code?.message} hint="Given to you by the mill, like ABCD-2FGH.">
        {(c) => <Input {...c} autoComplete="off" autoCapitalize="characters" {...form.register('invite_code')} />}
      </Field>
      <Field label="Choose a password" error={errors.password?.message} hint="At least 8 characters, with letters and a number.">
        {(c) => <PasswordInput {...c} autoComplete="new-password" {...form.register('password')} />}
      </Field>
      <Field label="Type it again" error={errors.again?.message}>
        {(c) => <PasswordInput {...c} autoComplete="new-password" {...form.register('again')} />}
      </Field>
      {formError && <Alert tone="error">{formError}</Alert>}
      <SubmitButton pending={pending} block>
        Create my account <ArrowRight size={16} aria-hidden />
      </SubmitButton>
    </form>
  )
}
