import { screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeEach, describe, expect, it, vi } from 'vitest'

vi.mock('@/lib/api/client', () => ({ api: { GET: vi.fn(), POST: vi.fn(), PATCH: vi.fn(), DELETE: vi.fn() } }))
import { api } from '@/lib/api/client'
import { NotificationBell } from '@/components/shell/NotificationBell'
import { mockApi, renderPage } from '@/test/utils'
import { DelayNoticeButton } from './DelayNotice'

const me = (role: string) => ({ id: 1, username: role, role, display_name: role, worker_id: null, buyer_id: null })
const post = vi.mocked(api.POST)
beforeEach(() => vi.clearAllMocks())

describe('Tell the buyer about a delay (owner)', () => {
  const channel = { whatsapp_ready: true, to: '+91 ••••• ••345', problem: null, tracking_url: 'https://mill.example/portal/orders/ORD-0001' }
  const draftReply = { message: 'Your order ORD-0001 is delayed because one of our machines needs repair.', drafted_by_ai: true, channel }

  function open(role = 'owner', extra: Record<string, unknown> = {}) {
    mockApi({
      GET: { '/api/auth/me': me(role) },
      POST: { '/api/orders/{order_code}/delay-notice/draft': draftReply, '/api/orders/{order_code}/delay-notice': { id: 1 }, ...extra },
    })
    return renderPage(<DelayNoticeButton orderCode="ORD-0001" buyerName="Sharma Fabrics" />)
  }

  it('is offered to the owner only', async () => {
    open('accountant')
    await new Promise((r) => setTimeout(r, 30))
    expect(screen.queryByRole('button', { name: /tell the buyer about a delay/i })).not.toBeInTheDocument()
  })

  it('drafts a sentence from the chosen reason, lets it be edited, and sends it', async () => {
    open()
    await userEvent.click(await screen.findByRole('button', { name: /tell the buyer about a delay/i }))
    const dialog = await screen.findByRole('dialog')
    await userEvent.selectOptions(within(dialog).getByLabelText('Reason for the delay'), 'machine_breakdown')
    const box = await within(dialog).findByLabelText('Message to the buyer')
    expect(box).toHaveValue(draftReply.message)
    expect(post).toHaveBeenCalledWith('/api/orders/{order_code}/delay-notice/draft', { params: { path: { order_code: 'ORD-0001' } }, body: { reason: 'machine_breakdown' } })
    expect(within(dialog).getByText(/written by the ai/i)).toBeInTheDocument()
    await userEvent.clear(box)
    await userEvent.type(box, 'Short delay: a repair.')
    await userEvent.click(within(dialog).getByRole('button', { name: 'Send to the buyer' }))
    await vi.waitFor(() =>
      expect(post).toHaveBeenCalledWith('/api/orders/{order_code}/delay-notice', {
        params: { path: { order_code: 'ORD-0001' } },
        body: { reason: 'machine_breakdown', message: 'Short delay: a repair.' },
      }),
    )
    await vi.waitFor(() => expect(screen.queryByRole('dialog')).not.toBeInTheDocument())
  })

  it('will not send before a reason is chosen', async () => {
    open()
    await userEvent.click(await screen.findByRole('button', { name: /tell the buyer about a delay/i }))
    await userEvent.click(within(await screen.findByRole('dialog')).getByRole('button', { name: 'Send to the buyer' }))
    expect(await screen.findByText('Choose a reason first')).toBeInTheDocument()
    expect(post).not.toHaveBeenCalledWith('/api/orders/{order_code}/delay-notice', expect.anything())
  })

  it('says a standard message was used when no model wrote it', async () => {
    open('owner', { '/api/orders/{order_code}/delay-notice/draft': { message: 'Standard text.', drafted_by_ai: false } })
    await userEvent.click(await screen.findByRole('button', { name: /tell the buyer about a delay/i }))
    await userEvent.selectOptions(within(await screen.findByRole('dialog')).getByLabelText('Reason for the delay'), 'power_cut')
    expect(await screen.findByText(/a standard message/i)).toBeInTheDocument()
  })
})

