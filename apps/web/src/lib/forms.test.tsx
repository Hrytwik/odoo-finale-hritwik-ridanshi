import { act, renderHook } from '@testing-library/react'
import { useForm } from 'react-hook-form'
import { describe, expect, it, vi } from 'vitest'
import { ApiError } from './api/errors'
import { applyServerErrors, useSubmitLock } from './forms'

describe('useSubmitLock', () => {
  it('runs the action once even when triggered twice at the same moment', async () => {
    let release!: () => void
    const action = vi.fn(() => new Promise<string>((r) => (release = () => r('done'))))
    const { result } = renderHook(() => useSubmitLock())
    let first!: Promise<string | undefined>
    let second!: Promise<string | undefined>
    act(() => {
      first = result.current.run(action)
      second = result.current.run(action)
    })
    expect(action).toHaveBeenCalledTimes(1)
    await expect(second).resolves.toBeUndefined()
    await act(async () => release())
    await expect(first).resolves.toBe('done')
  })

  it('allows another submit after the first finishes', async () => {
    const action = vi.fn(async () => 'ok')
    const { result } = renderHook(() => useSubmitLock())
    await act(() => result.current.run(action))
    await act(() => result.current.run(action))
    expect(action).toHaveBeenCalledTimes(2)
  })

  it('releases the lock when the action throws', async () => {
    const { result } = renderHook(() => useSubmitLock())
    await act(() =>
      result.current
        .run(async () => {
          throw new Error('boom')
        })
        .catch(() => undefined),
    )
    expect(result.current.pending).toBe(false)
    const action = vi.fn(async () => 1)
    await act(() => result.current.run(action))
    expect(action).toHaveBeenCalledOnce()
  })
})

describe('applyServerErrors', () => {
  const setup = () => renderHook(() => useForm({ defaultValues: { challan_no: '', qty_kg: 0 } })).result

  it('places every server field error on its field', () => {
    const form = setup()
    const err = new ApiError(422, {
      code: 'VALIDATION_ERROR',
      message: 'x',
      field: 'challan_no',
      fields: { challan_no: 'Required', qty_kg: 'Must be more than 0' },
    })
    let formMessage: string | null = 'unset'
    act(() => {
      formMessage = applyServerErrors(form.current, err)
    })
    expect(formMessage).toBeNull()
    expect(form.current.getFieldState('challan_no').error?.message).toBe('Required')
    expect(form.current.getFieldState('qty_kg').error?.message).toBe('Must be more than 0')
  })

  it('uses `field` when `fields` is absent', () => {
    const form = setup()
    const err = new ApiError(409, {
      code: 'DUPLICATE_CHALLAN',
      message: 'Already entered',
      field: 'challan_no',
      fields: null,
    })
    act(() => {
      applyServerErrors(form.current, err)
    })
    expect(form.current.getFieldState('challan_no').error?.message).toBe('Already entered')
  })

  it('returns a form-level message when the field is not on the form', () => {
    const form = setup()
    const err = new ApiError(409, { code: 'LOT_BLOCKED', message: 'Lot is blocked', field: 'lot_code', fields: null })
    let formMessage: string | null = null
    act(() => {
      formMessage = applyServerErrors(form.current, err)
    })
    expect(formMessage).toBe('Lot is blocked')
  })

  it('handles non-API errors', () => {
    const form = setup()
    expect(applyServerErrors(form.current, new Error('x'))).toBe('Something went wrong.')
  })
})
