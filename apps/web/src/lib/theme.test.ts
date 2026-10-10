import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { THEMES, applyTheme, getTheme, nextTheme, setTheme, subscribeTheme } from './theme'

beforeEach(() => {
  localStorage.clear()
  delete document.documentElement.dataset.theme
})
afterEach(() => vi.restoreAllMocks())

describe('theme', () => {
  it('has a light and a dark look', () => {
    expect(THEMES).toEqual(['light', 'dark'])
  })

  it('defaults to light', () => {
    expect(getTheme()).toBe('light')
  })

  it('remembers the choice and applies it to the page', () => {
    setTheme('dark')
    expect(getTheme()).toBe('dark')
    expect(document.documentElement.dataset.theme).toBe('dark')
    expect(localStorage.getItem('everest-theme')).toBe('dark')
  })

  it('ignores a saved value it does not know', () => {
    localStorage.setItem('everest-theme', 'neon-pink')
    expect(getTheme()).toBe('light')
  })

  it('still works when browser storage is blocked', () => {
    vi.spyOn(Storage.prototype, 'getItem').mockImplementation(() => {
      throw new Error('blocked')
    })
    vi.spyOn(Storage.prototype, 'setItem').mockImplementation(() => {
      throw new Error('blocked')
    })
    expect(getTheme()).toBe('light')
    expect(() => setTheme('dark')).not.toThrow()
    expect(document.documentElement.dataset.theme).toBe('dark')
  })

  it('applyTheme changes the page without remembering it', () => {
    applyTheme('dark')
    expect(document.documentElement.dataset.theme).toBe('dark')
    expect(localStorage.getItem('everest-theme')).toBeNull()
  })

  it('switches between the two', () => {
    expect(nextTheme('light')).toBe('dark')
    expect(nextTheme('dark')).toBe('light')
  })

  it('tells listeners when the theme changes, and stops when they unsubscribe', () => {
    const listener = vi.fn()
    const off = subscribeTheme(listener)
    setTheme('dark')
    expect(listener).toHaveBeenCalledTimes(1)
    off()
    setTheme('light')
    expect(listener).toHaveBeenCalledTimes(1)
  })
})
