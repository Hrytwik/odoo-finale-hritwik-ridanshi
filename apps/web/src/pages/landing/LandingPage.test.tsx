import { screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeEach, describe, expect, it, vi } from 'vitest'

vi.mock('@/lib/api/client', () => ({ api: { GET: vi.fn(), POST: vi.fn(), PATCH: vi.fn(), DELETE: vi.fn() } }))
import { mockApi, renderPage } from '@/test/utils'
import { LandingGate } from './LandingPage'

const ME = { id: 3, username: 'supervisor', role: 'supervisor', display_name: 'Arjun Rao', worker_id: 3, buyer_id: null }

beforeEach(() => {
  vi.clearAllMocks()
  localStorage.clear()
})

describe('Landing page', () => {
  it('greets a visitor with the headline, and sends the log in buttons to the login page', async () => {
    mockApi({ GET: { '/api/auth/me': { status: 401, error: 'Not logged in' } } })
    renderPage(<LandingGate />, { path: '/', extra: [{ path: '/login', element: <p>login page</p> }] })
    expect(await screen.findByRole('heading', { name: 'Every roll, from yarn to invoice.' })).toBeInTheDocument()
    const links = screen.getAllByRole('link', { name: /log in/i })
    expect(links.length).toBeGreaterThanOrEqual(2)
    for (const l of links) expect(l).toHaveAttribute('href', '/login')
    await userEvent.click(links[0])
    expect(await screen.findByText('login page')).toBeInTheDocument()
  })

  it('lists the four areas of the mill', async () => {
    mockApi({ GET: { '/api/auth/me': { status: 401, error: 'Not logged in' } } })
    renderPage(<LandingGate />, { path: '/' })
    await screen.findByRole('heading', { name: /every roll/i })
    for (const name of ['Production', 'Quality', 'Dispatch', 'Accounts']) {
      expect(screen.getByRole('heading', { name })).toBeInTheDocument()
    }
  })

  it('sends someone who is already logged in to their own home', async () => {
    mockApi({ GET: { '/api/auth/me': ME } })
    renderPage(<LandingGate />, { path: '/', extra: [{ path: '/floor', element: <p>floor page</p> }] })
    expect(await screen.findByText('floor page')).toBeInTheDocument()
  })

  it('switches between light and dark from the header', async () => {
    mockApi({ GET: { '/api/auth/me': { status: 401, error: 'Not logged in' } } })
    renderPage(<LandingGate />, { path: '/' })
    await userEvent.click(await screen.findByRole('button', { name: /switch to dark mode/i }))
    expect(document.documentElement.dataset.theme).toBe('dark')
    await userEvent.click(screen.getByRole('button', { name: /switch to light mode/i }))
    expect(document.documentElement.dataset.theme).toBe('light')
  })
})
