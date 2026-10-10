import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { render } from '@testing-library/react'
import type { ReactElement } from 'react'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import { vi } from 'vitest'
import { api } from '@/lib/api/client'

type Handler = unknown | ((args: { params?: unknown; body?: unknown; query?: unknown }) => unknown)
type Table = Record<string, Handler>

const ok = (data: unknown, status = 200) => Promise.resolve({ data, response: new Response(null, { status }) })
const fail = (status: number, error: unknown) => Promise.resolve({ error, response: new Response(null, { status }) })

/** Replies as the API would: `error` objects with a `status` come back as error responses, everything else as data. */
export function reply(handler: Handler, opts?: { params?: unknown; body?: unknown; query?: unknown }) {
  const value = typeof handler === 'function' ? (handler as (a: typeof opts) => unknown)(opts) : handler
  if (value && typeof value === 'object' && 'status' in value && 'error' in value) {
    return fail((value as { status: number }).status, (value as { error: unknown }).error)
  }
  return ok(value)
}

/** Makes the mocked `api` answer by URL pattern, e.g. mockApi({ GET: { '/api/stock': [...] }, POST: { '/api/lots': {...} } }). */
export function mockApi(table: { GET?: Table; POST?: Table; PATCH?: Table; DELETE?: Table }) {
  for (const method of ['GET', 'POST', 'PATCH', 'DELETE'] as const) {
    const fn = (api as unknown as Record<string, ReturnType<typeof vi.fn>>)[method]
    fn.mockReset()
    fn.mockImplementation((url: string, init?: { params?: unknown; body?: unknown }) => {
      const handler = table[method]?.[url]
      if (handler === undefined) {
        return fail(404, { code: 'NOT_FOUND', message: `no mock for ${method} ${url}`, field: null, fields: null })
      }
      return reply(handler, { params: init?.params, body: init?.body })
    })
  }
}

export function renderPage(ui: ReactElement, opts: { route?: string; path?: string } = {}) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  const route = opts.route ?? '/'
  return render(
    <QueryClientProvider client={client}>
      <MemoryRouter initialEntries={[route]}>
        <Routes>
          <Route path={opts.path ?? '*'} element={ui} />
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>,
  )
}
