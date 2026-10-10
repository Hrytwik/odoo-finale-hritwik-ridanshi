/** Which login role a worker's job maps to. Operators and helpers work the machines but do not log in: the supervisor records for them. */
export const LOGIN_ROLE_FOR_JOB: Record<string, 'qc' | 'store' | 'supervisor' | 'dispatch'> = {
  inspector: 'qc',
  storekeeper: 'store',
  supervisor: 'supervisor',
  dispatch: 'dispatch',
}

/** "Ravi Kumar" becomes ravi.k, "Imran" becomes imran. A number is added when the name is already taken. */
export function suggestUsername(fullName: string, taken: Set<string>): string {
  const words = fullName
    .toLowerCase()
    .split(/\s+/)
    .map((w) => w.replace(/[^a-z]/g, ''))
    .filter(Boolean)
  const base = words.length === 0 ? 'user' : words.length === 1 ? words[0] : `${words[0]}.${words[words.length - 1][0]}`
  if (!taken.has(base)) return base
  for (let n = 2; ; n++) if (!taken.has(`${base}${n}`)) return `${base}${n}`
}

// no 0/O, 1/l/I: a password read off a slip is not mistaken
const UPPER = 'ABCDEFGHJKLMNPQRSTUVWXYZ'
const LOWER = 'abcdefghijkmnopqrstuvwxyz'
const LETTERS = UPPER + LOWER
const DIGITS = '23456789'

/** A random 12-character password in three groups (like Kf7x-Rm3p-Wq9z), always with letters and a number. */
export function generatePassword(random: (max: number) => number = secureInt): string {
  const pick = (set: string) => set[random(set.length)]
  const chars = [pick(DIGITS), pick(UPPER), pick(LOWER)]
  const all = LETTERS + DIGITS
  while (chars.length < 12) chars.push(pick(all))
  // a random order, so the number is not always first
  for (let i = chars.length - 1; i > 0; i--) {
    const j = random(i + 1)
    ;[chars[i], chars[j]] = [chars[j], chars[i]]
  }
  const text = chars.join('')
  return `${text.slice(0, 4)}-${text.slice(4, 8)}-${text.slice(8)}`
}

/** An unbiased random whole number below `max`, from the browser's secure random source. */
function secureInt(max: number): number {
  const limit = Math.floor(0x1_0000_0000 / max) * max
  const buffer = new Uint32Array(1)
  do crypto.getRandomValues(buffer)
  while (buffer[0] >= limit)
  return buffer[0] % max
}

const escapeHtml = (s: string) => s.replace(/[&<>"']/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' })[c] as string)

/** The words on the slip, in the language the owner is using (English when not given). */
export type SlipWords = { brand: string; loginFor: (name: string) => string; address: string; username: string; password: string; changeAfter: string }
const ENGLISH_SLIP: SlipWords = { brand: 'Everest Mills', loginFor: (name) => `Login for ${name}`, address: 'Address', username: 'Username', password: 'Temporary password', changeAfter: 'Please change this password after you log in (the key icon at the top).' }

/** The text of a small slip to hand over: name, username and the temporary password. */
export function slipHtml(name: string, username: string, password: string, address: string, words: SlipWords = ENGLISH_SLIP): string {
  return `<!doctype html><meta charset="utf-8"><title>${escapeHtml(words.loginFor(name))}</title>
<style>body{font:16px/1.5 system-ui,sans-serif;padding:32px;max-width:420px}h1{font-size:20px;margin:0 0 4px}p{margin:4px 0 16px;color:#444}
dl{border:2px solid #222;border-radius:8px;padding:16px;margin:0}dt{font-size:12px;text-transform:uppercase;color:#666}dd{margin:0 0 12px;font:600 20px ui-monospace,monospace}</style>
<h1>${escapeHtml(words.brand)}</h1><p>${escapeHtml(words.loginFor(name))}</p>
<dl><dt>${escapeHtml(words.address)}</dt><dd>${escapeHtml(address)}</dd><dt>${escapeHtml(words.username)}</dt><dd>${escapeHtml(username)}</dd><dt>${escapeHtml(words.password)}</dt><dd>${escapeHtml(password)}</dd></dl>
<p>${escapeHtml(words.changeAfter)}</p>`
}
