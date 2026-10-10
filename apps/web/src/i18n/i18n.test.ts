import { describe, expect, it } from 'vitest'
import { en, type Key } from './en'
import { LANGUAGES } from './languages'
import { locales } from './locales'
import { translate } from './translate'

const keys = Object.keys(en) as Key[]
const blanks = (text: string) => (text.match(/\{\w+\}/g) ?? []).sort().join(',')
const others = LANGUAGES.filter((l) => l.code !== 'en')

describe('languages', () => {
  it('lists English plus nine Indian languages, Hindi included', () => {
    expect(LANGUAGES.map((l) => l.code)).toEqual(['en', 'hi', 'kn', 'ta', 'te', 'mr', 'bn', 'gu', 'ml', 'pa'])
  })

  it.each(others)('$english translates every sentence, with no empty ones', ({ code }) => {
    const own = locales[code] ?? {}
    expect(keys.filter((k) => !own[k]?.trim())).toEqual([])
    expect(Object.keys(own).filter((k) => !(k in en))).toEqual([])
  })

  it.each(others)('$english keeps every {blank} the English sentence has', ({ code }) => {
    const own = locales[code] ?? {}
    expect(keys.filter((k) => blanks(own[k] ?? '') !== blanks(en[k]))).toEqual([])
  })

  it('falls back to English for a sentence a language lacks, and fills the blanks', () => {
    expect(translate('en', 'floor.downSince', { time: '9:30' })).toBe('Down since 9:30')
    expect(translate('hi', 'floor.downSince', { time: '9:30' })).toContain('9:30')
  })
})
