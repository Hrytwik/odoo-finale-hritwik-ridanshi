import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { RouterProvider, createMemoryRouter } from 'react-router-dom'
import { beforeEach, describe, expect, it, vi } from 'vitest'

vi.mock('@/lib/api/client', () => ({ api: { GET: vi.fn(), POST: vi.fn() } }))
vi.mock('@/lib/live', () => ({ useLiveEvents: vi.fn() }))
import { api } from '@/lib/api/client'
import { routeObjects } from '@/router'

type Role = 'owner' | 'accountant' | 'store' | 'supervisor' | 'qc' | 'dispatch' | 'buyer'
const meFor = (role: Role) => ({ id: 3, username: role, role, display_name: 'Arjun Rao', worker_id: null, buyer_id: null })
const reply = (status: number, body?: unknown) =>
  Promise.resolve(status < 400 ? { data: body, response: new Response(null, { status }) } : { error: body, response: new Response(null, { status }) })

const ROLL = { id: 142, code: 'R-0142', order_code: 'ORD-0012', buyer_name: 'Sharma Fabrics', fabric: 'Poplin 58in', colour: 'navy', metres: 110, status: 'in_store', created_at: '2026-10-10T10:00:00Z' }
const PASSPORT = { roll: ROLL, order_code: 'ORD-0012', buyer_name: 'Sharma Fabrics', deadline: '2026-10-20', yarn_lots: [], runs: [], inspections: [], cost: null, dispatch: null }

function setup(role: Role, path: string, opts: { demo?: boolean; meStatus?: number } = {}) {
  vi.mocked(api.GET).mockImplementation(((url: string) => {
    if (url === '/api/auth/me') return opts.meStatus && opts.meStatus >= 400
      ? reply(opts.meStatus, { code: 'NOT_AUTHENTICATED', message: 'Please log in', field: null, fields: null })
      : reply(200, meFor(role))
    if (url === '/api/health') return reply(200, { status: 'ok', demo_data: !!opts.demo })
    if (url === '/api/rolls/{roll_code}/passport') return reply(200, PASSPORT)
    return reply(404, { code: 'NOT_FOUND', message: 'nope', field: null, fields: null })
  }) as never)
  const router = createMemoryRouter(routeObjects, { initialEntries: [path] })
  render(
    <QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}>
      <RouterProvider router={router} />
    </QueryClientProvider>,
  )
  return router
}

beforeEach(() => {
  vi.mocked(api.GET).mockReset()
  vi.mocked(api.POST).mockReset()
})

describe('session gate and home redirect', () => {
  it('sends a supervisor from / to the floor board', async () => {
    const router = setup('supervisor', '/')
    expect(await screen.findByRole('heading', { level: 1, name: 'Floor board' })).toBeInTheDocument()
    expect(router.state.location.pathname).toBe('/floor')
  })

  it('sends a buyer from / to the portal', async () => {
    const router = setup('buyer', '/')
    expect(await screen.findByRole('heading', { level: 1, name: 'My orders' })).toBeInTheDocument()
    expect(router.state.location.pathname).toBe('/portal')
  })

  it('shows a Retry state, not a blank page, when the server cannot be reached', async () => {
    vi.mocked(api.GET).mockRejectedValue(new TypeError('Failed to fetch'))
    const router = createMemoryRouter(routeObjects, { initialEntries: ['/floor'] })
    render(
      <QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}>
        <RouterProvider router={router} />
      </QueryClientProvider>,
    )
    expect(await screen.findByRole('alert')).toHaveTextContent(/reach the server/i)
    expect(screen.getByRole('button', { name: /retry/i })).toBeInTheDocument()
  })
})

describe('app shell', () => {
  it("opens the menu from a button on small screens and lists the role's pages", async () => {
    setup('supervisor', '/floor')
    await userEvent.click(await screen.findByRole('button', { name: /open menu/i }))
    const dialog = await screen.findByRole('dialog', { name: 'Menu' })
    expect(dialog).toHaveTextContent('Floor board')
    expect(dialog).toHaveTextContent('Attendance')
    expect(dialog).not.toHaveTextContent('Month-end')
  })

  it('closes the menu after choosing a page', async () => {
    setup('supervisor', '/floor')
    await userEvent.click(await screen.findByRole('button', { name: /open menu/i }))
    const dialog = await screen.findByRole('dialog', { name: 'Menu' })
    await userEvent.click(dialog.querySelector('a[href="/orders"]') as HTMLElement)
    expect(await screen.findByRole('heading', { level: 1, name: 'Orders' })).toBeInTheDocument()
    expect(screen.queryByRole('dialog')).not.toBeInTheDocument()
  })

  it('shows the demo-data badge when the API says so, and not otherwise', async () => {
    setup('owner', '/owner', { demo: true })
    expect(await screen.findByText('Demo data')).toBeInTheDocument()
  })

  it('has no demo badge for real data', async () => {
    setup('owner', '/owner', { demo: false })
    await screen.findByRole('heading', { level: 1, name: 'Month-end' })
    expect(screen.queryByText('Demo data')).not.toBeInTheDocument()
  })
})

describe('role guard', () => {
  it('shows a clear message when a buyer opens a staff page', async () => {
    setup('buyer', '/floor')
    expect(await screen.findByText(/not available for your role/i)).toBeInTheDocument()
    expect(screen.queryByRole('heading', { level: 1, name: 'Floor board' })).not.toBeInTheDocument()
  })

  it('lets everyone open a roll passport', async () => {
    setup('buyer', '/r/R-0142')
    expect(await screen.findByRole('heading', { level: 1, name: 'R-0142' })).toBeInTheDocument()
  })

  it('shows Page not found for an unknown address', async () => {
    setup('owner', '/nothing/here')
    expect(await screen.findByText('Page not found')).toBeInTheDocument()
  })
})
