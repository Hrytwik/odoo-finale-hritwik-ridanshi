import '@testing-library/jest-dom/vitest'
import { cleanup } from '@testing-library/react'
import { afterEach } from 'vitest'

// Vitest globals are off, so Testing Library cannot register its own cleanup: unmount after every test.
afterEach(() => cleanup())

// jsdom has no IntersectionObserver (scroll-reveal animations use it). Report everything as already visible.
class VisibleObserver implements IntersectionObserver {
  readonly root = null
  readonly rootMargin = ''
  readonly scrollMargin = ''
  readonly thresholds = []
  private callback: IntersectionObserverCallback
  constructor(callback: IntersectionObserverCallback) {
    this.callback = callback
  }
  private seen = new WeakSet<Element>()
  observe(target: Element) {
    if (this.seen.has(target)) return // report each element once, and never synchronously (the caller may observe again)
    this.seen.add(target)
    setTimeout(() => this.callback([{ isIntersecting: true, target, intersectionRatio: 1 } as IntersectionObserverEntry], this), 0)
  }
  unobserve() {}
  disconnect() {}
  takeRecords() {
    return []
  }
}
globalThis.IntersectionObserver = VisibleObserver
