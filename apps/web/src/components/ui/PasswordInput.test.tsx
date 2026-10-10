import { fireEvent, render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it } from 'vitest'
import { PasswordInput } from './PasswordInput'

describe('PasswordInput', () => {
  it('hides what is typed until asked to show it', async () => {
    render(<PasswordInput aria-label="Secret" />)
    const box = screen.getByLabelText('Secret')
    await userEvent.type(box, 'abc123')
    expect(box).toHaveAttribute('type', 'password')
    expect(box).toHaveValue('abc123')
    const toggle = screen.getByRole('button', { name: 'Show characters' })
    expect(toggle).toHaveAttribute('aria-pressed', 'false')
    await userEvent.click(toggle)
    expect(box).toHaveAttribute('type', 'text')
    expect(screen.getByRole('button', { name: 'Hide characters' })).toHaveAttribute('aria-pressed', 'true')
  })

  it('keeps the typed value when toggled', async () => {
    render(<PasswordInput aria-label="Secret" />)
    await userEvent.type(screen.getByLabelText('Secret'), 'hello1')
    await userEvent.click(screen.getByRole('button', { name: 'Show characters' }))
    expect(screen.getByLabelText('Secret')).toHaveValue('hello1')
  })

  it('does not submit a form when the toggle is pressed', async () => {
    let submitted = false
    render(
      <form
        onSubmit={(e) => {
          e.preventDefault()
          submitted = true
        }}
      >
        <PasswordInput aria-label="Secret" />
      </form>,
    )
    await userEvent.click(screen.getByRole('button', { name: 'Show characters' }))
    expect(submitted).toBe(false)
  })

  it('warns while Caps Lock is on, and stops when it is off', () => {
    render(<PasswordInput aria-label="Secret" />)
    const box = screen.getByLabelText('Secret')
    fireEvent.keyUp(box, { key: 'a', modifierCapsLock: true })
    expect(screen.getByText('Caps Lock is on')).toBeInTheDocument()
    fireEvent.keyUp(box, { key: 'a', modifierCapsLock: false })
    expect(screen.queryByText('Caps Lock is on')).not.toBeInTheDocument()
  })

  it('passes the usual input props through', () => {
    render(<PasswordInput aria-label="Secret" placeholder="Saved" autoComplete="new-password" disabled />)
    const box = screen.getByLabelText('Secret')
    expect(box).toHaveAttribute('placeholder', 'Saved')
    expect(box).toHaveAttribute('autocomplete', 'new-password')
    expect(box).toBeDisabled()
  })
})
