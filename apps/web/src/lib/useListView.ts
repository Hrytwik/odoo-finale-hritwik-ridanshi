import { useMemo, useState } from 'react'

export type SortDef<T> = { key: string; label: string; value: (row: T) => string | number | null | undefined }
export type FilterDef<T> = {
  key: string
  label: string
  options: { value: string; label: string }[]
  /** True when the row belongs under the chosen option. */
  test: (row: T, value: string) => boolean
}

export type ListView<T> = {
  rows: T[]
  total: number
  query: string
  setQuery: (value: string) => void
  sorts: SortDef<T>[]
  sortKey: string
  setSortKey: (key: string) => void
  descending: boolean
  toggleDirection: () => void
  filters: FilterDef<T>[]
  filterValues: Record<string, string>
  setFilter: (key: string, value: string) => void
  active: boolean
  clear: () => void
}

const compare = (a: string | number | null | undefined, b: string | number | null | undefined) => {
  if (a == null && b == null) return 0
  if (a == null) return 1 // empty values always sink to the bottom
  if (b == null) return -1
  if (typeof a === 'number' && typeof b === 'number') return a - b
  return String(a).localeCompare(String(b), undefined, { numeric: true, sensitivity: 'base' })
}

/**
 * Search, filter and sort a list that is already loaded. Every word typed must appear somewhere in the row's text,
 * so "cotton sharma" narrows to rows that mention both.
 */
export function useListView<T>(
  source: T[] | undefined,
  options: { text: (row: T) => string; sorts?: SortDef<T>[]; filters?: FilterDef<T>[]; defaultSort?: string; defaultDescending?: boolean },
): ListView<T> {
  const sorts = options.sorts ?? []
  const filters = options.filters ?? []
  const [query, setQuery] = useState('')
  const [sortKey, setSortKey] = useState(options.defaultSort ?? '')
  const [descending, setDescending] = useState(options.defaultDescending ?? false)
  const [filterValues, setFilterValues] = useState<Record<string, string>>({})

  const rows = useMemo(() => {
    const words = query.toLowerCase().split(/\s+/).filter(Boolean)
    let out = (source ?? []).filter((row) => {
      if (words.length > 0) {
        const hay = options.text(row).toLowerCase()
        if (!words.every((w) => hay.includes(w))) return false
      }
      return filters.every((f) => !filterValues[f.key] || f.test(row, filterValues[f.key]))
    })
    const sort = sorts.find((s) => s.key === sortKey)
    if (sort) out = [...out].sort((x, y) => (descending ? -1 : 1) * compare(sort.value(x), sort.value(y)))
    return out
    // the definitions are rebuilt every render; only the data and the user's choices matter
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [source, query, sortKey, descending, filterValues])

  const active = query.trim() !== '' || Object.values(filterValues).some(Boolean)
  return {
    rows,
    total: source?.length ?? 0,
    query,
    setQuery,
    sorts,
    sortKey,
    setSortKey,
    descending,
    toggleDirection: () => setDescending((d) => !d),
    filters,
    filterValues,
    setFilter: (key, value) => setFilterValues((v) => ({ ...v, [key]: value })),
    active,
    clear: () => {
      setQuery('')
      setFilterValues({})
    },
  }
}
