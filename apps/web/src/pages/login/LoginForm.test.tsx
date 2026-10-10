import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeEach, describe, expect, it, vi } from 'vitest'

vi.mock('@/lib/api/client', () => ({ api: { POST: vi.fn() } }))
import { api } from '@/lib/api/client'
import { LoginForm } from './LoginForm'

const ok = (data: unknown) => Promise.resolve({ data, response: new Response(null, { status: 200 }) })
const me = { id: 1, username: 'owner', role: 'owner', display_name: 'owner', worker_id: null, buyer_id: null }

beforeEach(() => {
  vi.mocked(api.POST).mockReset()
})

async function fill() {
  await userEvent.type(screen.getByLabelText(/username/i), 'owner')
  await userEvent.type(screen.getByLabelText(/password/i), 'everest123')
}

describe('LoginForm', () => {
  it('logs in and reports the user', async () => {
    vi.mocked(api.POST).mockReturnValue(ok(me) as never)
    const onSuccess = vi.fn()
    render(<LoginForm onSuccess={onSuccess} />)
    await fill()
    await userEvent.click(screen.getByRole('button', { name: /log in/i }))
    await waitFor(() => expect(onSuccess).toHaveBeenCalledWith(me))
  })

  it('shows the server message on a wrong password', async () => {
    vi.mocked(api.POST).mockReturnValue(
      Promise.resolve({
        error: { code: 'BAD_CREDENTIALS', message: 'Wrong username or password', field: null, fields: null },
        response: new Response(null, { status: 401 }),
      }) as never,
    )
    render(<LoginForm onSuccess={vi.fn()} />)
    await fill()
    await userEvent.click(screen.getByRole('button', { name: /log in/i }))
    expect(await screen.findByRole('alert')).toHaveTextContent('Wrong username or password')
  })

  it('requires both fields before calling the server', async () => {
    render(<LoginForm onSuccess={vi.fn()} />)
    await userEvent.click(screen.getByRole('button', { name: /log in/i }))
    expect(await screen.findByText(/enter your username/i)).toBeInTheDocument()
    expect(screen.getByText(/enter your password/i)).toBeInTheDocument()
    expect(api.POST).not.toHaveBeenCalled()
  })

  it('sends one request when Log in is pressed twice quickly', async () => {
    vi.mocked(api.POST).mockReturnValue(new Promise(() => {}) as never)
    render(<LoginForm onSuccess={vi.fn()} />)
    await fill()
    const form = screen.getByRole('button', { name: /log in/i }).closest('form')!
    fireEvent.submit(form)
    fireEvent.submit(form)
    await waitFor(() => expect(api.POST).toHaveBeenCalledTimes(1))
  })

  it('shows a readable message when the server cannot be reached', async () => {
    vi.mocked(api.POST).mockRejectedValue(new TypeError('Failed to fetch'))
    render(<LoginForm onSuccess={vi.fn()} />)
    await fill()
    await userEvent.click(screen.getByRole('button', { name: /log in/i }))
    expect(await screen.findByRole('alert')).toHaveTextContent(/reach the server/i)
  })
})
