import type { ReactNode } from 'react'
import { Button } from '@/components/ui/Button'
import { Dialog } from '@/components/ui/Dialog'
import { Alert } from './Alert'
import { SubmitButton } from './SubmitButton'

/** A dialog for one action: explanation and fields, the server's error message, and a confirm and a cancel button. */
export function ActionDialog({
  open,
  onClose,
  title,
  confirmLabel,
  cancelLabel = 'Cancel',
  onConfirm,
  pending,
  error,
  danger,
  children,
}: {
  open: boolean
  onClose: () => void
  title: string
  confirmLabel: string
  cancelLabel?: string
  onConfirm: () => void
  pending: boolean
  error: string | null
  danger?: boolean
  children?: ReactNode
}) {
  return (
    <Dialog open={open} onClose={onClose} title={title}>
      <form
        className="stack"
        noValidate
        onSubmit={(e) => {
          e.preventDefault()
          onConfirm()
        }}
      >
        {children}
        {error && <Alert tone="error">{error}</Alert>}
        <div className="row">
          <SubmitButton pending={pending} variant={danger ? 'danger' : 'primary'}>
            {confirmLabel}
          </SubmitButton>
          <Button variant="secondary" onClick={onClose}>
            {cancelLabel}
          </Button>
        </div>
      </form>
    </Dialog>
  )
}
