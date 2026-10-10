import { createContext, useContext, type Context } from 'react'
import type { Key } from './en'
import { DEFAULT_LANGUAGE, languageOf, type LangCode, type Language } from './languages'
import { translate, type Vars } from './translate'

export type I18nValue = { lang: LangCode; language: Language; setLang: (code: LangCode) => void; t: (key: Key, vars?: Vars) => string }

// While the app is being edited, the dev server reloads this file. A second copy of the context would split the provider from the
// screens, and every screen would fall back to English until the page was refreshed. Keeping one copy on the window prevents that.
const holder = globalThis as { __everestI18n?: Context<I18nValue> }

// Outside a provider (a small test, say) the app simply reads as English.
export const I18nContext: Context<I18nValue> = (holder.__everestI18n ??= createContext<I18nValue>({
  lang: DEFAULT_LANGUAGE,
  language: languageOf(DEFAULT_LANGUAGE),
  setLang: () => undefined,
  t: (key, vars) => translate(DEFAULT_LANGUAGE, key, vars),
}))

export const useI18n = () => useContext(I18nContext)
