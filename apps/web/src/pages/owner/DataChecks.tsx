import { ShieldAlert } from 'lucide-react'
import { Disclosure } from '@/components/motion/Disclosure'
import { Badge } from '@/components/ui/Badge'
import { Table } from '@/components/ui/Table'
import { formatDate } from '@/lib/format'
import { groupWarnings } from '@/lib/warnings'

const plural = (n: number, one: string, many: string) => `${n} ${n === 1 ? one : many}`

/**
 * What to be careful about in this month's numbers, as a short summary with the detail one click away,
 * instead of one line per run. Cautions the screen does not recognise are always shown in full.
 */
export function DataChecks({ warnings }: { warnings: string[] }) {
  if (warnings.length === 0) return null
  const g = groupWarnings(warnings)
  const hours = g.attendance.reduce((n, a) => n + a.hours, 0)
  const nothing = g.attendance.length + g.provisional.length + g.other.length === 0
  if (nothing) return null
  return (
    <section className="data-checks" aria-label="Check before you rely on these numbers">
      <header className="data-checks-head">
        <ShieldAlert size={20} aria-hidden />
        <div>
          <h2 className="data-checks-title">Check before you rely on these numbers</h2>
          <p className="muted text-sm">The month is worked out from what was recorded. These gaps can move the figures.</p>
        </div>
      </header>
      <div className="data-checks-chips">
        {g.attendance.length > 0 && <Badge tone="amber">{plural(g.attendance.length, 'run', 'runs')} with attendance gaps ({Math.round(hours * 10) / 10} h)</Badge>}
        {g.provisional.length > 0 && <Badge tone="blue">{plural(g.provisional.length, 'run is', 'runs are')} still going, so cost is provisional</Badge>}
      </div>
      {g.other.length > 0 && (
        <ul className="plain-list data-checks-other">
          {g.other.map((w) => (
            <li key={w}>{w}</li>
          ))}
        </ul>
      )}
      {(g.attendance.length > 0 || g.provisional.length > 0) && (
        <Disclosure title="See which runs" meta={plural(g.attendance.length + g.provisional.length, 'note', 'notes')}>
          <div className="stack">
            {g.attendance.length > 0 && (
              <div className="stack-sm">
                <h3>Attendance gaps</h3>
                <p className="muted text-sm">Nobody was marked present for the whole run, so labour cost may be too low. Mark attendance for these shifts.</p>
                <Table>
                  <thead>
                    <tr>
                      <th>Run</th>
                      <th>Machine</th>
                      <th>Date</th>
                      <th className="num">Hours not covered</th>
                    </tr>
                  </thead>
                  <tbody>
                    {g.attendance.map((a) => (
                      <tr key={a.run}>
                        <td>#{a.run}</td>
                        <td>{a.machine}</td>
                        <td className="nowrap">{formatDate(a.date)}</td>
                        <td className="num">{a.hours} h</td>
                      </tr>
                    ))}
                  </tbody>
                </Table>
              </div>
            )}
            {g.provisional.length > 0 && (
              <div className="stack-sm">
                <h3>Runs still going</h3>
                <p className="muted text-sm">These runs have not ended, so their cost is counted up to now and will grow.</p>
                <Table>
                  <thead>
                    <tr>
                      <th>Run</th>
                      <th>Machine</th>
                      <th>Started</th>
                    </tr>
                  </thead>
                  <tbody>
                    {g.provisional.map((p) => (
                      <tr key={p.run}>
                        <td>#{p.run}</td>
                        <td>{p.machine}</td>
                        <td className="nowrap">{formatDate(p.date)}</td>
                      </tr>
                    ))}
                  </tbody>
                </Table>
              </div>
            )}
          </div>
        </Disclosure>
      )}
    </section>
  )
}
