import { describe, expect, it } from 'vitest'
import { matchesSearch } from './orderSearch'

const order = { code: 'ORD-0012', buyer: { name: 'Sharma Fabrics' }, fabric_type: { name: 'Poplin 58in' }, colour: 'navy', stage: 'quality_check', state: 'confirmed' } as never

describe('matchesSearch', () => {
  it('matches everything when nothing is typed', () => expect(matchesSearch(order, '  ')).toBe(true))
  it('finds an order by code, buyer, fabric, colour or stage, in any case', () => {
    for (const q of ['ord-0012', '0012', 'sharma', 'POPLIN', 'navy', 'quality check']) expect(matchesSearch(order, q), q).toBe(true)
  })
  it('needs every word to match', () => {
    expect(matchesSearch(order, 'sharma navy')).toBe(true)
    expect(matchesSearch(order, 'sharma maroon')).toBe(false)
  })
  it('does not match something that is not there', () => expect(matchesSearch(order, 'ORD-9999')).toBe(false))
})
