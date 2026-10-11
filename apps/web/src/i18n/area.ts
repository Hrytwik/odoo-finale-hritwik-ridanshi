import type { LangCode } from './languages'

/** One sentence in every language. A screen's file lists these, so a missing language is a build error, not a gap a person finds later. */
export type Entry = Record<LangCode, string>
export type Area = Record<string, Entry>

/** The English sentences of an area, to join the base list in `en.ts`. */
export function englishOf<A extends Area>(area: A): { [K in keyof A]: string } {
  return Object.fromEntries(Object.entries(area).map(([key, entry]) => [key, entry.en])) as { [K in keyof A]: string }
}

/** One language's sentences from several areas, to join that language's file. */
export function languageOf(code: Exclude<LangCode, 'en'>, ...areas: Area[]): Record<string, string> {
  const out: Record<string, string> = {}
  for (const area of areas) for (const [key, entry] of Object.entries(area)) out[key] = entry[code]
  return out
}
