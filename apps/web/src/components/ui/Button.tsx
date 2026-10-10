import type { ComponentProps } from 'react'
import { cx } from '@/lib/cx'

export type ButtonVariant = 'primary' | 'secondary' | 'ghost' | 'danger'

type Props = ComponentProps<'button'> & {
  variant?: ButtonVariant
  /** full-width, e.g. for forms on a phone */
  block?: boolean
  /** square icon-only button; give it an aria-label */
  icon?: boolean
}

export function Button({ variant = 'primary', block, icon, className, type = 'button', ...props }: Props) {
  return (
    <button
      type={type}
      className={cx('btn', `btn-${variant}`, block && 'btn-block', icon && 'btn-icon', className)}
      {...props}
    />
  )
}
