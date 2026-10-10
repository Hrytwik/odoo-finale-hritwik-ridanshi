import { useQueryClient } from '@tanstack/react-query'
import { Link, useNavigate, useSearchParams } from 'react-router-dom'
import wovenUrl from '@/assets/art/woven-plaid.svg'
import { BrandMark } from '@/components/common/BrandMark'
import { Typewriter } from '@/components/motion/Typewriter'
import { homeFor, safeNext } from '@/lib/nav'
import { LoginForm } from './LoginForm'

/** The second line of the headline; each is typed, held, deleted, then the next. The first is what screen readers get. */
const PHRASES = ['from yarn to invoice.', 'from loom to buyer.', 'from scan to payment.']

export function LoginScreen() {
  const navigate = useNavigate()
  const [params] = useSearchParams()
  const queryClient = useQueryClient()

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
            <Typewriter before="Every roll," phrases={PHRASES} />
            <p style={{ maxWidth: '40ch' }}>
              Store, floor, quality, dispatch and the books in one place. Scan a roll and see its whole life.
            </p>
          </div>
        </div>
      </section>

      <section className="login-panel">
        <div className="login-wrap">
          <div className="login-card">
            <div className="card-body stack">
              <div className="stack-sm">
                <p className="eyebrow">Sign in</p>
                <h1>Welcome back</h1>
                <p className="muted text-sm">Log in to continue to Everest Mills.</p>
              </div>
              <LoginForm
                onSuccess={(me) => {
                  queryClient.setQueryData(['me'], me)
                  navigate(safeNext(params.get('next')) ?? homeFor(me.role), { replace: true })
                }}
              />
              <p className="muted text-sm">
                New buyer? <Link to="/signup">Create your account</Link>
              </p>
            </div>
          </div>
        </div>
      </section>
    </main>
  )
}
