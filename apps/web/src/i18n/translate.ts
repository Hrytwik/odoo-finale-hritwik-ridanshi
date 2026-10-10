import { en, type Key } from './en'
import type { LangCode } from './languages'
import { locales } from './locales'

export type Vars = Record<string, string | number>

/** Puts {name}-style blanks into a sentence. A blank with no value is left as it is, so the gap is visible instead of silent. */
export function fill(text: string, vars?: Vars): string {
  return vars ? text.replace(/\{(\w+)\}/g, (whole, name: string) => (name in vars ? String(vars[name]) : whole)) : text
}

/** The sentence for this key in this language, or the English one when that language has no translation yet. */
export function translate(lang: LangCode, key: Key, vars?: Vars): string {
  const own = lang === 'en' ? undefined : locales[lang]?.[key]
  return fill(own && own.trim() ? own : en[key], vars)
}
