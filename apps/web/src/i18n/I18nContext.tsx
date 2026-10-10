import { createContext, useCallback, useContext, useEffect, useMemo, useState, type ReactNode } from 'react'
import type { Key } from './en'
import { DEFAULT_LANGUAGE, isLangCode, languageOf, type LangCode, type Language } from './languages'
import { translate, type Vars } from './translate'

const STORAGE_KEY = 'everest-lang'

type Value = { lang: LangCode; language: Language; setLang: (code: LangCode) => void; t: (key: Key, vars?: Vars) => string }

// Outside a provider (a small test, say) the app simply reads as English.
const Context = createContext<Value>({
  lang: DEFAULT_LANGUAGE,
  language: languageOf(DEFAULT_LANGUAGE),
  setLang: () => undefined,
  t: (key, vars) => translate(DEFAULT_LANGUAGE, key, vars),
})

function savedLanguage(): LangCode {
  try {
    const saved = window.localStorage.getItem(STORAGE_KEY)
    return isLangCode(saved) ? saved : DEFAULT_LANGUAGE
  } catch {
    return DEFAULT_LANGUAGE
  }
}

/** Holds the chosen language for the whole app, remembers it on this device, and tells the page which language it is in. */
export function I18nProvider({ children }: { children: ReactNode }) {
  const [lang, setLangState] = useState<LangCode>(savedLanguage)

  useEffect(() => {
    document.documentElement.lang = lang
  }, [lang])

  const setLang = useCallback((code: LangCode) => {
    setLangState(code)
    try {
      window.localStorage.setItem(STORAGE_KEY, code)
    } catch {
      // the choice still applies for this visit
    }
  }, [])

  const value = useMemo<Value>(() => ({ lang, language: languageOf(lang), setLang, t: (key, vars) => translate(lang, key, vars) }), [lang, setLang])
  return <Context.Provider value={value}>{children}</Context.Provider>
}

export const useI18n = () => useContext(Context)
