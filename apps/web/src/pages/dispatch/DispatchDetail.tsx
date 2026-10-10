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
          {loading ? <Badge tone="amber">Loading</Badge> : <Badge tone="green">Dispatched</Badge>}
          <span className="muted text-sm">
            {d.rolls.length} {d.rolls.length === 1 ? 'roll' : 'rolls'} · {formatMetres(d.total_metres)}
            {d.dispatched_at ? ` · sent ${formatDateTime(d.dispatched_at)}` : ''}
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
            <Card title="Orders on this truck">
              <div className="stack">
                {d.orders.map((o) => (
                  <div key={o.order_code} className="load-order">
                    <div className="row">
                      <strong>{o.order_code}</strong>
                      {o.over_shipped && <Badge tone="red">Over-shipping</Badge>}
                    </div>
                    <ProgressBar label={`${o.order_code} shipped`} value={o.previously_dispatched_m + o.loaded_m} max={o.ordered_m} unit="m" tone={o.over_shipped ? 'red' : 'blue'} />
                    <p className="muted text-sm">
                      Loaded now {formatMetres(o.loaded_m)} · already sent {formatMetres(o.previously_dispatched_m)} · remaining {formatMetres(o.remaining_m)} of {formatMetres(o.ordered_m)}
                    </p>
                  </div>
                ))}
              </div>
            </Card>
          </Reveal>
        )}

        <Reveal>
          <Card title="Rolls on the truck">
            {d.rolls.length === 0 ? (
              <EmptyState title="Nothing loaded yet" description="Scan a roll's QR tag, or type its code, to put it on this truck." />
            ) : (
              <Table>
                <thead>
                  <tr>
                    <th>Roll</th>
                    <th>Order</th>
                    <th className="num">Metres</th>
                    <th>Status</th>
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
  return (
    <Link to={`/invoices/${no}`}>
      <Button>Open invoice {no}</Button>
    </Link>
  )
}

/* ---------- scan to load ---------- */

let logId = 0

function ScanLoad({ d }: { d: Dispatch }) {
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
    if (!code) return setError('That is not a roll code. It looks like R-0142.')
    setError(undefined)
    setBusy(true)
    try {
      const updated = await call(api.POST('/api/dispatches/{dispatch_code}/items', { params: { path: { dispatch_code: d.code } }, body: { roll_code: code } }))
      queryClient.setQueryData(['dispatches', d.code], updated)
      void queryClient.invalidateQueries({ queryKey: ['dispatches'], exact: true })
      add(true, `${code} loaded`)
      setText('')
    } catch (err) {
      // the server's reason is shown as it is: not passed QC, already dispatched, wrong buyer...
      add(false, `${code} refused: ${errorMessage(err)}`)
      setText('')
    } finally {
      setBusy(false)
      input.current?.focus()
    }
  }

  return (
    <Card title="Scan rolls onto the truck">
      <div className="stack">
        <form
          className="scan-row"
          noValidate
          onSubmit={(e) => {
            e.preventDefault()
            void load(text)
          }}
        >
          <Field label="Roll code" error={error}>
            {(c) => <Input {...c} ref={input} autoFocus autoComplete="off" autoCapitalize="characters" readOnly={busy} value={text} onChange={(e) => setText(e.target.value)} />}
          </Field>
          <Button type="submit" disabled={busy}>
            <Truck size={16} aria-hidden /> Load roll
          </Button>
          <Button variant="secondary" onClick={() => setScanning(true)}>
            <ScanLine size={16} aria-hidden /> Scan with camera
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
        <ol className="scan-log" role="log" aria-live="polite" aria-label="Scan log">
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
  const queryClient = useQueryClient()
  const { act } = useAction({ invalidate: [['rolls'], ['orders']] })
  return (
    <Button
      variant="ghost"
      icon
      aria-label={`Remove ${rollCode}`}
      onClick={() =>
        act(async () => {
          const updated = await call(api.DELETE('/api/dispatches/{dispatch_code}/items/{roll_code}', { params: { path: { dispatch_code: dispatchCode, roll_code: rollCode } } }))
          queryClient.setQueryData(['dispatches', dispatchCode], updated)
          void queryClient.invalidateQueries({ queryKey: ['dispatches'], exact: true })
        }, `${rollCode} taken off the truck`)
      }
    >
      <Trash2 size={16} aria-hidden />
    </Button>
  )
}

/* ---------- confirm ---------- */

function ConfirmButton({ d }: { d: Dispatch }) {
  const [open, setOpen] = useState(false)
  const queryClient = useQueryClient()
  const { act, pending, error } = useAction({ invalidate: [['rolls'], ['orders'], ['money']], onDone: () => setOpen(false) })
  return (
    <>
      <Button disabled={d.rolls.length === 0} onClick={() => setOpen(true)}>
        <CheckCircle2 size={16} aria-hidden /> Confirm dispatch
      </Button>
      <ActionDialog
        open={open}
        onClose={() => setOpen(false)}
        title={`Send ${d.code}?`}
        confirmLabel="Confirm dispatch"
        cancelLabel="Keep loading"
        pending={pending}
        error={error}
        onConfirm={() =>
          act(async () => {
            const sent = await call(api.POST('/api/dispatches/{dispatch_code}/confirm', { params: { path: { dispatch_code: d.code } } }))
            queryClient.setQueryData(['dispatches', d.code], sent)
            void queryClient.invalidateQueries({ queryKey: ['dispatches'], exact: true })
          }, `${d.code} sent`)
        }
      >
        <p>
          {d.rolls.length} {d.rolls.length === 1 ? 'roll' : 'rolls'}, {formatMetres(d.total_metres)}, for {d.buyer.name}. This creates the invoice. After this the dispatch and the invoice cannot be changed.
        </p>
      </ActionDialog>
    </>
  )
}
