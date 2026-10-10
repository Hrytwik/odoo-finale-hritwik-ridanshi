import { ArrowRight, Factory, House, ScanLine, ShieldCheck, Truck, Wallet, Waypoints, type LucideIcon } from 'lucide-react'
import { useMemo } from 'react'
import { Link, Navigate } from 'react-router-dom'
import millUrl from '@/assets/photos/mill-spinning-frame.jpg'
import { BrandMark } from '@/components/common/BrandMark'
import { Typewriter } from '@/components/motion/Typewriter'
import { ThemeToggle } from '@/components/shell/ThemeToggle'
import type { Key } from '@/i18n/en'
import { useI18n } from '@/i18n/I18nContext'
import { LanguageSwitcher } from '@/i18n/LanguageSwitcher'
import { useMe } from '@/lib/auth'
import { homeFor } from '@/lib/nav'

const NAV: { href: string; label: Key; icon: LucideIcon }[] = [
  { href: '#home', label: 'landing.home', icon: House },
  { href: '#production', label: 'nav.group.Production', icon: Factory },
  { href: '#quality', label: 'nav.group.Quality', icon: ShieldCheck },
  { href: '#dispatch', label: 'nav.group.Dispatch', icon: Truck },
  { href: '#accounts', label: 'landing.accounts', icon: Wallet },
]

const FEATURES: { id: string; title: Key; text: Key; icon: LucideIcon }[] = [
  { id: 'production', title: 'nav.group.Production', icon: Factory, text: 'landing.feature.production' },
  { id: 'quality', title: 'nav.group.Quality', icon: ShieldCheck, text: 'landing.feature.quality' },
  { id: 'dispatch', title: 'nav.group.Dispatch', icon: ScanLine, text: 'landing.feature.dispatch' },
  { id: 'accounts', title: 'landing.accounts', icon: Wallet, text: 'landing.feature.accounts' },
]

export function LandingPage() {
  const { t } = useI18n()
  // The second line of the headline: typed, held, deleted, then the next. Screen readers get the first.
  const phrases = useMemo(() => [t('landing.phrase1'), t('landing.phrase2'), t('landing.phrase3')], [t])
  return (
    <div className="landing">
      <header className="landing-header">
        <Link to="/" className="brand">
          <span className="brand-mark">
            <BrandMark size={18} />
          </span>
          {t('brand.name')}
        </Link>
        <nav className="landing-nav" aria-label={t('landing.sections')}>
          {NAV.map(({ href, label, icon: Icon }) => (
            <a key={href} href={href}>
              <Icon size={15} aria-hidden /> {t(label)}
            </a>
          ))}
        </nav>
        <div className="landing-actions">
          <LanguageSwitcher className="header-square" />
          <ThemeToggle className="header-square" />
          <Link to="/login" className="btn btn-lime landing-login">
            {t('login.submit')}
          </Link>
        </div>
      </header>

      <section id="home" className="landing-hero" style={{ backgroundImage: `url(${millUrl})` }}>
        <div className="landing-hero-inner">
          <span className="landing-badge">
            <Waypoints size={14} aria-hidden /> {t('landing.badge')}
          </span>
          <Typewriter as="h1" before={t('landing.heroBefore')} phrases={phrases} />
          <p className="landing-lead">
            {t('landing.lead')}
          </p>
          <ul className="landing-chips">
            <li>
              <Factory size={14} aria-hidden /> {t('landing.chip1')}
            </li>
            <li>
              <ShieldCheck size={14} aria-hidden /> {t('landing.chip2')}
            </li>
            <li>
              <ScanLine size={14} aria-hidden /> {t('landing.chip3')}
            </li>
          </ul>
          <div className="landing-cta">
            <Link to="/login" className="btn btn-lime btn-lg">
              {t('login.submit')} <ArrowRight size={16} aria-hidden />
            </Link>
            <a href="#production" className="btn btn-light btn-lg">
              {t('landing.seeInside')}
            </a>
          </div>
          <p className="landing-foot">{t('landing.foot')}</p>
        </div>
      </section>

      <section className="landing-features" aria-label={t('landing.inside')}>
        <div className="landing-features-grid">
          {FEATURES.map(({ id, title, text, icon: Icon }) => (
            <article key={id} id={id} className="landing-feature">
              <span className="landing-feature-icon">
                <Icon size={20} aria-hidden />
              </span>
              <h2>{t(title)}</h2>
              <p className="muted">{t(text)}</p>
            </article>
          ))}
        </div>
      </section>
    </div>
  )
}

/**
 * The page at `/`. Visitors see the landing page; someone who is already logged in goes straight to their own home.
 * While we find out who they are the landing page is shown, so a visitor never waits on a spinner.
 */
export function LandingGate() {
  const me = useMe()
  if (me.data) return <Navigate to={homeFor(me.data.role)} replace />
  return <LandingPage />
}
