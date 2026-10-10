import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeEach, describe, expect, it, vi } from 'vitest'

vi.mock('@/lib/api/client', () => ({ api: { POST: vi.fn() } }))
import { api } from '@/lib/api/client'
import { ChangePasswordDialog } from './ChangePasswordDialog'

const post = vi.mocked(api.POST)
const ok = () => Promise.resolve({ data: { id: 1 }, response: new Response(null, { status: 200 }) }) as never
const fail = (status: number, error: object) => Promise.resolve({ error, response: new Response(null, { status }) }) as never

function open(onClose = vi.fn()) {
  render(<ChangePasswordDialog open onClose={onClose} username="ravi" />)
  return onClose
}
const type = async (label: string, text: string) => userEvent.type(screen.getByLabelText(label), text)
const submit = () => userEvent.click(screen.getByRole('button', { name: 'Change password' }))
async function fillAll(current: string, next: string, again = next) {
  await type('Current password', current)
  await type('New password', next)
  await type('New password again', again)
}

beforeEach(() => post.mockReset())

describe('ChangePasswordDialog', () => {
  it('sends the current and the new password, and closes', async () => {
    post.mockReturnValue(ok())
    const onClose = open()
    await fillAll('rightpass1', 'brandnew-pass9')
    await submit()
    await waitFor(() => expect(post).toHaveBeenCalledWith('/api/auth/change-password', { body: { current_password: 'rightpass1', new_password: 'brandnew-pass9' } }))
    await waitFor(() => expect(onClose).toHaveBeenCalled())
  })

  it('asks for the current password', async () => {
    open()
    await type('New password', 'brandnew-pass9')
    await type('New password again', 'brandnew-pass9')
    await submit()
    expect(await screen.findByText('Enter your current password')).toBeInTheDocument()
    expect(post).not.toHaveBeenCalled()
  })

  it('refuses a weak new password with the reason, before sending', async () => {
    open()
    await fillAll('rightpass1', 'short1')
    await submit()
    expect(await screen.findByText('Use at least 8 characters')).toBeInTheDocument()
    expect(post).not.toHaveBeenCalled()
  })

  it('refuses a new password that contains the username', async () => {
    open()
    await fillAll('rightpass1', 'my-ravi-pass9')
    await submit()
    expect(await screen.findByText(/username/i)).toBeInTheDocument()
    expect(post).not.toHaveBeenCalled()
  })

  it('refuses when the two new passwords differ', async () => {
    open()
    await fillAll('rightpass1', 'brandnew-pass9', 'brandnew-pass8')
    await submit()
    expect(await screen.findByText('The two new passwords are not the same')).toBeInTheDocument()
    expect(post).not.toHaveBeenCalled()
  })

  it('refuses the same password as the current one', async () => {
    open()
    await fillAll('rightpass1', 'rightpass1')
    await submit()
    expect(await screen.findByText(/different from the current one/i)).toBeInTheDocument()
    expect(post).not.toHaveBeenCalled()
  })

  it('puts the wrong-current-password message under that box and keeps the dialog open', async () => {
    post.mockReturnValue(fail(422, { code: 'WRONG_PASSWORD', message: 'The current password is not right', field: 'current_password', fields: null }))
    const onClose = open()
    await fillAll('not-right-1', 'brandnew-pass9')
    await submit()
    expect(await screen.findByText('The current password is not right')).toBeInTheDocument()
    expect(onClose).not.toHaveBeenCalled()
  })

  it('shows a lock-out message from the server in the dialog', async () => {
    post.mockReturnValue(fail(429, { code: 'TOO_MANY_ATTEMPTS', message: 'Too many wrong attempts. Try again in 15 minutes.', field: null, fields: null }))
    open()
    await fillAll('rightpass1', 'brandnew-pass9')
    await submit()
    expect(await screen.findByRole('alert')).toHaveTextContent('Try again in 15 minutes')
  })

  it('closes with Cancel without sending anything', async () => {
    const onClose = open()
    await type('Current password', 'rightpass1')
    await userEvent.click(screen.getByRole('button', { name: 'Cancel' }))
    expect(onClose).toHaveBeenCalled()
    expect(post).not.toHaveBeenCalled()
  })
})
