import { KeyRound, LogOut, Menu, ScanLine, Search } from 'lucide-react'
import { useEffect, useState, type ReactNode } from 'react'
import { toast } from 'sonner'
import { Link, useNavigate } from 'react-router-dom'
import { BrandMark } from '@/components/common/BrandMark'
import { QrScanner } from '@/components/common/QrScanner'
import { Button } from '@/components/ui/Button'
import { Dialog } from '@/components/ui/Dialog'
import { useI18n } from '@/i18n/I18nContext'
import { LanguageSwitcher } from '@/i18n/LanguageSwitcher'
import type { components } from '@/lib/api'
import { useLogout } from '@/lib/auth'
import { useLiveEvents } from '@/lib/live'
import { ROLE_LABEL, homeFor, navFor } from '@/lib/nav'
import { ChangePasswordDialog } from './ChangePasswordDialog'
import { CommandPalette } from './CommandPalette'
import { DemoBadge } from './DemoBadge'
import { NavList } from './NavList'
import { NotificationBell } from './NotificationBell'
import { ThemeToggle } from './ThemeToggle'

type Me = components['schemas']['Me']

/** True when the keyboard focus is somewhere text is typed, so a "/" there is just a slash. */
function isTyping(el: Element | null): boolean {
  if (!(el instanceof HTMLElement)) return false
  return el.isContentEditable || ['INPUT', 'TEXTAREA', 'SELECT'].includes(el.tagName)
}

export function AppShell({ me, children }: { me: Me; children: ReactNode }) {
  const [open, setOpen] = useState(false)
  const [palette, setPalette] = useState(false)
  const [account, setAccount] = useState(false)
  const [scanning, setScanning] = useState(false)
  const navigate = useNavigate()
  const logout = useLogout()
  const { t } = useI18n()
  const items = navFor(me.role)
  useLiveEvents()

  // "/" or Ctrl+K (Cmd+K) opens the search from anywhere
  useEffect(() => {
    function onKey(e: KeyboardEvent) {
      if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === 'k') {
        e.preventDefault()
        setPalette((p) => !p)
      } else if (e.key === '/' && !e.ctrlKey && !e.metaKey && !e.altKey && !isTyping(document.activeElement)) {
        e.preventDefault()
        setPalette(true)
      }
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [])

  return (
    <div className="shell">
      <header className="shell-header">
        <Button variant="ghost" icon className="menu-button" aria-label={t('header.menu')} onClick={() => setOpen(true)}>
          <Menu size={20} aria-hidden />
        </Button>
        <Link to={homeFor(me.role)} className="brand" aria-label="Everest Mills">
          <span className="brand-mark">
            <BrandMark size={18} />
          </span>
          <span className="brand-text" aria-hidden>
            Everest<span className="brand-more"> Mills</span>
          </span>
        </Link>
        <DemoBadge />
        <div className="shell-tools">
          <button type="button" className="header-search" aria-label={t('header.search')} onClick={() => setPalette(true)}>
            <Search size={15} aria-hidden />
            <span>{t('header.search')}</span>
            <kbd>/</kbd>
          </button>
          <Button variant="ghost" icon className="header-search-icon header-square" aria-label={t('header.search')} onClick={() => setPalette(true)}>
            <Search size={18} aria-hidden />
          </Button>
          {me.role === 'buyer' && <NotificationBell />}
          {me.role !== 'buyer' && (
            <Button variant="ghost" icon className="header-square" aria-label={t('header.scan')} title={t('header.scan')} onClick={() => setScanning(true)}>
              <ScanLine size={18} aria-hidden />
            </Button>
          )}
          <LanguageSwitcher className="header-square" />
          <ThemeToggle className="header-square" />
          <div className="shell-user">
            <span className="shell-user-name">
              <strong>{me.display_name}</strong>
              <span>{ROLE_LABEL[me.role]}</span>
            </span>
            <Button variant="ghost" icon className="header-square" aria-label={t('header.password')} title={t('header.password')} onClick={() => setAccount(true)}>
              <KeyRound size={18} aria-hidden />
            </Button>
            <Button variant="ghost" icon className="header-square" aria-label={t('header.logout')} onClick={logout}>
              <LogOut size={18} aria-hidden />
            </Button>
          </div>
        </div>
      </header>

      <div className="shell-body">
        <aside className="sidebar">
          <NavList items={items} />
        </aside>
        <main className="shell-main">{children}</main>
      </div>

      <div className="sidebar-drawer">
        <Dialog open={open} onClose={() => setOpen(false)} title={t('header.menuTitle')} side="left">
          <NavList items={items} onNavigate={() => setOpen(false)} />
        </Dialog>
      </div>
      <QrScanner
        open={scanning}
        onClose={() => setScanning(false)}
        onCode={(code) => {
          setScanning(false)
          toast.success(`Scanned roll ${code}. Opening its passport.`)
          navigate(`/r/${code}`)
        }}
      />
      <CommandPalette open={palette} onClose={() => setPalette(false)} role={me.role} />
      <ChangePasswordDialog open={account} onClose={() => setAccount(false)} username={me.username} />
    </div>
  )
}
