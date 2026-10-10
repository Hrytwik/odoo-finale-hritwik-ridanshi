import { useQueryClient } from '@tanstack/react-query'
import { Link, useNavigate } from 'react-router-dom'
import wovenUrl from '@/assets/art/woven-plaid.svg'
import { BrandMark } from '@/components/common/BrandMark'
import { Typewriter } from '@/components/motion/Typewriter'
import { homeFor } from '@/lib/nav'
import { SignupForm } from './SignupForm'

// the same sentence twice: the effect types it, holds, deletes and types it again, so the words never change
const PHRASES = ['roll by roll.', 'roll by roll.']

/** The page where a buyer creates their own login. Staff logins are made by the owner, so this is for buyers only. */
export function SignupScreen() {
  const navigate = useNavigate()
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
            <Typewriter before="Follow your orders," phrases={PHRASES} />
            <p style={{ maxWidth: '40ch' }}>See where each order stands, when it should reach you, and ask questions in plain words.</p>
          </div>
        </div>
      </section>

      <section className="login-panel">
        <div className="login-wrap">
          <div className="login-card">
            <div className="card-body stack">
              <div className="stack-sm">
                <p className="eyebrow">For buyers</p>
                <h1>Create your account</h1>
                <p className="muted text-sm">Use the email the mill has for your company and the invite code they gave you.</p>
              </div>
              <SignupForm
                onSuccess={(me) => {
                  queryClient.setQueryData(['me'], me)
                  navigate(homeFor(me.role), { replace: true })
                }}
              />
              <p className="muted text-sm">
                Already have an account? <Link to="/login">Log in</Link>
              </p>
            </div>
          </div>
        </div>
      </section>
    </main>
  )
}
