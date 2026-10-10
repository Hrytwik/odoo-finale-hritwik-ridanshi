import { useId, type ComponentProps, type ReactNode } from 'react'
import { cx } from '@/lib/cx'

export function Input({ className, ...props }: ComponentProps<'input'>) {
  return <input className={cx('input', className)} {...props} />
}

export function Select({ className, ...props }: ComponentProps<'select'>) {
  return <select className={cx('select', className)} {...props} />
}

export function Textarea({ className, ...props }: ComponentProps<'textarea'>) {
  return <textarea className={cx('textarea', className)} {...props} />
}

/** Props the field hands to its control so the label, hint and error are wired up for screen readers. */
export type ControlProps = {
  id: string
  'aria-invalid': boolean
  'aria-describedby': string | undefined
}

type FieldProps = {
  label: string
  error?: string
  hint?: string
  /** render the control, spreading the given props on it: `{(c) => <Input {...c} {...register('x')} />}` */
  children: (control: ControlProps) => ReactNode
}

export function Field({ label, error, hint, children }: FieldProps) {
  const id = useId()
  const hintId = `${id}-hint`
  const errorId = `${id}-error`
  const describedBy = [hint && hintId, error && errorId].filter(Boolean).join(' ') || undefined
  return (
    <div className="field">
      <label className="field-label" htmlFor={id}>
        {label}
      </label>
      {children({ id, 'aria-invalid': !!error, 'aria-describedby': describedBy })}
      {hint && (
        <p id={hintId} className="field-hint">
          {hint}
        </p>
      )}
      {error && (
        <p id={errorId} className="field-error">
          {error}
        </p>
      )}
    </div>
  )
}
