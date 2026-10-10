import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { useState } from 'react'
import { describe, expect, it } from 'vitest'
import { Disclosure } from './Disclosure'
import { Magnetic } from './Magnetic'
import { SlidingNumber } from './SlidingNumber'
import { Tilt } from './Tilt'
import { TransitionPanel } from './TransitionPanel'

describe('SlidingNumber', () => {
  it('reads out the formatted number once, not digit by digit', () => {
    render(<SlidingNumber value={1234567} />)
    expect(screen.getByLabelText('12,34,567')).toBeInTheDocument()
  })

  it('formats money when given a formatter', () => {
    render(<SlidingNumber value={39600} format={(n) => `₹${Math.round(n).toLocaleString('en-IN')}`} />)
    expect(screen.getByLabelText('₹39,600')).toBeInTheDocument()
  })

  it('shows one digit column per digit', () => {
    const { container } = render(<SlidingNumber value={587} />)
    expect(container.querySelectorAll('.sn-digit')).toHaveLength(3)
  })

  it('updates its label when the value changes', () => {
    const { rerender } = render(<SlidingNumber value={99} />)
    rerender(<SlidingNumber value={1250} />)
    expect(screen.getByLabelText('1,250')).toBeInTheDocument()
  })
})

describe('Disclosure', () => {
  it('starts closed, opens on click and closes again, keeping aria-expanded in sync', async () => {
    render(<Disclosure title="Ledger">row one</Disclosure>)
    const button = screen.getByRole('button', { name: /ledger/i })
    expect(button).toHaveAttribute('aria-expanded', 'false')
    expect(screen.queryByText('row one')).not.toBeInTheDocument()
    await userEvent.click(button)
    expect(button).toHaveAttribute('aria-expanded', 'true')
    expect(screen.getByText('row one')).toBeInTheDocument()
    await userEvent.click(button)
    expect(button).toHaveAttribute('aria-expanded', 'false')
    await waitFor(() => expect(screen.queryByText('row one')).not.toBeInTheDocument())
  })

  it('can start open and shows its meta text', () => {
    render(
      <Disclosure title="Ledger" defaultOpen meta="12 rows">
        row one
      </Disclosure>,
    )
    expect(screen.getByText('row one')).toBeInTheDocument()
    expect(screen.getByText('12 rows')).toBeInTheDocument()
  })

  it('opens from the keyboard', async () => {
    render(<Disclosure title="Ledger">row one</Disclosure>)
    screen.getByRole('button', { name: /ledger/i }).focus()
    await userEvent.keyboard('{Enter}')
    expect(screen.getByText('row one')).toBeInTheDocument()
  })
})

function Panels() {
  const [i, setI] = useState(0)
  return (
    <>
      <button onClick={() => setI(1)}>next</button>
      <TransitionPanel activeIndex={i}>
        {[<p key="a">first panel</p>, <p key="b">second panel</p>]}
      </TransitionPanel>
    </>
  )
}

describe('TransitionPanel', () => {
  it('shows the active panel and switches to the next', async () => {
    render(<Panels />)
    expect(screen.getByText('first panel')).toBeInTheDocument()
    await userEvent.click(screen.getByRole('button', { name: 'next' }))
    expect(await screen.findByText('second panel')).toBeInTheDocument()
    await waitFor(() => expect(screen.queryByText('first panel')).not.toBeInTheDocument())
  })
})

describe('Tilt and Magnetic', () => {
  it('render their children', () => {
    render(
      <>
        <Tilt>tilted</Tilt>
        <Magnetic>
          <button>pull</button>
        </Magnetic>
      </>,
    )
    expect(screen.getByText('tilted')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'pull' })).toBeInTheDocument()
  })
})
