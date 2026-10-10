import { useQueryClient } from '@tanstack/react-query'
import { useNavigate, useSearchParams } from 'react-router-dom'
import meshUrl from '@/assets/art/glow-mesh.svg'
import wovenUrl from '@/assets/art/woven-plaid.svg'
import { BrandMark } from '@/components/common/BrandMark'
import { BorderTrail } from '@/components/motion/BorderTrail'
import { GlowEffect } from '@/components/motion/GlowEffect'
import { Spotlight } from '@/components/motion/Spotlight'
import { TextEffect } from '@/components/motion/TextEffect'
import { homeFor, safeNext } from '@/lib/nav'
import { LoginForm } from './LoginForm'

export function LoginScreen() {
  const navigate = useNavigate()
  const [params] = useSearchParams()
  const queryClient = useQueryClient()

  return (
    <main className="login">
      <section className="login-art spotlight-host">
        <img src={wovenUrl} alt="" />
        <Spotlight size={360} />
        <div className="login-art-copy">
          <span className="brand" style={{ color: 'var(--color-on-ink)' }}>
            <span className="brand-mark">
              <BrandMark size={16} />
            </span>
            Everest Mills
          </span>
          <div className="stack-sm">
            <TextEffect as="h2" preset="fade-in-blur" delay={0.2}>
              Every roll, from yarn to invoice.
            </TextEffect>
            <p style={{ color: 'var(--color-on-ink-muted)', maxWidth: '38ch' }}>
              One place for the store, the floor, quality, dispatch and the books. Scan a roll and see its whole life.
            </p>
          </div>
        </div>
      </section>

      <section className="login-panel" style={{ backgroundImage: `url(${meshUrl})` }}>
        <div className="login-wrap">
          <GlowEffect colors={['#14b8a6', '#0f766e', '#5eead4', '#14b8a6']} blur={36} duration={10} scale={1.05} style={{ opacity: 0.6, borderRadius: 24 }} />
          <div className="login-card">
            <BorderTrail size={90} duration={7} />
            <div className="card-body stack">
              <div className="stack-sm">
                <h1>Welcome back</h1>
                <p className="muted text-sm">Log in to continue to Everest Mills.</p>
              </div>
              <LoginForm
                onSuccess={(me) => {
                  queryClient.setQueryData(['me'], me)
                  navigate(safeNext(params.get('next')) ?? homeFor(me.role), { replace: true })
                }}
              />
            </div>
          </div>
        </div>
      </section>
    </main>
  )
}
