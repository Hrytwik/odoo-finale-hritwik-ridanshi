import { render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import { MACHINE_STATUS, ORDER_STAGE, ROLL_STATUS, StatusBadge } from './StatusBadge'

describe('StatusBadge', () => {
  it('has a non-empty label for every status the API can send', () => {
    for (const map of [MACHINE_STATUS, ROLL_STATUS, ORDER_STAGE]) {
      for (const style of Object.values(map)) expect(style.label.length).toBeGreaterThan(0)
    }
    expect(Object.keys(MACHINE_STATUS)).toHaveLength(3)
    expect(Object.keys(ROLL_STATUS)).toHaveLength(9)
    expect(Object.keys(ORDER_STAGE)).toHaveLength(10)
  })

  it('renders the human label', () => {
    render(<StatusBadge kind="roll" value="awaiting_qc" />)
    expect(screen.getByText('Awaiting QC')).toBeInTheDocument()
  })

  it('colours a down machine red and a running one green', () => {
    const { rerender } = render(<StatusBadge kind="machine" value="down" />)
    expect(screen.getByText('Down')).toHaveClass('badge-red')
    rerender(<StatusBadge kind="machine" value="running" />)
    expect(screen.getByText('Running')).toHaveClass('badge-green')
  })

  it('shows the buyer-facing order stage', () => {
    render(<StatusBadge kind="order" value="partly_dispatched" />)
    expect(screen.getByText('Partly dispatched')).toBeInTheDocument()
  })
})
