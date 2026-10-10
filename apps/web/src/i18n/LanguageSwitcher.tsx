import { Check, Languages } from 'lucide-react'
import { useState } from 'react'
import { Button } from '@/components/ui/Button'
import { Dialog } from '@/components/ui/Dialog'
import { useI18n } from './I18nContext'
import { LANGUAGES } from './languages'

/** A globe button that opens the list of languages, each written in its own script. The choice is remembered on this device. */
export function LanguageSwitcher({ className }: { className?: string }) {
  const { lang, setLang, t } = useI18n()
  const [open, setOpen] = useState(false)
  const label = t('header.language')
  return (
    <>
      <Button variant="ghost" icon className={className} aria-label={label} title={label} onClick={() => setOpen(true)}>
        <Languages size={18} aria-hidden />
      </Button>
      <Dialog open={open} onClose={() => setOpen(false)} title={t('language.title')}>
        <ul className="lang-list">
          {LANGUAGES.map((l) => (
            <li key={l.code}>
              <button
                type="button"
                className="lang-option"
                lang={l.code}
                aria-pressed={l.code === lang}
                onClick={() => {
                  setLang(l.code)
                  setOpen(false)
                }}
              >
                <span>
                  <span className="lang-native">{l.native}</span>
                  {l.code !== 'en' && <span className="lang-english">{l.english}</span>}
                </span>
                {l.code === lang && <Check size={16} aria-hidden />}
              </button>
            </li>
          ))}
        </ul>
        <p className="muted text-sm" style={{ marginTop: 12 }}>
          {t('language.note')}
        </p>
      </Dialog>
    </>
  )
}
