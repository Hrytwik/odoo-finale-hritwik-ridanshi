import { useInfiniteQuery, useQuery, useQueryClient } from '@tanstack/react-query'
import { Camera, Download, ScanSearch } from 'lucide-react'
import { useEffect, useMemo, useState } from 'react'
import { Link } from 'react-router-dom'
import { Alert } from '@/components/common/Alert'
import { EmptyState } from '@/components/common/EmptyState'
import { KpiCard } from '@/components/common/KpiCard'
import { PhotoInput } from '@/components/common/PhotoInput'
import { PhotoWithBoxes } from '@/components/common/PhotoWithBoxes'
import { QueryBoundary } from '@/components/common/QueryBoundary'
import { AnimatedGroup } from '@/components/motion/AnimatedGroup'
import { Badge } from '@/components/ui/Badge'
import { Button } from '@/components/ui/Button'
import { Dialog } from '@/components/ui/Dialog'
import { Field, Input, Select } from '@/components/ui/Field'
import type { Key } from '@/i18n/en'
import { useI18n } from '@/i18n/I18nContext'
import { api, call, type components } from '@/lib/api'
import { formatDateTime, formatMetres } from '@/lib/format'
import { useDefectLabel } from '@/lib/useDefectLabel'
import { Inspection } from './QcInspect'

type Item = components['schemas']['LogItem']
type Verdict = Item['verdict']
type Sort = 'newest' | 'oldest' | 'order' | 'batch'
type Filters = { q: string; order: string; lot: string; verdict: '' | Verdict; from: string; to: string; overrode: boolean; withoutPhoto: boolean; sort: Sort }

const NO_FILTERS: Filters = { q: '', order: '', lot: '', verdict: '', from: '', to: '', overrode: false, withoutPhoto: false, sort: 'newest' }
const PAGE = 24
const VERDICT_LABEL: Record<Verdict, Key> = { pass: 'qc.passed', rework: 'qc.verdict.rework', reject: 'qc.rejected' }
const VERDICT_WORD: Record<Verdict, Key> = { pass: 'qc.verdictWord.pass', rework: 'qc.verdictWord.rework', reject: 'qc.verdictWord.reject' }
const TONE: Record<Verdict, 'green' | 'amber' | 'red'> = { pass: 'green', rework: 'amber', reject: 'red' }

