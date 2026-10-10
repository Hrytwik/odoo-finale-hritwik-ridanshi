import { screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeEach, describe, expect, it, vi } from 'vitest'

vi.mock('@/lib/api/client', () => ({ api: { GET: vi.fn(), POST: vi.fn(), PATCH: vi.fn(), DELETE: vi.fn() } }))
import { api } from '@/lib/api/client'
import { mockApi, renderPage } from '@/test/utils'
import { WorkerLoginCell } from './WorkerLogin'

const worker = (over: object) => ({ id: 3, code: 'W-003', name: 'Arjun Rao', role: 'supervisor', daily_wage: 900, active: true, ...over }) as never
const USER = { id: 1, username: 'owner', role: 'owner', worker_id: null, buyer_id: null }
const post = vi.mocked(api.POST)
beforeEach(() => vi.clearAllMocks())

describe('a worker login from the Workers screen', () => {
  it('offers Create login to a supervisor with no login', async () => {
    mockApi({ GET: { '/api/users': [USER] } })
    renderPage(<WorkerLoginCell worker={worker({})} />)
    expect(await screen.findByRole('button', { name: 'Create a login for Arjun Rao' })).toBeInTheDocument()
  })

  it('shows the login instead when there is one', async () => {
    mockApi({ GET: { '/api/users': [USER, { id: 2, username: 'arjun.r', role: 'supervisor', worker_id: 3, buyer_id: null }] } })
    renderPage(<WorkerLoginCell worker={worker({})} />)
    expect(await screen.findByText('Login: arjun.r')).toBeInTheDocument()
    expect(screen.queryByRole('button')).not.toBeInTheDocument()
  })

  it('offers nothing to an operator, who does not log in', async () => {
    mockApi({ GET: { '/api/users': [USER] } })
    renderPage(<WorkerLoginCell worker={worker({ role: 'operator' })} />)
    expect(await screen.findByText('No login needed')).toBeInTheDocument()
  })

  it('suggests a username and a password, creates the login linked to the worker, and shows the details once', async () => {
    mockApi({ GET: { '/api/users': [USER] }, POST: { '/api/users': { id: 9 } } })
    renderPage(<WorkerLoginCell worker={worker({ role: 'inspector', id: 7, name: 'Meena Devi' })} />)
    await userEvent.click(await screen.findByRole('button', { name: 'Create a login for Meena Devi' }))
    const dialog = await screen.findByRole('dialog')
    expect(within(dialog).getByLabelText('Username')).toHaveValue('meena.d')
    const password = (within(dialog).getByLabelText('Temporary password') as HTMLInputElement).value
    expect(password).toMatch(/^[A-Za-z2-9]{4}-[A-Za-z2-9]{4}-[A-Za-z2-9]{4}$/)
    expect(within(dialog).getByText('QC inspector')).toBeInTheDocument()
    await userEvent.click(within(dialog).getByRole('button', { name: 'Create login' }))
    await vi.waitFor(() => expect(post).toHaveBeenCalledWith('/api/users', { body: { username: 'meena.d', password, role: 'qc', worker_id: 7 } }))
    expect(await within(dialog).findByText('Temporary password')).toBeInTheDocument()
    expect(within(dialog).getByText(password)).toBeInTheDocument()
    expect(within(dialog).getByText(/shown only now/i)).toBeInTheDocument()
    expect(within(dialog).getByRole('button', { name: /print slip/i })).toBeInTheDocument()
  })

  it('shows the reason when the server refuses, and keeps the form', async () => {
    mockApi({
      GET: { '/api/users': [USER] },
      POST: { '/api/users': { status: 409, error: { code: 'CONFLICT', message: 'That username is already taken', field: 'username', fields: null } } },
    })
    renderPage(<WorkerLoginCell worker={worker({})} />)
    await userEvent.click(await screen.findByRole('button', { name: 'Create a login for Arjun Rao' }))
    await userEvent.click(within(await screen.findByRole('dialog')).getByRole('button', { name: 'Create login' }))
    expect(await screen.findByText('That username is already taken')).toBeInTheDocument()
  })
})
