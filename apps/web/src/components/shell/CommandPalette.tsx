import { CornerDownLeft, Search } from 'lucide-react'
import { useEffect, useId, useMemo, useRef, useState, type KeyboardEvent } from 'react'
import { useNavigate } from 'react-router-dom'
import { Dialog } from '@/components/ui/Dialog'
import type { Key } from '@/i18n/en'
import { useI18n } from '@/i18n/I18nContext'
import { jumpTargets, pageResults } from '@/lib/palette'
import type { Role } from '@/lib/nav'

type Result = { key: string; label: string; href: string; hint: string; Icon?: React.ComponentType<{ size?: number; 'aria-hidden'?: boolean }> }

/** Ctrl+K: jump to any page in your menu, or straight to a roll, order, lot, dispatch or invoice by typing its code. */
export function CommandPalette({ open, onClose, role }: { open: boolean; onClose: () => void; role: Role }) {
  const { t } = useI18n()
  return (
    <Dialog open={open} onClose={onClose} title={t('palette.title')}>
      <Palette onClose={onClose} role={role} />
    </Dialog>
  )
}

function Palette({ onClose, role }: { onClose: () => void; role: Role }) {
  const { t } = useI18n()
  const navigate = useNavigate()
  const input = useRef<HTMLInputElement>(null)
  const listId = useId()
  const [query, setQuery] = useState('')
  const [active, setActive] = useState(0)

  // the dialog moves focus to its own panel when it opens; take it back for the search box afterwards
  useEffect(() => {
    const id = window.setTimeout(() => input.current?.focus(), 0)
    return () => window.clearTimeout(id)
  }, [])

  const results = useMemo<Result[]>(
    () => [
      ...jumpTargets(query, role).map((j) => ({ key: `jump:${j.href}`, label: t(`palette.open.${j.kind}` as Key, { code: j.code }), href: j.href, hint: t('palette.go') })),
      ...pageResults(query, role, { label: (i) => t(i.labelKey), group: (i) => t(`nav.group.${i.group}` as Key) }).map((p) => ({ key: p.href, label: t(p.labelKey), href: p.href, hint: t(`nav.group.${p.group}` as Key), Icon: p.icon })),
    ],
    [query, role, t],
  )
  const clamped = Math.min(active, Math.max(0, results.length - 1))

  function choose(r: Result | undefined) {
    if (!r) return
    navigate(r.href)
    onClose()
  }

  function onKeyDown(e: KeyboardEvent<HTMLInputElement>) {
    if (e.key === 'ArrowDown') {
      e.preventDefault()
      setActive(Math.min(clamped + 1, results.length - 1))
    } else if (e.key === 'ArrowUp') {
      e.preventDefault()
      setActive(Math.max(clamped - 1, 0))
    } else if (e.key === 'Enter') {
      e.preventDefault()
      choose(results[clamped])
    }
  }

  return (
    <div className="palette">
      <div className="palette-input">
        <Search size={16} aria-hidden />
        <input
          ref={input}
          role="combobox"
          aria-expanded="true"
          aria-controls={listId}
          aria-activedescendant={results[clamped] ? `${listId}-${clamped}` : undefined}
          aria-label={t('palette.placeholder')}
          placeholder={t('palette.placeholder')}
          autoComplete="off"
          value={query}
          onChange={(e) => {
            setQuery(e.target.value)
            setActive(0)
          }}
          onKeyDown={onKeyDown}
        />
      </div>
      <ul id={listId} role="listbox" className="palette-list">
        {results.map((r, i) => (
          <li
            key={r.key}
            id={`${listId}-${i}`}
            role="option"
            aria-selected={i === clamped}
            className={i === clamped ? 'palette-item is-active' : 'palette-item'}
            onMouseMove={() => setActive(i)}
            onClick={() => choose(r)}
          >
            {r.Icon ? <r.Icon size={16} aria-hidden /> : <CornerDownLeft size={16} aria-hidden />}
            <span className="palette-label">{r.label}</span>
            <span className="palette-hint">{r.hint}</span>
          </li>
        ))}
      </ul>
      {results.length === 0 && <p className="muted text-sm palette-empty">{t('palette.empty')}</p>}
    </div>
  )
}