/** The photo log: every checked photo with its order, batch, result and the inspector's remark, filterable and sortable. */
export function PhotoLog() {
  const { t } = useI18n()
  const queryClient = useQueryClient()
  const [filters, setFilters] = useState<Filters>(NO_FILTERS)
  const [search, setSearch] = useState('')
  const [open, setOpen] = useState<Item | null>(null)
  const [checking, setChecking] = useState(false)

  // typing in the search box waits a moment before it asks the server
  useEffect(() => {
    const id = window.setTimeout(() => setFilters((f) => (f.q === search ? f : { ...f, q: search })), 300)
    return () => window.clearTimeout(id)
  }, [search])

  const options = useQuery({ queryKey: ['qc', 'log', 'filters'], queryFn: () => call(api.GET('/api/qc/log/filters')) })
  const log = useInfiniteQuery({
    queryKey: ['qc', 'log', filters],
    initialPageParam: 0,
    queryFn: ({ pageParam }) =>
      call(
        api.GET('/api/qc/log', {
          params: {
            query: {
              limit: PAGE, offset: pageParam, sort: filters.sort, with_photo: !filters.withoutPhoto,
              ...(filters.q ? { q: filters.q } : {}), ...(filters.order ? { order: filters.order } : {}), ...(filters.lot ? { lot: filters.lot } : {}),
              ...(filters.verdict ? { verdict: filters.verdict } : {}), ...(filters.from ? { date_from: filters.from } : {}),
              ...(filters.to ? { date_to: filters.to } : {}), ...(filters.overrode ? { overrode_ai: true } : {}),
            },
          },
        }),
      ),
    getNextPageParam: (last, all) => {
      const shown = all.reduce((n, p) => n + p.items.length, 0)
      return shown < last.counts.total ? shown : undefined
    },
  })

  const set = <K extends keyof Filters>(key: K, value: Filters[K]) => setFilters((f) => ({ ...f, [key]: value }))
  const items = useMemo(() => log.data?.pages.flatMap((p) => p.items) ?? [], [log.data])
  const counts = log.data?.pages[0]?.counts
  const dirty = JSON.stringify(filters) !== JSON.stringify(NO_FILTERS)

  return (
    <div className="stack">
      <div className="row" style={{ justifyContent: 'space-between', flexWrap: 'wrap' }}>
        <h2>{t('vision.tab.log')}</h2>
        <div className="row">
          <Button variant="secondary" disabled={items.length === 0} onClick={() => downloadCsv(items, t)}>
            <Download size={16} aria-hidden /> {t('log.export')}
          </Button>
          <Button onClick={() => setChecking(true)}>
            <Camera size={16} aria-hidden /> {t('log.check')}
          </Button>
        </div>
      </div>

      {counts && (
        <AnimatedGroup className="grid-cards">
          <KpiCard label={t('log.checked')} value={counts.total} />
          <KpiCard label={t('qc.passed')} value={counts.passed} />
          <KpiCard label={t('qc.verdict.rework')} value={counts.rework} />
          <KpiCard label={t('qc.rejected')} value={counts.rejected} tone={counts.rejected > 0 ? 'danger' : undefined} />
          <KpiCard label={t('log.overrode')} value={counts.overrode_ai} hint={t('log.overrodeHint')} />
        </AnimatedGroup>
      )}

      <section className="card" aria-label={t('log.filters')}>
        <div className="card-body stack-sm">
          <div className="grid-fields">
            <Field label={t('log.search')}>{(c) => <Input {...c} type="search" value={search} onChange={(e) => setSearch(e.target.value)} />}</Field>
            <Field label={t('log.order')}>
              {(c) => (
                <Select {...c} value={filters.order} onChange={(e) => set('order', e.target.value)}>
                  <option value="">{t('log.allOrders')}</option>
                  {(options.data?.orders ?? []).map((o) => (
                    <option key={o.code} value={o.code}>
                      {o.code} · {o.buyer_name}
                    </option>
                  ))}
                </Select>
              )}
            </Field>
            <Field label={t('log.batch')}>
              {(c) => (
                <Select {...c} value={filters.lot} onChange={(e) => set('lot', e.target.value)}>
                  <option value="">{t('log.allBatches')}</option>
                  {(options.data?.lots ?? []).map((l) => (
                    <option key={l} value={l}>
                      {l}
                    </option>
                  ))}
                </Select>
              )}
            </Field>
            <Field label={t('log.result')}>
              {(c) => (
                <Select {...c} value={filters.verdict} onChange={(e) => set('verdict', e.target.value as Filters['verdict'])}>
                  <option value="">{t('log.allResults')}</option>
                  {(['pass', 'rework', 'reject'] as Verdict[]).map((v) => (
                    <option key={v} value={v}>
                      {t(VERDICT_LABEL[v])}
                    </option>
                  ))}
                </Select>
              )}
            </Field>
            <Field label={t('log.from')}>{(c) => <Input {...c} type="date" value={filters.from} max={filters.to || undefined} onChange={(e) => set('from', e.target.value)} />}</Field>
            <Field label={t('log.to')}>{(c) => <Input {...c} type="date" value={filters.to} min={filters.from || undefined} onChange={(e) => set('to', e.target.value)} />}</Field>
            <Field label={t('log.sort')}>
              {(c) => (
                <Select {...c} value={filters.sort} onChange={(e) => set('sort', e.target.value as Sort)}>
                  {(['newest', 'oldest', 'order', 'batch'] as Sort[]).map((s) => (
                    <option key={s} value={s}>
                      {t(`log.sort.${s}` as Key)}
                    </option>
                  ))}
                </Select>
              )}
            </Field>
          </div>
          <div className="row" style={{ flexWrap: 'wrap' }}>
            <label className="row text-sm">
              <input type="checkbox" checked={filters.overrode} onChange={(e) => set('overrode', e.target.checked)} /> {t('log.onlyOverrode')}
            </label>
            <label className="row text-sm">
              <input type="checkbox" checked={filters.withoutPhoto} onChange={(e) => set('withoutPhoto', e.target.checked)} /> {t('log.withoutPhoto')}
            </label>
            {dirty && (
              <Button
                variant="ghost"
                onClick={() => {
                  setFilters(NO_FILTERS)
                  setSearch('')
                }}
              >
                {t('log.reset')}
              </Button>
            )}
          </div>
        </div>
      </section>

      <QueryBoundary query={log}>
        {() =>
          items.length === 0 ? (
            <EmptyState title={t('log.emptyTitle')} description={t('log.emptyHint')} />
          ) : (
            <>
              <ul className="photo-grid">
                {items.map((i) => (
                  <li key={i.id}>
                    <PhotoCard item={i} onOpen={() => setOpen(i)} />
                  </li>
                ))}
              </ul>
              <div className="row" style={{ justifyContent: 'center' }}>
                <span className="muted text-sm">{t('log.showing', { shown: items.length, total: counts?.total ?? items.length })}</span>
                {log.hasNextPage && (
                  <Button variant="secondary" onClick={() => void log.fetchNextPage()} disabled={log.isFetchingNextPage}>
                    {t('log.more')}
                  </Button>
                )}
              </div>
            </>
          )
        }
      </QueryBoundary>

      {open && <PhotoDetail item={open} onClose={() => setOpen(null)} />}
      {checking && (
        <CheckDialog
          onClose={() => setChecking(false)}
          onSaved={() => {
            setChecking(false)
            void queryClient.invalidateQueries({ queryKey: ['qc'] })
          }}
        />
      )}
    </div>
  )
}

