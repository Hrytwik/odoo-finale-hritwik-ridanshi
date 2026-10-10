import { useQueryClient } from '@tanstack/react-query'
import { useMemo } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import wovenUrl from '@/assets/art/woven-plaid.svg'
import { BrandMark } from '@/components/common/BrandMark'
import { Typewriter } from '@/components/motion/Typewriter'
import { useI18n } from '@/i18n/I18nContext'
import { LanguageSwitcher } from '@/i18n/LanguageSwitcher'
import { homeFor } from '@/lib/nav'
import { SignupForm } from './SignupForm'

/** The page where a buyer creates their own login. Staff logins are made by the owner, so this is for buyers only. */
export function SignupScreen() {
  const navigate = useNavigate()
  const queryClient = useQueryClient()
  const { t } = useI18n()
  // the same sentence twice: the effect types it, holds, deletes and types it again, so the words never change
  const phrases = useMemo(() => [t('signup.heroPhrase'), t('signup.heroPhrase')], [t])
  return (
    <main className="login">
      <section className="login-art">
        <img src={wovenUrl} alt="" />
        <div className="login-art-copy">
          <span className="brand" style={{ color: 'var(--color-on-ink)' }}>
            <span className="brand-mark">
              <BrandMark size={18} />
            </span>
            Everest Mills
          </span>
          <div className="stack-sm">
            <Typewriter before={t('signup.heroBefore')} phrases={phrases} />
            <p style={{ maxWidth: '40ch' }}>{t('signup.heroBody')}</p>
          </div>
        </div>
      </section>

      <section className="login-panel">
        <div className="login-wrap">
          <div style={{ display: 'flex', justifyContent: 'flex-end' }}>
            <LanguageSwitcher />
          </div>
          <div className="login-card">
            <div className="card-body stack">
              <div className="stack-sm">
                <p className="eyebrow">{t('signup.eyebrow')}</p>
                <h1>{t('login.createAccount')}</h1>
                <p className="muted text-sm">{t('signup.intro')}</p>
              </div>
              <SignupForm
                onSuccess={(me) => {
                  queryClient.setQueryData(['me'], me)
                  navigate(homeFor(me.role), { replace: true })
                }}
              />
              <p className="muted text-sm">
                {t('signup.haveAccount')} <Link to="/login">{t('login.submit')}</Link>
              </p>
            </div>
          </div>
        </div>
      </section>
    </main>
  )
}
