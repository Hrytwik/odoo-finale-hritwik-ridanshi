import { render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import { PhotoWithBoxes } from './PhotoWithBoxes'

const BOXES = [
  { x: 0.42, y: 0.31, w: 0.08, h: 0.07, defect_type: 'hole', confidence: 0.91 },
  { x: 0.1, y: 0.6, w: 0.2, h: 0.1, defect_type: 'stain', confidence: 0.55 },
] as const

describe('PhotoWithBoxes', () => {
  it('shows the photo with a description', () => {
    render(<PhotoWithBoxes src="/api/uploads/a.jpg" boxes={[]} alt="Cloth under inspection" />)
    expect(screen.getByRole('img', { name: 'Cloth under inspection' })).toHaveAttribute('src', '/api/uploads/a.jpg')
  })

  it('places each box using the 0 to 1 fractions as percentages of the photo', () => {
    render(<PhotoWithBoxes src="/x.jpg" boxes={[...BOXES]} alt="Cloth" />)
    const hole = screen.getByTestId('box-0')
    expect(hole).toHaveStyle({ left: '42%', top: '31%', width: '8%', height: '7%' })
    expect(screen.getByTestId('box-1')).toHaveStyle({ left: '10%', top: '60%', width: '20%', height: '10%' })
  })

  it('labels each box with the defect and how sure the model is', () => {
    render(<PhotoWithBoxes src="/x.jpg" boxes={[...BOXES]} alt="Cloth" />)
    expect(screen.getByText('Hole 91%')).toBeInTheDocument()
    expect(screen.getByText('Stain 55%')).toBeInTheDocument()
  })

  it('shows no boxes when there are none', () => {
    render(<PhotoWithBoxes src="/x.jpg" boxes={[]} alt="Cloth" />)
    expect(screen.queryByTestId('box-0')).not.toBeInTheDocument()
  })
})
