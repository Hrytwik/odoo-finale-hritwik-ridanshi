import { ArrowDownAZ, ArrowUpAZ, X } from 'lucide-react'
import type { ReactNode } from 'react'
import { Button } from '@/components/ui/Button'
import { Field, Input, Select } from '@/components/ui/Field'
import { useI18n } from '@/i18n/I18nContext'
import { useListView, type ListView } from '@/lib/useListView'

/** The search box, the filters and the sort choice for a list, with a count of what is shown. Needs a `useListView`. */
export function ListToolbar<T>({ view, placeholder }: { view: ListView<T>; placeholder?: string }) {
  const { t } = useI18n()
  return (
    <section className="card list-toolbar" aria-label={t('list.toolbar')}>
      <div className="card-body stack-sm">
        <div className="grid-fields">
          <Field label={t('list.search')}>
            {(c) => <Input {...c} type="search" autoComplete="off" placeholder={placeholder} value={view.query} onChange={(e) => view.setQuery(e.target.value)} />}
          </Field>
          {view.filters.map((f) => (
            <Field key={f.key} label={f.label}>
              {(c) => (
                <Select {...c} value={view.filterValues[f.key] ?? ''} onChange={(e) => view.setFilter(f.key, e.target.value)}>
                  <option value="">{t('list.all')}</option>
                  {f.options.map((o) => (
                    <option key={o.value} value={o.value}>
                      {o.label}
                    </option>
                  ))}
                </Select>
              )}
            </Field>
          ))}
          {view.sorts.length > 0 && (
            <Field label={t('list.sortBy')}>
              {(c) => (
                <span className="row" style={{ flexWrap: 'nowrap' }}>
                  <Select {...c} value={view.sortKey} onChange={(e) => view.setSortKey(e.target.value)}>
                    {view.sortKey === '' && <option value="">{t('list.sortNone')}</option>}
                    {view.sorts.map((s) => (
                      <option key={s.key} value={s.key}>
                        {s.label}
                      </option>
                    ))}
                  </Select>
                  <Button variant="secondary" icon aria-label={view.descending ? t('list.descending') : t('list.ascending')} title={view.descending ? t('list.descending') : t('list.ascending')} onClick={view.toggleDirection}>
                    {view.descending ? <ArrowDownAZ size={16} aria-hidden /> : <ArrowUpAZ size={16} aria-hidden />}
                  </Button>
                </span>
              )}
            </Field>
          )}
        </div>
        <p className="row muted text-sm" role="status">
          {t('list.shown', { shown: view.rows.length, total: view.total })}
          {view.active && (
            <Button variant="ghost" onClick={view.clear}>
              <X size={14} aria-hidden /> {t('list.clear')}
            </Button>
          )}
        </p>
      </div>
    </section>
  )
}

/** What to show in place of a list when the search or filters leave nothing. */
export function NoMatch<T>({ view }: { view: ListView<T> }) {
  const { t } = useI18n()
  if (view.rows.length > 0 || view.total === 0) return null
  return <p className="muted">{t('list.noMatch')}</p>
}

type Options<T> = Parameters<typeof useListView<T>>[1]

/** A loaded list with the toolbar above it: hands the rows left after searching, filtering and sorting to its child. */
export function Filtered<T>({ rows, options, placeholder, children }: { rows: T[]; options: Options<T>; placeholder?: string; children: (rows: T[]) => ReactNode }) {
  const view = useListView(rows, options)
  return (
    <div className="stack">
      <ListToolbar view={view} placeholder={placeholder} />
      <NoMatch view={view} />
      {children(view.rows)}
    </div>
  )
}
