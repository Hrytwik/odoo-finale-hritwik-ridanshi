import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'
import { ApiError } from '@/lib/api/errors'
import { Alert } from './Alert'
import { EmptyState } from './EmptyState'
import { ErrorState } from './ErrorState'
import { LoadingState } from './LoadingState'
import { PageHeader } from './PageHeader'
import { SubmitButton } from './SubmitButton'

describe('ErrorState', () => {
  it('explains a network failure and offers retry', async () => {
    const onRetry = vi.fn()
    const err = new ApiError(0, {
      code: 'NETWORK_ERROR',
      message: "Can't reach the server. Check the Wi-Fi and try again.",
      field: null,
      fields: null,
    })
    render(<ErrorState error={err} onRetry={onRetry} />)
    expect(screen.getByRole('alert')).toHaveTextContent(/reach the server/i)
    await userEvent.click(screen.getByRole('button', { name: /retry/i }))
    expect(onRetry).toHaveBeenCalledOnce()
  })

  it('has no retry button when there is nothing to retry', () => {
    render(<ErrorState error={new Error('x')} />)
    expect(screen.queryByRole('button')).not.toBeInTheDocument()
    expect(screen.getByRole('alert')).toHaveTextContent('Something went wrong.')
  })
})

describe('SubmitButton', () => {
  it('is a submit button', () => {
    render(<SubmitButton pending={false}>Log in</SubmitButton>)
    expect(screen.getByRole('button', { name: 'Log in' })).toHaveAttribute('type', 'submit')
  })

  it('is disabled and busy while pending', () => {
    render(<SubmitButton pending>Log in</SubmitButton>)
    const button = screen.getByRole('button', { name: 'Log in' })
    expect(button).toBeDisabled()
    expect(button).toHaveAttribute('aria-busy', 'true')
  })
})

describe('small pieces', () => {
  it('PageHeader shows title, description and actions', () => {
    render(<PageHeader title="Orders" description="All buyer orders" actions={<button>New order</button>} />)
    expect(screen.getByRole('heading', { level: 1, name: 'Orders' })).toBeInTheDocument()
    expect(screen.getByText('All buyer orders')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'New order' })).toBeInTheDocument()
  })

  it('EmptyState explains what to do', () => {
    render(<EmptyState title="No orders yet" description="Create the first one." />)
    expect(screen.getByText('No orders yet')).toBeInTheDocument()
  })

  it('LoadingState renders the requested number of placeholders and is marked busy', () => {
    const { container } = render(<LoadingState rows={3} />)
    expect(container.querySelectorAll('.skeleton')).toHaveLength(3)
    expect(screen.getByLabelText('Loading')).toHaveAttribute('aria-busy', 'true')
  })

  it('Alert announces errors but not info', () => {
    const { rerender } = render(<Alert tone="error">Wrong password</Alert>)
    expect(screen.getByRole('alert')).toHaveTextContent('Wrong password')
    rerender(<Alert>Saved</Alert>)
    expect(screen.queryByRole('alert')).not.toBeInTheDocument()
  })
})
