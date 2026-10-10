import { afterEach, describe, expect, it, vi } from 'vitest'
import { ApiError, call, errorMessage, setUnauthorizedHandler } from './errors'

const res = (status: number) => new Response(null, { status })

async function failure(promise: Promise<unknown>): Promise<ApiError> {
  try {
    await promise
  } catch (e) {
    return e as ApiError
  }
  throw new Error('expected the call to fail')
}

afterEach(() => setUnauthorizedHandler(null))

describe('call', () => {
  it('returns data on success', async () => {
    await expect(call(Promise.resolve({ data: { ok: 1 }, response: res(200) }))).resolves.toEqual({ ok: 1 })
  })

  it('returns undefined for 204', async () => {
    await expect(call(Promise.resolve({ response: res(204) }))).resolves.toBeUndefined()
  })

  it('turns the standard error body into ApiError', async () => {
    const error = { code: 'DUPLICATE_CHALLAN', message: 'Already entered', field: 'challan_no', fields: null }
    const err = await failure(call(Promise.resolve({ error, response: res(409) })))
    expect(err).toBeInstanceOf(ApiError)
    expect(err.status).toBe(409)
    expect(err.code).toBe('DUPLICATE_CHALLAN')
    expect(err.field).toBe('challan_no')
  })

  it('maps a network failure to NETWORK_ERROR', async () => {
    const err = await failure(call(Promise.reject(new TypeError('Failed to fetch'))))
    expect(err.code).toBe('NETWORK_ERROR')
    expect(err.status).toBe(0)
    expect(errorMessage(err)).toMatch(/reach the server/i)
  })

  it('maps a non-JSON 500 to SERVER_ERROR', async () => {
    const err = await failure(call(Promise.resolve({ error: 'Internal Server Error', response: res(500) })))
    expect(err.code).toBe('SERVER_ERROR')
  })

  it('calls the unauthorized handler on 401', async () => {
    const handler = vi.fn()
    setUnauthorizedHandler(handler)
    const error = { code: 'NOT_AUTHENTICATED', message: 'Please log in', field: null, fields: null }
    await call(Promise.resolve({ error, response: res(401) })).catch(() => undefined)
    expect(handler).toHaveBeenCalledOnce()
  })

  it('errorMessage falls back for unknown errors', () => {
    expect(errorMessage(new Error('x'))).toBe('Something went wrong.')
  })
})
