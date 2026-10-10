import { ShieldAlert } from 'lucide-react'
import { Disclosure } from '@/components/motion/Disclosure'
import { Badge } from '@/components/ui/Badge'
import { Table } from '@/components/ui/Table'
import { useI18n } from '@/i18n/I18nContext'
import { formatDate } from '@/lib/format'
import { groupWarnings } from '@/lib/warnings'

/**
 * What to be careful about in this month's numbers, as a short summary with the detail one click away,
 * instead of one line per run. Cautions the screen does not recognise are always shown in full.
 */
export function DataChecks({ warnings }: { warnings: string[] }) {
  const { t } = useI18n()
  if (warnings.length === 0) return null
  const g = groupWarnings(warnings)
  const hours = g.attendance.reduce((n, a) => n + a.hours, 0)
  const nothing = g.attendance.length + g.provisional.length + g.other.length === 0
  if (nothing) return null
  const count = (key: 'dc.runs' | 'dc.notes', n: number) => t(n === 1 ? `${key}.one` : `${key}.many`, { count: n })
  return (
    <section className="data-checks" aria-label={t('dc.title')}>
      <header className="data-checks-head">
        <ShieldAlert size={20} aria-hidden />
        <div>
          <h2 className="data-checks-title">{t('dc.title')}</h2>
          <p className="muted text-sm">{t('dc.intro')}</p>
        </div>
      </header>
      <div className="data-checks-chips">
        {g.attendance.length > 0 && <Badge tone="amber">{t('dc.attendanceChip', { runs: count('dc.runs', g.attendance.length), hours: Math.round(hours * 10) / 10 })}</Badge>}
        {g.provisional.length > 0 && <Badge tone="blue">{t(g.provisional.length === 1 ? 'dc.provisional.one' : 'dc.provisional.many', { count: g.provisional.length })}</Badge>}
      </div>
      {g.other.length > 0 && (
        <ul className="plain-list data-checks-other">
          {g.other.map((w) => (
            <li key={w}>{w}</li>
          ))}
        </ul>
      )}
      {(g.attendance.length > 0 || g.provisional.length > 0) && (
        <Disclosure title={t('dc.seeRuns')} meta={count('dc.notes', g.attendance.length + g.provisional.length)}>
          <div className="stack">
            {g.attendance.length > 0 && (
              <div className="stack-sm">
                <h3>{t('dc.attendanceGaps')}</h3>
                <p className="muted text-sm">{t('dc.attendanceText')}</p>
                <Table>
                  <thead>
                    <tr>
                      <th>{t('machine.col.run')}</th>
                      <th>{t('common.machine')}</th>
                      <th>{t('common.date')}</th>
                      <th className="num">{t('dc.hoursNotCovered')}</th>
                    </tr>
                  </thead>
                  <tbody>
                    {g.attendance.map((a) => (
                      <tr key={a.run}>
                        <td>#{a.run}</td>
                        <td>{a.machine}</td>
                        <td className="nowrap">{formatDate(a.date)}</td>
                        <td className="num">{t('owner.hours', { h: a.hours })}</td>
                      </tr>
                    ))}
                  </tbody>
                </Table>
              </div>
            )}
            {g.provisional.length > 0 && (
              <div className="stack-sm">
                <h3>{t('dc.stillGoing')}</h3>
                <p className="muted text-sm">{t('dc.stillGoingText')}</p>
                <Table>
                  <thead>
                    <tr>
                      <th>{t('machine.col.run')}</th>
                      <th>{t('common.machine')}</th>
                      <th>{t('machine.col.started')}</th>
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
