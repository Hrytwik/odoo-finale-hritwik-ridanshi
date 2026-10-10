import { useCallback, useRef, useState } from 'react'
import type { FieldValues, Path, UseFormReturn } from 'react-hook-form'
import { ApiError } from './api/errors'

/** Runs an async action at most once at a time. A second call while the first is running returns undefined. */
export function useSubmitLock() {
  const busy = useRef(false)
  const [pending, setPending] = useState(false)

  const run = useCallback(async <T,>(fn: () => Promise<T>): Promise<T | undefined> => {
    if (busy.current) return undefined
    busy.current = true
    setPending(true)
    try {
      return await fn()
    } finally {
      busy.current = false
      setPending(false)
    }
  }, [])

  return { run, pending }
}

/** Puts server field errors on matching form fields. Returns a form-level message if nothing could be placed. */
export function applyServerErrors<T extends FieldValues>(form: UseFormReturn<T>, err: unknown): string | null {
  if (!(err instanceof ApiError)) return 'Something went wrong.'
  const fields = err.fields ?? (err.field ? { [err.field]: err.body.message } : {})
  const known = form.getValues() as Record<string, unknown>
  let placed = false
  for (const [name, message] of Object.entries(fields)) {
    if (name in known) {
      form.setError(name as Path<T>, { type: 'server', message })
      placed = true
    }
  }
  return placed ? null : err.body.message
}
