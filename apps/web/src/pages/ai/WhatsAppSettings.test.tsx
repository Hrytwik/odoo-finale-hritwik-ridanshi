import { screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeEach, describe, expect, it, vi } from 'vitest'

vi.mock('@/lib/api/client', () => ({ api: { GET: vi.fn(), POST: vi.fn(), PUT: vi.fn(), PATCH: vi.fn(), DELETE: vi.fn() } }))
import { api } from '@/lib/api/client'
import { mockApi, renderPage } from '@/test/utils'
import WhatsAppSettings from './WhatsAppSettings'

const OFF = { account_sid: null, token_set: false, from_number: null, public_url: null, enabled: false, ready: false }
const ON = { account_sid: 'ACtest123', token_set: true, from_number: '+14155238886', public_url: 'https://mill.example', enabled: true, ready: true }
const put = vi.mocked(api.PUT)
const post = vi.mocked(api.POST)
beforeEach(() => vi.clearAllMocks())

function mockWithPut(settings: object, putReply: object | (() => object)) {
  mockApi({ GET: { '/api/messaging/settings': settings }, POST: { '/api/messaging/test': { status: 'sent', detail: null, to: '+91 ***** **345' } } })
  put.mockImplementation((() => Promise.resolve({ data: typeof putReply === 'function' ? putReply() : putReply, response: new Response(null, { status: 200 }) })) as never)
}

describe('WhatsApp settings', () => {
  it('says it is not connected, explains how to connect, and disables the test', async () => {
    mockWithPut(OFF, OFF)
    renderPage(<WhatsAppSettings />)
    expect(await screen.findByText('Not connected')).toBeInTheDocument()
    expect(screen.getByRole('region', { name: 'How to connect' })).toHaveTextContent('join code')
    expect(screen.getByRole('button', { name: /send a test message/i })).toBeDisabled()
  })

  it('saves the details and does not send the token when its box is left empty', async () => {
    mockWithPut({ ...ON }, ON)
    renderPage(<WhatsAppSettings />)
    await screen.findByText('Connected')
    await userEvent.click(screen.getByRole('button', { name: 'Save settings' }))
    await vi.waitFor(() => expect(put).toHaveBeenCalled())
    const body = (put.mock.calls[0][1] as { body: Record<string, unknown> }).body
    expect(body).toMatchObject({ account_sid: 'ACtest123', from_number: '+14155238886', enabled: true })
    expect(body).not.toHaveProperty('auth_token')
  })

  it('sends a new token when one is typed', async () => {
    mockWithPut(OFF, OFF)
    renderPage(<WhatsAppSettings />)
    await screen.findByText('Not connected')
    await userEvent.type(screen.getByLabelText('Account SID'), 'ACnew')
    await userEvent.type(screen.getByLabelText('Auth Token'), 'tok-123')
    await userEvent.click(screen.getByRole('button', { name: 'Save settings' }))
    await vi.waitFor(() => expect(put).toHaveBeenCalled())
    expect((put.mock.calls[0][1] as { body: Record<string, unknown> }).body).toMatchObject({ account_sid: 'ACnew', auth_token: 'tok-123' })
  })

  it('shows the server refusal under the right box', async () => {
    mockApi({ GET: { '/api/messaging/settings': OFF } })
    put.mockImplementation((() => Promise.resolve({ error: { code: 'VALIDATION_ERROR', message: 'That sender number does not look right.', field: 'from_number', fields: null }, response: new Response(null, { status: 422 }) })) as never)
    renderPage(<WhatsAppSettings />)
    await screen.findByText('Not connected')
    await userEvent.type(screen.getByLabelText('WhatsApp sender number'), 'abc')
    await userEvent.click(screen.getByRole('button', { name: 'Save settings' }))
    expect(await screen.findByText('That sender number does not look right.')).toBeInTheDocument()
  })

  it('sends a test message to the number typed and says where it went', async () => {
    mockWithPut(ON, ON)
    renderPage(<WhatsAppSettings />)
    await screen.findByText('Connected')
    await userEvent.type(screen.getByLabelText('Phone number'), '98450 12345')
    await userEvent.click(screen.getByRole('button', { name: /send a test message/i }))
    expect(await screen.findByText(/Sent to \+91 \*\*\*\*\* \*\*345/)).toBeInTheDocument()
    expect(post).toHaveBeenCalledWith('/api/messaging/test', { body: { to: '98450 12345' } })
  })

  it('shows why a test was not delivered', async () => {
    mockApi({ GET: { '/api/messaging/settings': ON }, POST: { '/api/messaging/test': { status: 'failed', detail: 'This phone has not joined the sandbox yet.', to: '+91 ***** **345' } } })
    renderPage(<WhatsAppSettings />)
    await screen.findByText('Connected')
    await userEvent.type(screen.getByLabelText('Phone number'), '98450 12345')
    await userEvent.click(screen.getByRole('button', { name: /send a test message/i }))
    expect(await screen.findByText('This phone has not joined the sandbox yet.')).toBeInTheDocument()
  })
})
