export type RunNote = { run: number; machine: string; date: string }
export type AttendanceGap = RunNote & { hours: number }
export type GroupedWarnings = { attendance: AttendanceGap[]; provisional: RunNote[]; other: string[] }

const ATTENDANCE = /^Run (\d+) \(([^,]+), (\d{4}-\d{2}-\d{2})\) has ([\d.]+) hours not covered by its operator's attendance$/
const PROVISIONAL = /^Run (\d+) \(([^,]+), (\d{4}-\d{2}-\d{2})\) is still open, so its cost is provisional$/

/**
 * The month report sends its cautions as sentences. Two kinds repeat once per run, so they are read into rows for a table;
 * anything else is kept as it is and shown in full. A gap of 0 hours is not worth a person's attention and is left out.
 */
export function groupWarnings(warnings: string[]): GroupedWarnings {
  const out: GroupedWarnings = { attendance: [], provisional: [], other: [] }
  for (const w of warnings) {
    const a = ATTENDANCE.exec(w)
    const p = PROVISIONAL.exec(w)
    if (a) {
      const hours = Number(a[4])
      if (hours > 0) out.attendance.push({ run: Number(a[1]), machine: a[2], date: a[3], hours })
    } else if (p) out.provisional.push({ run: Number(p[1]), machine: p[2], date: p[3] })
    else out.other.push(w)
  }
  return out
}
