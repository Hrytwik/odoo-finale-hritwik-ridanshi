import type { Key } from '@/i18n/en'
import { translate } from '@/i18n/translate'

/** The rules for a new password, the same ones the server enforces, so a person hears what is wrong before anything is sent. */
export const MIN_LENGTH = 8
export const MAX_BYTES = 72

const COMMON = new Set([
  'password', 'password1', 'password123', '12345678', '123456789', '1234567890', 'qwertyui', 'qwerty123',
  'iloveyou', 'admin123', 'letmein1', 'welcome1', 'abc12345', '11111111', '00000000',
])

export type PasswordIssue = { key: Key; vars?: { n: number } }

/** Why this password is not allowed, as a translation key (and its blanks), or null if it is fine. */
export function passwordIssue(password: string, username: string): PasswordIssue | null {
  if (password.length < MIN_LENGTH) return { key: 'pw.min', vars: { n: MIN_LENGTH } }
  if (new TextEncoder().encode(password).length > MAX_BYTES) return { key: 'pw.max', vars: { n: MAX_BYTES } }
  if (!/[A-Za-z]/.test(password) || !/\d/.test(password)) return { key: 'pw.mix' }
  if (COMMON.has(password.toLowerCase())) return { key: 'pw.common' }
  if (username.length >= 3 && password.toLowerCase().includes(username.toLowerCase())) return { key: 'pw.username' }
  return null
}

/** The same, in English words for the person choosing it, or null if it is fine. */
export function passwordProblem(password: string, username: string): string | null {
  const issue = passwordIssue(password, username)
  return issue ? translate('en', issue.key, issue.vars) : null
}
