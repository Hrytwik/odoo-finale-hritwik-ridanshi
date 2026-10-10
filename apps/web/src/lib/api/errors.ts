export type ErrorBody = {
  code: string
  message: string
  field: string | null
  fields: Record<string, string> | null
}

export class ApiError extends Error {
  status: number
  body: ErrorBody

  constructor(status: number, body: ErrorBody) {
    super(body.message)
    this.name = 'ApiError'
    this.status = status
    this.body = body
  }
  get code() {
    return this.body.code
  }
  get field() {
    return this.body.field
  }
  get fields() {
    return this.body.fields
  }
}

let onUnauthorized: (() => void) | null = null

export function setUnauthorizedHandler(fn: (() => void) | null) {
  onUnauthorized = fn
}

function isErrorBody(value: unknown): value is ErrorBody {
  return typeof value === 'object' && value !== null && 'code' in value && 'message' in value
}

function toErrorBody(error: unknown, status: number): ErrorBody {
  if (isErrorBody(error)) return { ...error, field: error.field ?? null, fields: error.fields ?? null }
  if (status >= 500) {
    return { code: 'SERVER_ERROR', message: 'Something went wrong on the server.', field: null, fields: null }
  }
  return { code: 'REQUEST_FAILED', message: 'The request failed.', field: null, fields: null }
}

export async function call<T>(
  request: Promise<{ data?: T; error?: unknown; response: Response }>,
): Promise<T> {
  let result: { data?: T; error?: unknown; response: Response }
  try {
    result = await request
  } catch {
    throw new ApiError(0, {
      code: 'NETWORK_ERROR',
      message: "Can't reach the server. Check the Wi-Fi and try again.",
      field: null,
      fields: null,
    })
  }
  const { data, error, response } = result
  if (response.ok) return data as T
  if (response.status === 401) onUnauthorized?.()
  throw new ApiError(response.status, toErrorBody(error, response.status))
}

export function errorMessage(err: unknown): string {
  return err instanceof ApiError ? err.body.message : 'Something went wrong.'
}
