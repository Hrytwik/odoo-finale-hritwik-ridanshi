import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'
import { QrScanner } from './QrScanner'

describe('QrScanner (no camera in the test browser)', () => {
  it('opens a roll typed by hand', async () => {
    const onCode = vi.fn()
    render(<QrScanner open onClose={vi.fn()} onCode={onCode} />)
    await userEvent.type(screen.getByLabelText(/roll code/i), 'r-0142')
    await userEvent.click(screen.getByRole('button', { name: /open roll/i }))
    expect(onCode).toHaveBeenCalledWith('R-0142')
  })

  it('accepts the address printed on the tag', async () => {
    const onCode = vi.fn()
    render(<QrScanner open onClose={vi.fn()} onCode={onCode} />)
    await userEvent.type(screen.getByLabelText(/roll code/i), 'https://192.168.1.23:8443/r/R-0007')
    await userEvent.click(screen.getByRole('button', { name: /open roll/i }))
    expect(onCode).toHaveBeenCalledWith('R-0007')
  })

  it('refuses something that is not a roll code and says what to type', async () => {
    const onCode = vi.fn()
    render(<QrScanner open onClose={vi.fn()} onCode={onCode} />)
    await userEvent.type(screen.getByLabelText(/roll code/i), 'L-0017')
    await userEvent.click(screen.getByRole('button', { name: /open roll/i }))
    expect(await screen.findByText(/not a roll code/i)).toBeInTheDocument()
    expect(onCode).not.toHaveBeenCalled()
  })

  it('explains when the camera cannot be used, and still lets you type', () => {
    render(<QrScanner open onClose={vi.fn()} onCode={vi.fn()} />)
    expect(screen.getByText(/camera is not available/i)).toBeInTheDocument()
    expect(screen.getByLabelText(/roll code/i)).toBeInTheDocument()
  })

  it('renders nothing while closed', () => {
    render(<QrScanner open={false} onClose={vi.fn()} onCode={vi.fn()} />)
    expect(screen.queryByRole('dialog')).not.toBeInTheDocument()
  })
})
