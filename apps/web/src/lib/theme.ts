import { useSyncExternalStore } from 'react'

/** Light is the main look. Dark is the same forest and sage palette on a night background, for the floor at night. */
export const THEMES = ['light', 'dark'] as const
export type Theme = (typeof THEMES)[number]

const KEY = 'everest-theme'
const EVENT = 'everest:theme'
const DEFAULT: Theme = 'light'

const isTheme = (v: unknown): v is Theme => THEMES.includes(v as Theme)

/** The saved choice, or light. Browser storage can be blocked, so every access is guarded. */
export function getTheme(): Theme {
  try {
    const saved = localStorage.getItem(KEY)
    if (isTheme(saved)) return saved
  } catch {
    // storage blocked: fall through to the default
  }
  return DEFAULT
}

/** Puts the theme on the page (the CSS reads `data-theme`) without remembering it. */
export function applyTheme(theme: Theme) {
  document.documentElement.dataset.theme = theme
}

export function setTheme(theme: Theme) {
  try {
    localStorage.setItem(KEY, theme)
  } catch {
    // not remembered, but still applied for this visit
  }
  applyTheme(theme)
  window.dispatchEvent(new CustomEvent(EVENT))
}

export const nextTheme = (current: Theme): Theme => (current === 'light' ? 'dark' : 'light')

export function subscribeTheme(listener: () => void) {
  window.addEventListener(EVENT, listener)
  return () => window.removeEventListener(EVENT, listener)
}

/** The current theme, updating when it is switched. */
export function useTheme(): Theme {
  return useSyncExternalStore(subscribeTheme, getTheme, () => DEFAULT)
}