function PhotoCard({ item: i, onOpen }: { item: Item; onOpen: () => void }) {
  const { t } = useI18n()
  const label = useDefectLabel()
  return (
    <article className="photo-card">
      <button type="button" className="photo-thumb" onClick={onOpen} aria-label={t('log.viewPhoto', { code: i.roll_code })}>
        {i.photo_url ? <img src={i.photo_url} alt={t('log.photoAlt', { code: i.roll_code })} loading="lazy" /> : <span className="muted">{t('log.noPhoto')}</span>}
        <Badge tone={TONE[i.verdict]}>{t(VERDICT_LABEL[i.verdict])}</Badge>
      </button>
      <div className="photo-meta stack-sm">
        <div className="row" style={{ justifyContent: 'space-between' }}>
          <Link to={`/r/${i.roll_code}`} className="code-text">
            {i.roll_code}
          </Link>
          <span className="muted text-sm">{formatDateTime(i.inspected_at)}</span>
        </div>
        <p className="text-sm">
          <Link to={`/orders/${i.order_code}`}>{i.order_code}</Link> · {i.buyer_name}
        </p>
        <p className="muted text-sm">
          {t('log.batchLabel')}: {i.lots.length > 0 ? i.lots.join(', ') : t('log.noBatch')}
        </p>
        {i.defects.length > 0 && (
          <p className="row text-sm" style={{ flexWrap: 'wrap' }}>
            {i.defects.map((d) => (
              <Badge key={d.defect_type} tone="gray">
                {label(d.defect_type)} × {d.count}
              </Badge>
            ))}
          </p>
        )}
        <p className="text-sm photo-remark">{i.remark ? i.remark : <span className="muted">{t('log.noRemark')}</span>}</p>
        <p className="muted text-sm">
          {i.ai ? (i.overrode_ai ? t('log.modelSaid', { verdict: t(VERDICT_WORD[i.ai.verdict]) }) : t('log.modelAgreed')) : t('log.noModel')}
        </p>
      </div>
    </article>
  )
}

function PhotoDetail({ item: i, onClose }: { item: Item; onClose: () => void }) {
  const { t } = useI18n()
  const label = useDefectLabel()
  return (
    <Dialog open onClose={onClose} title={t('log.detailTitle', { code: i.roll_code, order: i.order_code })}>
      <div className="stack">
        {i.photo_url && <PhotoWithBoxes src={i.photo_url} boxes={i.ai?.boxes ?? []} alt={t('log.photoAlt', { code: i.roll_code })} />}
        <div className="row" style={{ flexWrap: 'wrap' }}>
          <Badge tone={TONE[i.verdict]}>{t(VERDICT_LABEL[i.verdict])}</Badge>
          {i.overrode_ai && i.ai && <Badge tone="amber">{t('log.modelSaid', { verdict: t(VERDICT_WORD[i.ai.verdict]) })}</Badge>}
          <span className="muted text-sm">
            {t('log.checkedBy', { name: i.inspector })} · {formatDateTime(i.inspected_at)}
          </span>
        </div>
        <p>
          {i.buyer_name} · {i.fabric}, {i.colour} · {formatMetres(i.metres)}
        </p>
        <p className="muted text-sm">
          {t('log.batchLabel')}: {i.lots.length > 0 ? i.lots.join(', ') : t('log.noBatch')}
        </p>
        {i.defects.length > 0 && <p>{i.defects.map((d) => `${label(d.defect_type)} × ${d.count}`).join(', ')}</p>}
        <div>
          <strong className="text-sm">{t('log.remark')}</strong>
          <p>{i.remark ? i.remark : <span className="muted">{t('log.noRemark')}</span>}</p>
        </div>
        <div>
          <Link to={`/r/${i.roll_code}`} onClick={onClose}>
            <Button variant="secondary">{t('log.openRoll')}</Button>
          </Link>
        </div>
      </div>
    </Dialog>
  )
}

