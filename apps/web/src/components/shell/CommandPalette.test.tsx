import { screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'
import { renderPage } from '@/test/utils'
import { CommandPalette } from './CommandPalette'

type Role = Parameters<typeof CommandPalette>[0]['role']

function setup(role: Role = 'owner', onClose = vi.fn()) {
  renderPage(<CommandPalette open onClose={onClose} role={role} />, {
    extra: [
      { path: '/orders', element: <p>orders page</p> },
      { path: '/floor', element: <p>floor page</p> },
      { path: '/r/:code', element: <p>roll page</p> },
      { path: '/portal/orders/:code', element: <p>portal order page</p> },
      { path: '/orders/:code', element: <p>order page</p> },
    ],
  })
  return { onClose }
}
const box = () => screen.findByRole('combobox')

describe('CommandPalette', () => {
  it('lists the pages in the role menu to start with', async () => {
    setup('supervisor')
    await box()
    const options = screen.getAllByRole('option').map((o) => o.textContent ?? '')
    expect(options.join(' ')).toContain('Floor board')
    expect(options.join(' ')).not.toContain('Month-end')
  })

  it('puts the cursor in the search box straight away', async () => {
    setup()
    expect(await box()).toHaveFocus()
  })

  it('narrows the list as you type', async () => {
    setup()
    await userEvent.type(await box(), 'floor')
    const options = screen.getAllByRole('option')
    expect(options).toHaveLength(1)
    expect(options[0]).toHaveTextContent('Floor board')
  })

  it('opens the chosen page with Enter, and closes', async () => {
    const { onClose } = setup()
    await userEvent.type(await box(), 'floor{Enter}')
    expect(await screen.findByText('floor page')).toBeInTheDocument()
    expect(onClose).toHaveBeenCalled()
  })

  it('moves the highlight with the arrow keys', async () => {
    setup()
    const input = await box()
    const first = screen.getAllByRole('option')[0]
    expect(first).toHaveAttribute('aria-selected', 'true')
    await userEvent.type(input, '{ArrowDown}')
    expect(screen.getAllByRole('option')[1]).toHaveAttribute('aria-selected', 'true')
    expect(screen.getAllByRole('option')[0]).toHaveAttribute('aria-selected', 'false')
    await userEvent.type(input, '{ArrowUp}{ArrowUp}')
    // it stops at the top instead of wrapping to a surprise
    expect(screen.getAllByRole('option')[0]).toHaveAttribute('aria-selected', 'true')
  })

  it('opens a page by clicking it', async () => {
    setup()
    await userEvent.click(await screen.findByRole('option', { name: /orders/i }))
    expect(await screen.findByText('orders page')).toBeInTheDocument()
  })

  it('jumps straight to a roll typed as a code', async () => {
    setup()
    await userEvent.type(await box(), 'r-0142')
    expect(screen.getAllByRole('option')[0]).toHaveTextContent('Open roll R-0142')
    await userEvent.keyboard('{Enter}')
    expect(await screen.findByText('roll page')).toBeInTheDocument()
  })

  it('sends a buyer to the portal for an order code, not the staff orders area', async () => {
    setup('buyer')
    await userEvent.type(await box(), 'ORD-0012{Enter}')
    expect(await screen.findByText('portal order page')).toBeInTheDocument()
  })

  it('says so when nothing matches, and Enter then does nothing', async () => {
    const { onClose } = setup()
    await userEvent.type(await box(), 'zzzz{Enter}')
    expect(screen.getByText(/nothing matches/i)).toBeInTheDocument()
    expect(onClose).not.toHaveBeenCalled()
  })

  it('closes with Escape', async () => {
    const { onClose } = setup()
    await userEvent.type(await box(), '{Escape}')
    expect(onClose).toHaveBeenCalled()
  })
})
