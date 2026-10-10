import type { ComponentProps } from 'react'
import { Button } from '@/components/ui/Button'

/** The submit button for every form. Pair it with useSubmitLock: `pending` disables it and shows a spinner. */
export function SubmitButton({ pending, children, disabled, ...props }: ComponentProps<typeof Button> & { pending: boolean }) {
  return (
    <Button type="submit" disabled={pending || disabled} aria-busy={pending} {...props}>
      {pending && <span className="spinner" aria-hidden />}
      {children}
    </Button>
  )
}
