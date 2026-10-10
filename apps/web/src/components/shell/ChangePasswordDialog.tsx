import { useState } from 'react'
import { toast } from 'sonner'
import { ActionDialog } from '@/components/common/ActionDialog'
import { Field } from '@/components/ui/Field'
import { PasswordInput } from '@/components/ui/PasswordInput'
import { ApiError, api, call, errorMessage } from '@/lib/api'
import { useSubmitLock } from '@/lib/forms'
import { passwordProblem } from '@/lib/passwordRules'

/** Change your own password. After it changes, any other device that was logged in is logged out. */
export function ChangePasswordDialog({ open, onClose, username }: { open: boolean; onClose: () => void; username: string }) {
  const { run, pending } = useSubmitLock()
  const [current, setCurrent] = useState('')
  const [next, setNext] = useState('')
  const [again, setAgain] = useState('')
  const [errors, setErrors] = useState<Record<string, string>>({})
  const [formError, setFormError] = useState<string | null>(null)

  const close = () => {
    setCurrent('')
    setNext('')
    setAgain('')
    setErrors({})
    setFormError(null)
    onClose()
  }

  const submit = () =>
    run(async () => {
      const found: Record<string, string> = {}
      if (!current) found.current_password = 'Enter your current password'
      const problem = passwordProblem(next, username)
      if (problem) found.new_password = problem
      else if (next === current) found.new_password = 'Choose a password different from the current one'
      if (next && again !== next) found.again = 'The two new passwords are not the same'
      setErrors(found)
      setFormError(null)
      if (Object.keys(found).length) return
      try {
        await call(api.POST('/api/auth/change-password', { body: { current_password: current, new_password: next } }))
        toast.success('Password changed. Other devices were logged out.')
        close()
      } catch (err) {
        const placed: Record<string, string> = {}
        if (err instanceof ApiError) {
          const known = new Set(['current_password', 'new_password'])
          for (const [name, message] of Object.entries(err.fields ?? (err.field ? { [err.field]: err.body.message } : {}))) if (known.has(name)) placed[name] = message
        }
        if (Object.keys(placed).length) setErrors(placed)
        else setFormError(errorMessage(err))
      }
    })

  return (
    <ActionDialog open={open} onClose={close} title="Change your password" confirmLabel="Change password" onConfirm={() => void submit()} pending={pending} error={formError}>
      <Field label="Current password" error={errors.current_password}>
        {(c) => <PasswordInput {...c} autoComplete="current-password" autoFocus value={current} onChange={(e) => setCurrent(e.target.value)} />}
      </Field>
      <Field label="New password" error={errors.new_password} hint="At least 8 characters, with letters and a number">
        {(c) => <PasswordInput {...c} autoComplete="new-password" value={next} onChange={(e) => setNext(e.target.value)} />}
      </Field>
      <Field label="New password again" error={errors.again}>
        {(c) => <PasswordInput {...c} autoComplete="new-password" value={again} onChange={(e) => setAgain(e.target.value)} />}
      </Field>
    </ActionDialog>
  )
}
