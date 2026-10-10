import { motion } from 'motion/react'
import { useId } from 'react'
import { NavLink } from 'react-router-dom'
import type { Key } from '@/i18n/en'
import { useI18n } from '@/i18n/I18nContext'
import type { NavItem } from '@/lib/nav'

/** The role's menu, grouped. The active page gets a highlight that slides between items. */
export function NavList({ items, onNavigate }: { items: NavItem[]; onNavigate?: () => void }) {
  const uid = useId()
  const { t } = useI18n()
  const groups = [...new Set(items.map((i) => i.group))]
  return (
    <nav className="nav" aria-label="Main">
      {groups.map((group) => (
        <div key={group}>
          <p className="nav-group-title">{t(`nav.group.${group}` as Key)}</p>
          {items
            .filter((i) => i.group === group)
            .map((item) => (
              <NavLink key={item.href} to={item.href} onClick={onNavigate} className="nav-link">
                {({ isActive }) => (
                  <>
                    {isActive && (
                      <motion.span
                        layoutId={`nav-active-${uid}`}
                        className="ab-highlight"
                        transition={{ type: 'spring', bounce: 0.2, duration: 0.4 }}
                      />
                    )}
                    <item.icon size={16} aria-hidden style={{ position: 'relative' }} />
                    <span style={{ position: 'relative' }}>{t(item.labelKey)}</span>
                  </>
                )}
              </NavLink>
            ))}
        </div>
      ))}
    </nav>
  )
}
