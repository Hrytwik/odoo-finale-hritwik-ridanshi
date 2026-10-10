/** How the headline types: a letter every 95 ms, deletes faster, rests while the sentence is read. */
export const TIMING = { type: 95, remove: 45, hold: 1900, wait: 350 }

export type TypePhase = 'typing' | 'holding' | 'deleting' | 'waiting'
export type TypeState = { index: number; length: number; phase: TypePhase }

/** The first phrase starts fully typed, as if it had just finished. */
export function startState(phrases: string[]): TypeState {
  return { index: 0, length: phrases[0]?.length ?? 0, phase: 'holding' }
}

/** One tick of the animation: the next state, and how long to wait before the tick after it. */
export function step(state: TypeState, phrases: string[]): { next: TypeState; delay: number } {
  const full = phrases[state.index]?.length ?? 0
  switch (state.phase) {
    case 'typing': {
      const length = Math.min(state.length + 1, full)
      return length >= full
        ? { next: { ...state, length, phase: 'holding' }, delay: TIMING.hold }
        : { next: { ...state, length }, delay: TIMING.type }
    }
    case 'holding':
      return { next: { ...state, phase: 'deleting' }, delay: TIMING.remove }
    case 'deleting': {
      const length = Math.max(state.length - 1, 0)
      return length === 0
        ? { next: { ...state, length, phase: 'waiting' }, delay: TIMING.wait }
        : { next: { ...state, length }, delay: TIMING.remove }
    }
    case 'waiting':
      return { next: { index: (state.index + 1) % phrases.length, length: 0, phase: 'typing' }, delay: TIMING.type }
  }
}
