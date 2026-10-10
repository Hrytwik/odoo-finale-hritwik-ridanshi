import { Fragment, useCallback, useEffect, useMemo, useState, type ReactNode } from 'react'
import { setFormatLanguage } from '@/lib/format'
import { I18nContext, type I18nValue } from './I18nContext'
import { DEFAULT_LANGUAGE, isLangCode, languageOf, type LangCode } from './languages'
import { translate } from './translate'

const STORAGE_KEY = 'everest-lang'

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
  // before anything below renders, so units and dates are already in this language
  setFormatLanguage(lang)

  useEffect(() => {
    document.documentElement.lang = lang
    document.title = translate(lang, 'brand.name')
  }, [lang])

  const setLang = useCallback((code: LangCode) => {
    setLangState(code)
    try {
      window.localStorage.setItem(STORAGE_KEY, code)
    } catch {
      // the choice still applies for this visit
    }
  }, [])

  const value = useMemo<I18nValue>(() => ({ lang, language: languageOf(lang), setLang, t: (key, vars) => translate(lang, key, vars) }), [lang, setLang])
  // keyed by language: a switch remounts the screen, so nothing keeps text, units or dates from the old language
  return (
    <I18nContext.Provider value={value}>
      <Fragment key={lang}>{children}</Fragment>
    </I18nContext.Provider>
  )
}
