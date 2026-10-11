import { useQuery, useQueryClient } from '@tanstack/react-query'
import { CheckCircle2, ScanLine, Trash2, Truck, XCircle } from 'lucide-react'
import { useRef, useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import { ActionDialog } from '@/components/common/ActionDialog'
import { Alert } from '@/components/common/Alert'
import { EmptyState } from '@/components/common/EmptyState'
import { PageHeader } from '@/components/common/PageHeader'
import { QrScanner } from '@/components/common/QrScanner'
import { QueryBoundary } from '@/components/common/QueryBoundary'
import { StatusBadge } from '@/components/common/StatusBadge'
import { Reveal } from '@/components/motion/Reveal'
import { Badge } from '@/components/ui/Badge'
import { Button } from '@/components/ui/Button'
import { Card } from '@/components/ui/Card'
import { Field, Input } from '@/components/ui/Field'
import { ProgressBar } from '@/components/ui/ProgressBar'
import { Table } from '@/components/ui/Table'
import { useI18n } from '@/i18n/I18nContext'
import { api, call, errorMessage, type components } from '@/lib/api'
import { formatDateTime, formatMetres } from '@/lib/format'
import { parseRollCode } from '@/lib/rollCode'
import { useAction } from '@/lib/useAction'

type Dispatch = components['schemas']['DispatchOut']
type LogEntry = { id: number; ok: boolean; text: string }

export default function DispatchDetail() {
  const { code = '' } = useParams()
  const dispatch = useQuery({
    queryKey: ['dispatches', code],
    queryFn: () => call(api.GET('/api/dispatches/{dispatch_code}', { params: { path: { dispatch_code: code } } })),
    enabled: !!code,
  })
  return <QueryBoundary query={dispatch}>{(d) => <TruckPage d={d} />}</QueryBoundary>
}

function TruckPage({ d }: { d: Dispatch }) {
  const { t } = useI18n()
  const loading = d.state === 'loading'
  return (
    <>
      <PageHeader
        title={d.code}
        description={`${d.buyer.name} · ${d.vehicle_no}${d.driver_name ? ` · ${d.driver_name}` : ''}`}
        actions={loading ? <ConfirmButton d={d} /> : d.invoice_no ? <InvoiceLink no={d.invoice_no} /> : null}
      />
      <div className="stack">
        <div className="row">
          {loading ? <Badge tone="amber">{t('status.roll.loading')}</Badge> : <Badge tone="green">{t('status.roll.dispatched')}</Badge>}
          <span className="muted text-sm">
            {t(d.rolls.length === 1 ? 'dispatch.rolls.one' : 'dispatch.rolls.many', { count: d.rolls.length })} · {formatMetres(d.total_metres)}
            {d.dispatched_at ? t('dispatch.sentAt', { time: formatDateTime(d.dispatched_at) }) : ''}
          </span>
        </div>

        {d.warnings.map((w) => (
          <Alert key={w} tone="error">
            {w}
          </Alert>
        ))}

        {loading && <ScanLoad d={d} />}

        {d.orders.length > 0 && (
          <Reveal>
            <Card title={t('dispatch.ordersOnTruck')}>
              <div className="stack">
                {d.orders.map((o) => (
                  <div key={o.order_code} className="load-order">
                    <div className="row">
                      <strong>{o.order_code}</strong>
                      {o.over_shipped && <Badge tone="red">{t('dispatch.overShipping')}</Badge>}
                    </div>
                    <ProgressBar label={t('dispatch.shippedLabel', { order: o.order_code })} value={o.previously_dispatched_m + o.loaded_m} max={o.ordered_m} unit="m" tone={o.over_shipped ? 'red' : 'blue'} />
                    <p className="muted text-sm">
                      {t('dispatch.loadedLine', { loaded: formatMetres(o.loaded_m), sent: formatMetres(o.previously_dispatched_m), remaining: formatMetres(o.remaining_m), ordered: formatMetres(o.ordered_m) })}
                    </p>
                  </div>
                ))}
              </div>
            </Card>
          </Reveal>
        )}

        <Reveal>
          <Card title={t('dispatch.rollsOnTruck')}>
            {d.rolls.length === 0 ? (
              <EmptyState title={t('dispatch.nothingLoaded')} description={t('dispatch.nothingLoadedDescription')} />
            ) : (
              <Table>
                <thead>
                  <tr>
                    <th>{t('qc.col.roll')}</th>
                    <th>{t('qc.col.order')}</th>
                    <th className="num">{t('dispatch.col.metres')}</th>
                    <th>{t('qc.col.status')}</th>
                    {loading && <th />}
                  </tr>
                </thead>
                <tbody>
                  {d.rolls.map((r) => (
                    <tr key={r.code}>
                      <td>
                        <Link to={`/r/${r.code}`}>{r.code}</Link>
                      </td>
                      <td>{r.order_code}</td>
                      <td className="num">{formatMetres(r.metres)}</td>
                      <td>
                        <StatusBadge kind="roll" value={r.status} />
                      </td>
                      {loading && (
                        <td>
                          <RemoveButton dispatchCode={d.code} rollCode={r.code} />
                        </td>
                      )}
                    </tr>
                  ))}
                </tbody>
              </Table>
            )}
          </Card>
        </Reveal>
      </div>
    </>
  )
}

function InvoiceLink({ no }: { no: string }) {
  const { t } = useI18n()
  return (
    <Link to={`/invoices/${no}`}>
      <Button>{t('dispatch.openInvoice', { no })}</Button>
    </Link>
  )
}

/* ---------- scan to load ---------- */

let logId = 0

function ScanLoad({ d }: { d: Dispatch }) {
  const { t } = useI18n()
  const queryClient = useQueryClient()
  const input = useRef<HTMLInputElement>(null)
  const [text, setText] = useState('')
  const [error, setError] = useState<string | undefined>()
  const [busy, setBusy] = useState(false)
  const [scanning, setScanning] = useState(false)
  const [log, setLog] = useState<LogEntry[]>([])
  const add = (ok: boolean, line: string) => setLog((l) => [{ id: ++logId, ok, text: line }, ...l].slice(0, 8))

  async function load(raw: string) {
    const code = parseRollCode(raw)
    if (!code) return setError(t('dispatch.notRollCode'))
    setError(undefined)
    setBusy(true)
    try {
      const updated = await call(api.POST('/api/dispatches/{dispatch_code}/items', { params: { path: { dispatch_code: d.code } }, body: { roll_code: code } }))
      queryClient.setQueryData(['dispatches', d.code], updated)
      void queryClient.invalidateQueries({ queryKey: ['dispatches'], exact: true })
      add(true, t('dispatch.rollLoaded', { code }))
      setText('')
    } catch (err) {
      // the server's reason is shown as it is: not passed QC, already dispatched, wrong buyer...
      add(false, t('dispatch.rollRefused', { code, reason: errorMessage(err) }))
      setText('')
    } finally {
      setBusy(false)
      input.current?.focus()
    }
  }

  return (
    <Card title={t('dispatch.scanTitle')}>
      <div className="stack">
        <form
          className="scan-row"
          noValidate
          onSubmit={(e) => {
            e.preventDefault()
            void load(text)
          }}
        >
          <Field label={t('dispatch.rollCode')} error={error}>
            {(c) => <Input {...c} ref={input} autoFocus autoComplete="off" autoCapitalize="characters" readOnly={busy} value={text} onChange={(e) => setText(e.target.value)} />}
          </Field>
          <Button type="submit" disabled={busy}>
            <Truck size={16} aria-hidden /> {t('dispatch.loadRoll')}
          </Button>
          <Button variant="secondary" onClick={() => setScanning(true)}>
            <ScanLine size={16} aria-hidden /> {t('dispatch.scanCamera')}
          </Button>
        </form>
        <QrScanner
          open={scanning}
          onClose={() => setScanning(false)}
          onCode={(code) => {
            setScanning(false)
            void load(code)
          }}
        />
        <ol className="scan-log" role="log" aria-live="polite" aria-label={t('dispatch.scanLog')}>
          {log.map((e) => (
            <li key={e.id} className={e.ok ? 'scan-ok' : 'scan-refused'}>
              {e.ok ? <CheckCircle2 size={16} aria-hidden /> : <XCircle size={16} aria-hidden />}
              <span>{e.text}</span>
            </li>
          ))}
        </ol>
      </div>
    </Card>
  )
}

function RemoveButton({ dispatchCode, rollCode }: { dispatchCode: string; rollCode: string }) {
  const { t } = useI18n()
  const queryClient = useQueryClient()
  const { act } = useAction({ invalidate: [['rolls'], ['orders']] })
  return (
    <Button
      variant="ghost"
      icon
      aria-label={t('dispatch.removeRoll', { code: rollCode })}
      onClick={() =>
        act(async () => {
          const updated = await call(api.DELETE('/api/dispatches/{dispatch_code}/items/{roll_code}', { params: { path: { dispatch_code: dispatchCode, roll_code: rollCode } } }))
          queryClient.setQueryData(['dispatches', dispatchCode], updated)
          void queryClient.invalidateQueries({ queryKey: ['dispatches'], exact: true })
        }, t('dispatch.takenOff', { code: rollCode }))
      }
    >
      <Trash2 size={16} aria-hidden />
    </Button>
  )
}

/* ---------- confirm ---------- */

function ConfirmButton({ d }: { d: Dispatch }) {
  const { t } = useI18n()
  const [open, setOpen] = useState(false)
  const queryClient = useQueryClient()
  const { act, pending, error } = useAction({ invalidate: [['rolls'], ['orders'], ['money']], onDone: () => setOpen(false) })
  return (
    <>
      <Button disabled={d.rolls.length === 0} onClick={() => setOpen(true)}>
        <CheckCircle2 size={16} aria-hidden /> {t('dispatch.confirm')}
      </Button>
      <ActionDialog
        open={open}
        onClose={() => setOpen(false)}
        title={t('dispatch.sendTitle', { code: d.code })}
        confirmLabel={t('dispatch.confirm')}
        cancelLabel={t('dispatch.keepLoading')}
        pending={pending}
        error={error}
        onConfirm={() =>
          act(async () => {
            const sent = await call(api.POST('/api/dispatches/{dispatch_code}/confirm', { params: { path: { dispatch_code: d.code } } }))
            queryClient.setQueryData(['dispatches', d.code], sent)
            void queryClient.invalidateQueries({ queryKey: ['dispatches'], exact: true })
          }, t('dispatch.sentToast', { code: d.code }))
        }
      >
        <p>
          {t('dispatch.confirmBody', { rolls: t(d.rolls.length === 1 ? 'dispatch.rolls.one' : 'dispatch.rolls.many', { count: d.rolls.length }), metres: formatMetres(d.total_metres), buyer: d.buyer.name })}
        </p>
      </ActionDialog>
    </>
  )
}
