/** Orders whose stage differs from the last time we looked. A first look (no earlier map) reports nothing. */
export function changedStages(previous: Map<string, string> | null, now: { code: string; stage: string }[]): { code: string; from: string; to: string }[] {
  if (!previous) return []
  return now.filter((o) => previous.has(o.code) && previous.get(o.code) !== o.stage).map((o) => ({ code: o.code, from: previous.get(o.code) as string, to: o.stage }))
}

/** "just now", "12 s ago", "3 min ago": how long since the data was fetched. */
export function sinceText(seconds: number): string {
  if (seconds < 5) return 'just now'
  if (seconds < 60) return `${Math.floor(seconds)} s ago`
  return `${Math.floor(seconds / 60)} min ago`
}
