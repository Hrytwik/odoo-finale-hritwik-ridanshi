import { describe, expect, it } from 'vitest'
import { changedStages, sinceText } from './stageChanges'

describe('changedStages', () => {
  const before = new Map([['ORD-1', 'weaving'], ['ORD-2', 'dyeing']])
  it('says nothing on the first look', () => expect(changedStages(null, [{ code: 'ORD-1', stage: 'weaving' }])).toEqual([]))
  it('reports an order that moved on', () => {
    expect(changedStages(before, [{ code: 'ORD-1', stage: 'dyeing' }, { code: 'ORD-2', stage: 'dyeing' }])).toEqual([{ code: 'ORD-1', from: 'weaving', to: 'dyeing' }])
  })
  it('does not report an order that is new to the list', () => expect(changedStages(before, [{ code: 'ORD-9', stage: 'weaving' }])).toEqual([]))
})

describe('sinceText', () => {
  it('reads in plain words', () => {
    expect(sinceText(2)).toBe('just now')
    expect(sinceText(12.7)).toBe('12 s ago')
    expect(sinceText(185)).toBe('3 min ago')
  })
})
