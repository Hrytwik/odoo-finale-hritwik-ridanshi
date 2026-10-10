import { ArrowRight, Factory, House, ScanLine, ShieldCheck, Truck, Wallet, Waypoints, type LucideIcon } from 'lucide-react'
import { Link, Navigate } from 'react-router-dom'
import millUrl from '@/assets/photos/mill-spinning-frame.jpg'
import { BrandMark } from '@/components/common/BrandMark'
import { Typewriter } from '@/components/motion/Typewriter'
import { ThemeToggle } from '@/components/shell/ThemeToggle'
import { useMe } from '@/lib/auth'
import { homeFor } from '@/lib/nav'

/** The second line of the headline: typed, held, deleted, then the next. Screen readers get the first. */
const PHRASES = ['from yarn to invoice.', 'from loom to buyer.', 'from scan to payment.']

const NAV: { href: string; label: string; icon: LucideIcon }[] = [
  { href: '#home', label: 'Home', icon: House },
  { href: '#production', label: 'Production', icon: Factory },
  { href: '#quality', label: 'Quality', icon: ShieldCheck },
  { href: '#dispatch', label: 'Dispatch', icon: Truck },
  { href: '#accounts', label: 'Accounts', icon: Wallet },
]

const FEATURES: { id: string; title: string; text: string; icon: LucideIcon }[] = [
  { id: 'production', title: 'Production', icon: Factory, text: 'See every spinning frame, loom and jigger live: who is running it, which order, and how far along it is.' },
  { id: 'quality', title: 'Quality', icon: ShieldCheck, text: 'Inspect each roll against photos with defects boxed in. Every roll keeps a passport from yarn lot to buyer.' },
  { id: 'dispatch', title: 'Dispatch', icon: ScanLine, text: 'Scan rolls onto the truck. A roll that is not ready, or not for that order, is refused on the spot.' },
  { id: 'accounts', title: 'Accounts', icon: Wallet, text: 'Invoices, what buyers owe and what you owe suppliers, kept next to the work that earned them.' },
]

export function LandingPage() {
  return (
    <div className="landing">
      <header className="landing-header">
        <Link to="/" className="brand">
          <span className="brand-mark">
            <BrandMark size={18} />
          </span>
          Everest Mills
        </Link>
        <nav className="landing-nav" aria-label="Sections">
          {NAV.map(({ href, label, icon: Icon }) => (
            <a key={href} href={href}>
              <Icon size={15} aria-hidden /> {label}
            </a>
          ))}
        </nav>
        <div className="landing-actions">
          <ThemeToggle className="header-square" />
          <Link to="/login" className="btn btn-lime landing-login">
            Log in
          </Link>
        </div>
      </header>

      <section id="home" className="landing-hero" style={{ backgroundImage: `url(${millUrl})` }}>
        <div className="landing-hero-inner">
          <span className="landing-badge">
            <Waypoints size={14} aria-hidden /> Textile mill management
          </span>
          <Typewriter as="h1" before="Every roll," phrases={PHRASES} />
          <p className="landing-lead">
            One place for the store, the floor, quality, dispatch and the books. Scan a roll and see its whole life.
          </p>
          <ul className="landing-chips">
            <li>
              <Factory size={14} aria-hidden /> Live floor board
            </li>
            <li>
              <ShieldCheck size={14} aria-hidden /> Quality passport on every roll
            </li>
            <li>
              <ScanLine size={14} aria-hidden /> Scan-to-load dispatch
            </li>
          </ul>
          <div className="landing-cta">
            <Link to="/login" className="btn btn-lime btn-lg">
              Log in <ArrowRight size={16} aria-hidden />
            </Link>
            <a href="#production" className="btn btn-light btn-lg">
              See what is inside
            </a>
          </div>
          <p className="landing-foot">Spinning · Weaving · Dyeing · Quality check · Dispatch · Accounts</p>
        </div>
      </section>

      <section className="landing-features" aria-label="What is inside">
        <div className="landing-features-grid">
          {FEATURES.map(({ id, title, text, icon: Icon }) => (
            <article key={id} id={id} className="landing-feature">
              <span className="landing-feature-icon">
                <Icon size={20} aria-hidden />
              </span>
              <h2>{title}</h2>
              <p className="muted">{text}</p>
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