describe("the buyer's bell", () => {
  const item = (id: number, read: boolean) => ({ id, order_code: 'ORD-0001', reason: 'power_cut', reason_label: 'Power cut', message: `Message ${id}`, created_at: '2026-10-10T10:00:00Z', read })

  it('shows how many are new and opens the list, marking them read', async () => {
    let data = { unread: 2, items: [item(2, false), item(1, false)] }
    mockApi({
      GET: { '/api/portal/notifications': () => data },
      POST: {
        '/api/portal/notifications/read': () => {
          data = { unread: 0, items: data.items.map((i) => ({ ...i, read: true })) }
          return data
        },
      },
    })
    renderPage(<NotificationBell />)
    const bell = await screen.findByRole('button', { name: 'Notifications, 2 new' })
    await userEvent.click(bell)
    const dialog = await screen.findByRole('dialog', { name: 'Notifications' })
    expect(within(dialog).getByText('Message 2')).toBeInTheDocument()
    expect(within(dialog).getAllByRole('link', { name: 'ORD-0001' })[0]).toHaveAttribute('href', '/portal/orders/ORD-0001')
    await vi.waitFor(() => expect(post).toHaveBeenCalledWith('/api/portal/notifications/read'))
    expect(await screen.findByRole('button', { name: 'Notifications' })).toBeInTheDocument()
  })

  it('says so when there is nothing yet', async () => {
    mockApi({ GET: { '/api/portal/notifications': { unread: 0, items: [] } } })
    renderPage(<NotificationBell />)
    await userEvent.click(await screen.findByRole('button', { name: 'Notifications' }))
    expect(await screen.findByText(/Nothing yet/)).toBeInTheDocument()
  })
})


describe('the WhatsApp part of the delay dialog', () => {
  const draft = (channel: object) => ({ message: 'Your order is delayed: a power cut.', drafted_by_ai: false, channel })
  const open = async (channel: object, sent: object = { id: 1, whatsapp_status: 'sent', whatsapp_detail: null }) => {
    mockApi({
      GET: { '/api/auth/me': me('owner') },
      POST: { '/api/orders/{order_code}/delay-notice/draft': draft(channel), '/api/orders/{order_code}/delay-notice': sent },
    })
    renderPage(<DelayNoticeButton orderCode="ORD-0001" buyerName="Sharma Fabrics" />)
    await userEvent.click(await screen.findByRole('button', { name: /tell the buyer about a delay/i }))
    await userEvent.selectOptions(within(await screen.findByRole('dialog')).getByLabelText('Reason for the delay'), 'power_cut')
    return screen.findByRole('dialog')
  }

  it('shows the message as it will look on WhatsApp, with the tracking button, and where it will go', async () => {
    const dialog = await open({ whatsapp_ready: true, to: '+91 ***** **345', problem: null, tracking_url: 'https://mill.example/portal/orders/ORD-0001' })
    const preview = await within(dialog).findByRole('figure', { name: 'Preview of the WhatsApp message' })
    expect(preview).toHaveTextContent('Your order is delayed: a power cut.')
    expect(preview).toHaveTextContent('Track my order')
    expect(within(dialog).getByText('It will also be sent to +91 ***** **345.')).toBeInTheDocument()
  })

  it('follows what the owner types in the message box', async () => {
    const dialog = await open({ whatsapp_ready: true, to: '+91 ***** **345', problem: null, tracking_url: 'https://x/y' })
    const box = await within(dialog).findByLabelText('Message to the buyer')
    await userEvent.clear(box)
    await userEvent.type(box, 'New words.')
    expect(within(dialog).getByRole('figure')).toHaveTextContent('New words.')
  })

  it('says why it will not go on WhatsApp, and leaves out the tracking button when there is no address', async () => {
    const dialog = await open({ whatsapp_ready: false, to: null, problem: 'Sharma Fabrics has no phone number. Add one under Buyers.', tracking_url: null })
    expect(await within(dialog).findByText('Sharma Fabrics has no phone number. Add one under Buyers.')).toBeInTheDocument()
    expect(within(dialog).getByRole('figure')).not.toHaveTextContent('Track my order')
  })
})
