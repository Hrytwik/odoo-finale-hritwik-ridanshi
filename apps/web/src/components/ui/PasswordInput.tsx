import { Eye, EyeOff } from 'lucide-react'
import { useState, type ComponentProps, type KeyboardEvent } from 'react'
import { cx } from '@/lib/cx'

/** A password box with a button to show what was typed, and a quiet warning while Caps Lock is on. */
export function PasswordInput({ className, onKeyUp, ...props }: Omit<ComponentProps<'input'>, 'type'>) {
  const [shown, setShown] = useState(false)
  const [caps, setCaps] = useState(false)

  const watchCaps = (e: KeyboardEvent<HTMLInputElement>) => {
    setCaps(e.getModifierState?.('CapsLock') ?? false)
    onKeyUp?.(e)
  }

  return (
    <>
      <span className="password-field">
        <input {...props} className={cx('input', className)} type={shown ? 'text' : 'password'} onKeyUp={watchCaps} />
        <button type="button" className="password-toggle" aria-label={shown ? 'Hide characters' : 'Show characters'} aria-pressed={shown} onClick={() => setShown((s) => !s)}>
          {shown ? <EyeOff size={16} aria-hidden /> : <Eye size={16} aria-hidden />}
        </button>
      </span>
      {caps && (
        <p className="field-hint" role="status">
          Caps Lock is on
        </p>
      )}
    </>
  )
}
