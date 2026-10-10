import { LogOut, Menu } from 'lucide-react'
import { useState, type ReactNode } from 'react'
import { Link } from 'react-router-dom'
import { BrandMark } from '@/components/common/BrandMark'
import { Button } from '@/components/ui/Button'
import { Dialog } from '@/components/ui/Dialog'
import type { components } from '@/lib/api'
import { useLogout } from '@/lib/auth'
import { useLiveEvents } from '@/lib/live'
import { ROLE_LABEL, homeFor, navFor } from '@/lib/nav'
import { DemoBadge } from './DemoBadge'
import { NavList } from './NavList'

type Me = components['schemas']['Me']

export function AppShell({ me, children }: { me: Me; children: ReactNode }) {
  const [open, setOpen] = useState(false)
  const logout = useLogout()
  const items = navFor(me.role)
  useLiveEvents()

  return (
    <div className="shell">
      <header className="shell-header">
        <Button variant="ghost" icon className="menu-button" aria-label="Open menu" onClick={() => setOpen(true)}>
          <Menu size={20} aria-hidden />
        </Button>
        <Link to={homeFor(me.role)} className="brand">
          <span className="brand-mark">
            <BrandMark size={16} />
          </span>
          Everest Mills
        </Link>
        <DemoBadge />
        <div className="shell-user">
          <span className="muted text-sm shell-user-name">
            {me.display_name} · {ROLE_LABEL[me.role]}
          </span>
          <Button variant="ghost" icon aria-label="Log out" onClick={logout}>
            <LogOut size={18} aria-hidden />
          </Button>
        </div>
      </header>

      <div className="shell-body">
        <aside className="sidebar">
          <NavList items={items} />
        </aside>
        <main className="shell-main">{children}</main>
      </div>

      <div className="sidebar-drawer">
        <Dialog open={open} onClose={() => setOpen(false)} title="Menu" side="left">
          <NavList items={items} onNavigate={() => setOpen(false)} />
        </Dialog>
      </div>
    </div>
  )
}
