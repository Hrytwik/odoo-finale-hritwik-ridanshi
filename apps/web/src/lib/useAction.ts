import { useQueryClient } from '@tanstack/react-query'
import { useState } from 'react'
import { toast } from 'sonner'
import { errorMessage } from '@/lib/api'
import { useSubmitLock } from '@/lib/forms'

/**
 * Runs one server action from a dialog: locks against double taps, shows the server's message in the dialog if it fails,
 * and on success shows a toast, refetches the given query areas and closes the dialog.
 */
export function useAction(options: { invalidate: string[][]; onDone?: () => void }) {
  const queryClient = useQueryClient()
  const { run, pending } = useSubmitLock()
  const [error, setError] = useState<string | null>(null)

  /** `successMessage` may be a function of the server's reply, e.g. to name the roll that was just created. */
  const act = <T,>(fn: () => Promise<T>, successMessage: string | ((result: T) => string)) =>
    run(async () => {
      setError(null)
      try {
        const result = await fn()
        toast.success(typeof successMessage === 'function' ? successMessage(result) : successMessage)
        for (const queryKey of options.invalidate) void queryClient.invalidateQueries({ queryKey })
        options.onDone?.()
      } catch (err) {
        setError(errorMessage(err))
      }
    })

  return { act, pending, error, setError }
}
