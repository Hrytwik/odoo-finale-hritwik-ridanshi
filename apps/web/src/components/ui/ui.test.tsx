import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { useState } from 'react'
import { describe, expect, it, vi } from 'vitest'
import { Badge } from './Badge'
import { Button } from './Button'
import { Dialog } from './Dialog'
import { Field, Input } from './Field'
import { Table } from './Table'

describe('Button', () => {
  it('is type="button" by default so it never submits a form by accident', () => {
    render(<Button>Save</Button>)
    expect(screen.getByRole('button', { name: 'Save' })).toHaveAttribute('type', 'button')
  })

  it('applies the variant class and fires onClick', async () => {
    const onClick = vi.fn()
    render(
      <Button variant="danger" onClick={onClick}>
        Delete
      </Button>,
    )
    const button = screen.getByRole('button', { name: 'Delete' })
    expect(button).toHaveClass('btn-danger')
    await userEvent.click(button)
    expect(onClick).toHaveBeenCalledOnce()
  })

  it('does not fire when disabled', async () => {
    const onClick = vi.fn()
    render(
      <Button disabled onClick={onClick}>
        Save
      </Button>,
    )
    await userEvent.click(screen.getByRole('button', { name: 'Save' }))
    expect(onClick).not.toHaveBeenCalled()
  })
})

describe('Field', () => {
  it('connects the label to the control', () => {
    render(<Field label="Challan no">{(c) => <Input {...c} />}</Field>)
    expect(screen.getByLabelText('Challan no')).toBeInTheDocument()
  })

  it('shows the error, marks the control invalid and links the description', () => {
    render(
      <Field label="Challan no" error="Already entered" hint="From the paper challan">
        {(c) => <Input {...c} />}
      </Field>,
    )
    const input = screen.getByLabelText('Challan no')
    expect(input).toHaveAttribute('aria-invalid', 'true')
    expect(input).toHaveAccessibleDescription('From the paper challan Already entered')
    expect(screen.getByText('Already entered')).toBeInTheDocument()
  })

  it('is valid when there is no error', () => {
    render(<Field label="Name">{(c) => <Input {...c} />}</Field>)
    expect(screen.getByLabelText('Name')).toHaveAttribute('aria-invalid', 'false')
  })
})

describe('Badge and Table', () => {
  it('renders a tone class', () => {
    render(<Badge tone="green">In store</Badge>)
    expect(screen.getByText('In store')).toHaveClass('badge-green')
  })

  it('wraps the table in a scroll box', () => {
    const { container } = render(
      <Table>
        <tbody>
          <tr>
            <td>x</td>
          </tr>
        </tbody>
      </Table>,
    )
    expect(container.querySelector('.table-wrap > table.table')).not.toBeNull()
  })
})

function Harness({ onClose }: { onClose?: () => void }) {
  const [open, setOpen] = useState(false)
  return (
    <>
      <Button onClick={() => setOpen(true)}>Open</Button>
      <Dialog
        open={open}
        title="Menu"
        onClose={() => {
          onClose?.()
          setOpen(false)
        }}
      >
        <a href="/one">One</a>
        <a href="/two">Two</a>
      </Dialog>
    </>
  )
}

describe('Dialog', () => {
  it('is hidden until opened, then labelled by its title', async () => {
    render(<Harness />)
    expect(screen.queryByRole('dialog')).not.toBeInTheDocument()
    await userEvent.click(screen.getByRole('button', { name: 'Open' }))
    expect(screen.getByRole('dialog', { name: 'Menu' })).toBeInTheDocument()
  })

  it('closes on Escape and gives focus back to the opener', async () => {
    const onClose = vi.fn()
    render(<Harness onClose={onClose} />)
    const opener = screen.getByRole('button', { name: 'Open' })
    await userEvent.click(opener)
    await userEvent.keyboard('{Escape}')
    expect(onClose).toHaveBeenCalledOnce()
    expect(screen.queryByRole('dialog')).not.toBeInTheDocument()
    expect(opener).toHaveFocus()
  })

  it('closes with the Close button', async () => {
    render(<Harness />)
    await userEvent.click(screen.getByRole('button', { name: 'Open' }))
    await userEvent.click(screen.getByRole('button', { name: 'Close' }))
    expect(screen.queryByRole('dialog')).not.toBeInTheDocument()
  })

  it('closes when the dark backdrop is pressed but not when the panel is', async () => {
    render(<Harness />)
    await userEvent.click(screen.getByRole('button', { name: 'Open' }))
    await userEvent.click(screen.getByRole('dialog'))
    expect(screen.getByRole('dialog')).toBeInTheDocument()
    const backdrop = screen.getByRole('dialog').parentElement as HTMLElement
    await userEvent.pointer({ target: backdrop, keys: '[MouseLeft]' })
    expect(screen.queryByRole('dialog')).not.toBeInTheDocument()
  })

  it('keeps Tab inside the dialog and locks page scroll while open', async () => {
    render(<Harness />)
    await userEvent.click(screen.getByRole('button', { name: 'Open' }))
    expect(document.body.style.overflow).toBe('hidden')
    // Close, One, Two are the focusable items; Tab past the last wraps to the first
    screen.getByRole('link', { name: 'Two' }).focus()
    await userEvent.tab()
    expect(screen.getByRole('button', { name: 'Close' })).toHaveFocus()
    await userEvent.keyboard('{Escape}')
    expect(document.body.style.overflow).toBe('')
  })
})
