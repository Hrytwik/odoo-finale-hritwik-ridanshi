import { QueryClient } from '@tanstack/react-query'
import { describe, expect, it, vi } from 'vitest'
import { EVENT_KEYS, handleLiveMessage, keysFor } from './live'

describe('live events', () => {
  it('maps every backend event type', () => {
    for (const type of [
      'lot.changed',
      'stock.changed',
      'order.changed',
      'machine.changed',
      'run.changed',
      'roll.changed',
      'qc.changed',
      'dispatch.changed',
      'payment.changed',
      'attendance.changed',
      'notice.changed',
    ]) {
      expect(keysFor(type).length).toBeGreaterThan(0)
    }
    expect(Object.keys(EVENT_KEYS)).toHaveLength(11)
  })

  it('a machine change refreshes the floor board', () => {
    expect(keysFor('machine.changed')).toContainEqual(['floor'])
  })

  it('ignores unknown events and bad JSON', () => {
    const qc = new QueryClient()
    const spy = vi.spyOn(qc, 'invalidateQueries')
    handleLiveMessage(qc, '{"type":"unknown.thing","id":1}')
    handleLiveMessage(qc, 'not json')
    handleLiveMessage(qc, '{"id":1}')
    expect(spy).not.toHaveBeenCalled()
  })

  it('invalidates each mapped key once', () => {
    const qc = new QueryClient()
    const spy = vi.spyOn(qc, 'invalidateQueries')
    handleLiveMessage(qc, '{"type":"dispatch.changed","id":7}')
    expect(spy).toHaveBeenCalledTimes(keysFor('dispatch.changed').length)
    expect(spy).toHaveBeenCalledWith({ queryKey: ['dispatches'] })
  })
})
