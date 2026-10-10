import { useQuery, useQueryClient } from '@tanstack/react-query'
import { Check } from 'lucide-react'
import { useState } from 'react'
import { toast } from 'sonner'
import { Alert } from '@/components/common/Alert'
import { EmptyState } from '@/components/common/EmptyState'
import { PageHeader } from '@/components/common/PageHeader'
import { QueryBoundary } from '@/components/common/QueryBoundary'
import { SubmitButton } from '@/components/common/SubmitButton'
import { Reveal } from '@/components/motion/Reveal'
import { Badge } from '@/components/ui/Badge'
import { Button } from '@/components/ui/Button'
import { Field, Input, Select } from '@/components/ui/Field'
import { api, call, errorMessage, type components } from '@/lib/api'
import { todayIso } from '@/lib/dates'
import { formatDate } from '@/lib/format'
import { useSubmitLock } from '@/lib/forms'

type Sheet = components['schemas']['AttendanceSheet']
type Status = components['schemas']['AttendanceEntry']['status']

const OPTIONS: { value: Status; label: string }[] = [
  { value: 'present', label: 'Present' },
  { value: 'half_day', label: 'Half day' },
  { value: 'absent', label: 'Absent' },
]

/** Mark who came to a shift. The usual day is everyone present, so that is where the sheet starts; untick the ones who did not. */
export default function Attendance() {
  const [date, setDate] = useState(todayIso)
  const [shiftId, setShiftId] = useState('')
  const shifts = useQuery({ queryKey: ['master', 'shifts'], queryFn: () => call(api.GET('/api/shifts')) })

  return (
    <>
      <PageHeader eyebrow="People" title="Attendance" description="Mark who came to a shift. Everyone starts as present; change the ones who were not." />
      <div className="stack">
        <div className="grid-fields">
          <Field label="Date">{(c) => <Input {...c} type="date" max={todayIso()} value={date} onChange={(e) => e.target.value && setDate(e.target.value)} />}</Field>
          <Field label="Shift">
            {(c) => (
              <Select {...c} value={shiftId} onChange={(e) => setShiftId(e.target.value)}>
                <option value="">Select a shift</option>
                {(shifts.data ?? []).map((s) => (
                  <option key={s.id} value={s.id}>
                    {s.name} ({s.start_time.slice(0, 5)} to {s.end_time.slice(0, 5)})
                  </option>
                ))}
              </Select>
            )}
          </Field>
        </div>
        {shiftId ? <Roster key={`${date}-${shiftId}`} date={date} shiftId={Number(shiftId)} /> : <EmptyState title="Choose a shift" description="Pick the day and the shift to see who is on the sheet." />}
      </div>
    </>
  )
}

function Roster({ date, shiftId }: { date: string; shiftId: number }) {
  const queryClient = useQueryClient()
  const key = ['people', 'attendance', date, shiftId]
  const sheet = useQuery({ queryKey: key, queryFn: () => call(api.GET('/api/attendance', { params: { query: { date, shift_id: shiftId } } })) })
  return <QueryBoundary query={sheet}>{(s) => <Sheet sheet={s} onSaved={() => queryClient.invalidateQueries({ queryKey: key })} />}</QueryBoundary>
}

function Sheet({ sheet, onSaved }: { sheet: Sheet; onSaved: () => unknown }) {
  const { run, pending } = useSubmitLock()
  const [edits, setEdits] = useState<Record<number, Status>>({})
  const [error, setError] = useState<string | null>(null)
  const statusOf = (r: Sheet['rows'][number]): Status => edits[r.worker_id] ?? r.status ?? 'present'
  const anyMarked = sheet.rows.some((r) => r.status !== null)
  const unsaved = sheet.rows.some((r) => statusOf(r) !== (r.status ?? null)) || (!anyMarked && sheet.rows.length > 0)
  const counts = { present: 0, half_day: 0, absent: 0 }
  for (const r of sheet.rows) counts[statusOf(r)] += 1

  const save = () =>
    run(async () => {
      setError(null)
      try {
        await call(api.POST('/api/attendance', { body: { date: sheet.date, shift_id: sheet.shift.id, entries: sheet.rows.map((r) => ({ worker_id: r.worker_id, status: statusOf(r) })) } }))
        toast.success(`Attendance saved for shift ${sheet.shift.name}, ${formatDate(sheet.date)}`)
        setEdits({})
        await onSaved()
      } catch (err) {
        setError(errorMessage(err))
      }
    })

  if (sheet.rows.length === 0) return <EmptyState title="No workers on the payroll" description="Add workers under People, then come back to mark them." />

  return (
    <Reveal>
      <section className="card" aria-label={`Attendance for shift ${sheet.shift.name}`}>
        <div className="card-header row">
          <h2 className="card-title">
            Shift {sheet.shift.name} · {formatDate(sheet.date)}
          </h2>
          {anyMarked ? <Badge tone="green">Saved</Badge> : <Badge tone="amber">Not marked yet</Badge>}
        </div>
        <ul className="roster">
          {sheet.rows.map((r) => (
            <li key={r.worker_id} className="roster-row">
              <span>
                <strong>{r.worker_name}</strong>
                <span className="muted text-sm"> {r.worker_code}</span>
              </span>
              <fieldset className="segmented" aria-label={`Attendance for ${r.worker_name}`}>
                {OPTIONS.map((o) => (
                  <label key={o.value} className={statusOf(r) === o.value ? `is-on is-${o.value}` : undefined}>
                    <input type="radio" name={`worker-${r.worker_id}`} value={o.value} checked={statusOf(r) === o.value} onChange={() => setEdits((e) => ({ ...e, [r.worker_id]: o.value }))} />
                    {o.label}
                  </label>
                ))}
              </fieldset>
            </li>
          ))}
        </ul>
        <div className="card-body stack-sm">
          <p className="muted text-sm" role="status">
            {counts.present} present, {counts.half_day} half day, {counts.absent} absent
          </p>
          {error && <Alert tone="error">{error}</Alert>}
          <div className="row">
            <SubmitButton pending={pending} onClick={() => void save()} disabled={!unsaved}>
              <Check size={16} aria-hidden /> Save attendance
            </SubmitButton>
            <Button variant="secondary" onClick={() => setEdits(Object.fromEntries(sheet.rows.map((r) => [r.worker_id, 'present' as Status])))}>
              Mark everyone present
            </Button>
          </div>
        </div>
      </section>
    </Reveal>
  )
}
