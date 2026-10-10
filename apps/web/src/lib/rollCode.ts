const CODE = /^R-\d+$/

/**
 * Turns whatever a scan or a typed entry contains into a roll code, or null. Accepts the bare code (`R-0142`) and
 * the address printed on the QR tag (`https://host/r/R-0142`). Anything else is rejected, so a scan can never send
 * someone to another site or to the wrong roll.
 */
export function parseRollCode(text: string): string | null {
  const trimmed = text.trim()
  if (!trimmed) return null
  let candidate = trimmed
  if (/^https?:\/\//i.test(trimmed)) {
    try {
      const match = new URL(trimmed).pathname.match(/^\/r\/([^/]+)\/?$/)
      if (!match) return null
      candidate = match[1]
    } catch {
      return null
    }
  }
  candidate = candidate.toUpperCase()
  return CODE.test(candidate) ? candidate : null
}

/** The address a roll's QR tag points to. */
export function rollUrl(code: string, origin: string = window.location.origin): string {
  return `${origin}/r/${code}`
}