/** Pick a roll waiting for quality check and use the full check (photo, model, verdict, remark); or just try the model on a photo. */
function CheckDialog({ onClose, onSaved }: { onClose: () => void; onSaved: () => void }) {
  const { t } = useI18n()
  const [code, setCode] = useState('')
  const queue = useQuery({ queryKey: ['qc', 'queue'], queryFn: () => call(api.GET('/api/qc/queue')) })
  const waiting = (queue.data?.rolls ?? []).filter((r) => r.status === 'awaiting_qc')
  const roll = waiting.find((r) => r.code === code)
  return (
    <Dialog open onClose={onClose} title={t('log.checkTitle')}>
      <div className="stack">
        <Field label={t('log.pickRoll')}>
          {(c) => (
            <Select {...c} value={code} onChange={(e) => setCode(e.target.value)}>
              <option value="">{t('log.noRoll')}</option>
              {waiting.map((r) => (
                <option key={r.code} value={r.code}>
                  {t('log.rollOption', { code: r.code, order: r.order_code, buyer: r.buyer_name, metres: formatMetres(r.metres) })}
                </option>
              ))}
            </Select>
          )}
        </Field>
        {queue.data && waiting.length === 0 && <Alert tone="info">{t('log.noRollsWaiting')}</Alert>}
        {roll ? <Inspection key={roll.code} roll={roll} embedded onRecorded={onSaved} /> : <TryModel />}
      </div>
    </Dialog>
  )
}

/** Upload a photo and see what the model thinks. Nothing is saved. */
function TryModel() {
  const { t } = useI18n()
  const label = useDefectLabel()
  const [preview, setPreview] = useState<string | null>(null)
  const [result, setResult] = useState<components['schemas']['AnalyzeOut'] | null>(null)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => () => void (preview && URL.revokeObjectURL(preview)), [preview])

  async function analyse(file: File) {
    setBusy(true)
    setError(null)
    setResult(null)
    try {
      const data = new FormData()
      data.append('file', file)
      const up = await call(api.POST('/api/uploads', { body: { file: file as unknown as string }, bodySerializer: () => data }))
      setResult(await call(api.POST('/api/qc/analyze', { body: { photo_path: up.path } })))
    } catch {
      setError(t('qc.inspect.analyseFailed'))
    } finally {
      setBusy(false)
    }
  }

  const s = result?.suggestion
  return (
    <div className="stack">
      <p className="muted text-sm">{t('log.tryHint')}</p>
      <Field label={t('qc.inspect.photo')}>
        {(c) => (
          <PhotoInput
            {...c}
            onFile={(file) => {
              setPreview(file ? URL.createObjectURL(file) : null)
              if (file) void analyse(file)
            }}
          />
        )}
      </Field>
      {preview && <PhotoWithBoxes src={preview} boxes={s?.boxes ?? []} alt={t('qc.inspect.photoAlt')} />}
      {busy && (
        <p className="muted" role="status">
          <ScanSearch size={16} aria-hidden /> {t('qc.inspect.analysing')}
        </p>
      )}
      {error && <Alert tone="error">{error}</Alert>}
      {result && !s && <Alert tone="info">{result.message ?? t('qc.inspect.noSuggestion')}</Alert>}
      {s && (
        <div className="stack-sm">
          <p>
            <strong>
              {t('qc.inspect.aiSuggests', { verdict: t(VERDICT_WORD[s.verdict]), found: t(s.boxes.length === 1 ? 'defect.count.one' : 'defect.count.many', { count: s.boxes.length }) })}
            </strong>{' '}
            <span className="muted text-sm">({s.model_version})</span>
          </p>
          {s.boxes.length > 0 && <p className="text-sm">{[...new Set(s.boxes.map((b) => label(b.defect_type)))].join(', ')}</p>}
          {!result?.available && <Badge tone="amber">{t('qc.inspect.unvalidated')}</Badge>}
          {result?.message && <p className="muted text-sm">{result.message}</p>}
        </div>
      )}
    </div>
  )
}

function downloadCsv(items: Item[], t: ReturnType<typeof useI18n>['t']) {
  const cell = (v: string | number) => `"${String(v).replace(/"/g, '""')}"`
  const head = [t('log.csv.roll'), t('log.order'), t('qc.col.buyer'), t('log.batchLabel'), t('log.result'), t('log.remark'), t('log.csv.inspector'), t('common.date'), t('log.csv.defects')]
  const rows = items.map((i) => [i.roll_code, i.order_code, i.buyer_name, i.lots.join(' '), t(VERDICT_LABEL[i.verdict]), i.remark ?? '', i.inspector, i.inspected_at, i.defects.map((d) => `${t(`defect.${d.defect_type}` as Key)} x${d.count}`).join('; ')])
  const csv = '﻿' + [head, ...rows].map((r) => r.map(cell).join(',')).join(String.fromCharCode(10))
  const url = URL.createObjectURL(new Blob([csv], { type: 'text/csv;charset=utf-8' }))
  const a = document.createElement('a')
  a.href = url
  a.download = 'photo-log.csv'
  a.click()
  URL.revokeObjectURL(url)
}
