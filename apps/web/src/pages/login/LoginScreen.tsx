import { useQueryClient } from '@tanstack/react-query'
import { Link, useNavigate, useSearchParams } from 'react-router-dom'
import wovenUrl from '@/assets/art/woven-plaid.svg'
import { BrandMark } from '@/components/common/BrandMark'
import { Typewriter } from '@/components/motion/Typewriter'
import { LanguageSwitcher } from '@/i18n/LanguageSwitcher'
import { useI18n } from '@/i18n/I18nContext'
import { homeFor, safeNext } from '@/lib/nav'
import { LoginForm } from './LoginForm'

/** The login page has its own sentence (the first page says "Every roll, from yarn to invoice"). The same words twice: the effect types them, holds, deletes and types them again. */
const PHRASES = ['one login away.', 'one login away.']

export function LoginScreen() {
  const navigate = useNavigate()
  const [params] = useSearchParams()
  const queryClient = useQueryClient()
  const { t } = useI18n()

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
            <Typewriter before="Your whole mill," phrases={PHRASES} />
            <p style={{ maxWidth: '40ch' }}>
              Store, floor, quality, dispatch and the books in one place. Scan a roll and see its whole life.
            </p>
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
                <p className="eyebrow">{t('login.eyebrow')}</p>
                <h1>{t('login.title')}</h1>
                <p className="muted text-sm">{t('login.intro')}</p>
              </div>
              <LoginForm
                onSuccess={(me) => {
                  queryClient.setQueryData(['me'], me)
                  navigate(safeNext(params.get('next')) ?? homeFor(me.role), { replace: true })
                }}
              />
              <p className="muted text-sm">
                {t('login.newBuyer')} <Link to="/signup">{t('login.createAccount')}</Link>
              </p>
            </div>
          </div>
        </div>
      </section>
    </main>
  )
}
