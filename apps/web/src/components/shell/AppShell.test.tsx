import { screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeEach, describe, expect, it, vi } from 'vitest'

vi.mock('@/lib/api/client', () => ({ api: { GET: vi.fn(), POST: vi.fn(), PATCH: vi.fn(), DELETE: vi.fn() } }))
vi.mock('@/lib/live', () => ({ useLiveEvents: vi.fn() }))
import { mockApi, renderPage } from '@/test/utils'
import { AppShell } from './AppShell'

const me = { id: 3, username: 'supervisor', role: 'supervisor' as const, display_name: 'Arjun Rao', worker_id: 3, buyer_id: null }

function renderShell() {
  mockApi({ GET: { '/api/health': { status: 'ok', demo_data: false } } })
  return renderPage(
    <AppShell me={me}>
      <p>content</p>
    </AppShell>,
  )
}

beforeEach(() => {
  vi.clearAllMocks()
  localStorage.clear()
  document.documentElement.dataset.theme = 'light'
})

describe('AppShell', () => {
  it("shows who is logged in and the role's menu", () => {
    renderShell()
    expect(screen.getByText('Arjun Rao')).toBeInTheDocument()
    expect(screen.getAllByText('Supervisor').length).toBeGreaterThan(0)
    expect(screen.getByRole('link', { name: /floor board/i })).toBeInTheDocument()
    expect(screen.queryByRole('link', { name: /month-end/i })).not.toBeInTheDocument()
  })

  it('opens the search from the header', async () => {
    renderShell()
    await userEvent.click(screen.getAllByRole('button', { name: /search rolls, lots, orders/i })[0])
    expect(await screen.findByRole('combobox')).toBeInTheDocument()
  })

  it('opens the search with the / key, but not while typing in a field', async () => {
    renderShell()
    await userEvent.keyboard('/')
    expect(await screen.findByRole('combobox')).toBeInTheDocument()
    await userEvent.keyboard('{Escape}')
    expect(screen.queryByRole('combobox')).not.toBeInTheDocument()
  })

  it('opens the search with Ctrl+K and closes it with Ctrl+K again', async () => {
    renderShell()
    await userEvent.keyboard('{Control>}k{/Control}')
    expect(await screen.findByRole('combobox')).toBeInTheDocument()
    await userEvent.keyboard('{Control>}k{/Control}')
    expect(screen.queryByRole('combobox')).not.toBeInTheDocument()
  })

  it('switches to dark mode and back, and remembers the choice', async () => {
    renderShell()
    await userEvent.click(screen.getByRole('button', { name: /switch to dark mode/i }))
    expect(document.documentElement.dataset.theme).toBe('dark')
    expect(localStorage.getItem('everest-theme')).toBe('dark')
    await userEvent.click(screen.getByRole('button', { name: /switch to light mode/i }))
    expect(document.documentElement.dataset.theme).toBe('light')
  })
})
