import { screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeEach, describe, expect, it, vi } from 'vitest'

vi.mock('@/lib/api/client', () => ({ api: { GET: vi.fn(), POST: vi.fn(), PATCH: vi.fn(), DELETE: vi.fn() } }))
import { api } from '@/lib/api/client'
import { mockApi, renderPage } from '@/test/utils'
import BuyerInvites from '../admin/BuyerInvites'
import { SignupForm } from './SignupForm'

const ME = { id: 9, username: 'a@b.co', role: 'buyer', display_name: 'Sharma Fabrics', worker_id: null, buyer_id: 1 }
const post = vi.mocked(api.POST)
beforeEach(() => vi.clearAllMocks())

async function fill(over: Partial<Record<'Your email' | 'Invite code' | 'Choose a password' | 'Type it again', string>> = {}) {
  const v = { 'Your email': 'accounts@sharma.example', 'Invite code': 'ABCD-2FGH', 'Choose a password': 'Sharma-pass9', 'Type it again': 'Sharma-pass9', ...over }
  for (const [label, value] of Object.entries(v)) await userEvent.type(screen.getByLabelText(label), value)
  await userEvent.click(screen.getByRole('button', { name: /create my account/i }))
}

describe('buyer sign-up form', () => {
  it('sends the email, code and password and hands back the new login', async () => {
    mockApi({ POST: { '/api/auth/signup': ME } })
    const done = vi.fn()
    renderPage(<SignupForm onSuccess={done} />)
    await fill()
    await vi.waitFor(() => expect(done).toHaveBeenCalledWith(ME))
    expect(post).toHaveBeenCalledWith('/api/auth/signup', { body: { email: 'accounts@sharma.example', invite_code: 'ABCD-2FGH', password: 'Sharma-pass9' } })
  })

  it('does not send a weak password and says why', async () => {
    mockApi({ POST: { '/api/auth/signup': ME } })
    renderPage(<SignupForm onSuccess={vi.fn()} />)
    await fill({ 'Choose a password': 'short1', 'Type it again': 'short1' })
    expect(await screen.findByText('Use at least 8 characters')).toBeInTheDocument()
    expect(post).not.toHaveBeenCalled()
  })

  it('does not send when the two passwords differ', async () => {
    mockApi({ POST: { '/api/auth/signup': ME } })
    renderPage(<SignupForm onSuccess={vi.fn()} />)
    await fill({ 'Type it again': 'Different-pass9' })
    expect(await screen.findByText('The two passwords are not the same')).toBeInTheDocument()
    expect(post).not.toHaveBeenCalled()
  })

  it('shows the same plain refusal for a wrong code or email', async () => {
    mockApi({ POST: { '/api/auth/signup': { status: 422, error: { code: 'SIGNUP_REFUSED', message: 'That email and invite code do not match a buyer. Check both, or ask the mill.', field: null, fields: null } } } })
    renderPage(<SignupForm onSuccess={vi.fn()} />)
    await fill()
    expect(await screen.findByText(/do not match a buyer/)).toBeInTheDocument()
  })
})

describe('buyer invites (owner)', () => {
  it('lists each buyer with the code, whether they have a login, and what to do when there is no email', async () => {
    mockApi({
      GET: {
        '/api/auth/buyer-invites': [
          { buyer_id: 1, buyer_name: 'Sharma Fabrics', email: 'a@sharma.example', invite_code: 'ABCD-2FGH', has_account: true },
          { buyer_id: 2, buyer_name: 'No Email Co', email: null, invite_code: null, has_account: false },
        ],
      },
    })
    renderPage(<BuyerInvites />)
    expect(await screen.findByText('ABCD-2FGH')).toBeInTheDocument()
    // the filter also offers an option with this label, so look for the badge on the row itself
    expect(screen.getAllByText('Has a login').some((el) => el.tagName !== 'OPTION')).toBe(true)
    expect(screen.getAllByText('Not signed up').some((el) => el.tagName !== 'OPTION')).toBe(true)
    expect(screen.getByRole('link', { name: 'Buyers' })).toHaveAttribute('href', '/admin/buyers')
    expect(screen.getByRole('button', { name: 'Copy the invite code for Sharma Fabrics' })).toBeInTheDocument()
  })
})
