/** Today as YYYY-MM-DD in the browser's own calendar. Used for "not in the past" checks on date fields. */
export function todayIso(): string {
  const d = new Date()
  const pad = (n: number) => String(n).padStart(2, '0')
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}`
}
