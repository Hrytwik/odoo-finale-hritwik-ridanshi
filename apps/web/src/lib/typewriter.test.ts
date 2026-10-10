import { describe, expect, it } from 'vitest'
import { TIMING, startState, step, type TypeState } from './typewriter'

const PHRASES = ['ab', 'xyz']

describe('typewriter steps', () => {
  it('starts with the first phrase fully shown', () => {
    expect(startState(PHRASES)).toEqual({ index: 0, length: 2, phase: 'holding' })
  })

  it('rests, then deletes one letter at a time', () => {
    let s: TypeState = startState(PHRASES)
    let r = step(s, PHRASES)
    expect(r.next.phase).toBe('deleting')
    s = r.next
    r = step(s, PHRASES)
    expect(r.next).toMatchObject({ length: 1, phase: 'deleting' })
    expect(r.delay).toBe(TIMING.remove)
    r = step(r.next, PHRASES)
    expect(r.next).toMatchObject({ length: 0, phase: 'waiting' })
    expect(r.delay).toBe(TIMING.wait)
  })

  it('moves on to the next phrase and types it letter by letter', () => {
    let r = step({ index: 0, length: 0, phase: 'waiting' }, PHRASES)
    expect(r.next).toEqual({ index: 1, length: 0, phase: 'typing' })
    r = step(r.next, PHRASES)
    expect(r.next.length).toBe(1)
    expect(r.delay).toBe(TIMING.type)
    r = step(r.next, PHRASES)
    r = step(r.next, PHRASES)
    expect(r.next).toMatchObject({ length: 3, phase: 'holding' })
    expect(r.delay).toBe(TIMING.hold)
  })

  it('goes back to the first phrase after the last', () => {
    const r = step({ index: 1, length: 0, phase: 'waiting' }, PHRASES)
    expect(r.next.index).toBe(0)
  })

  it('never runs past the end of a phrase or below zero', () => {
    expect(step({ index: 0, length: 2, phase: 'typing' }, PHRASES).next.length).toBe(2)
    expect(step({ index: 0, length: 0, phase: 'deleting' }, PHRASES).next.length).toBe(0)
  })
})
