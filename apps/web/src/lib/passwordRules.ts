/** The rules for a new password, the same ones the server enforces, so a person hears what is wrong before anything is sent. */
export const MIN_LENGTH = 8
export const MAX_BYTES = 72

const COMMON = new Set([
  'password', 'password1', 'password123', '12345678', '123456789', '1234567890', 'qwertyui', 'qwerty123',
  'iloveyou', 'admin123', 'letmein1', 'welcome1', 'abc12345', '11111111', '00000000',
])

/** Why this password is not allowed, in words for the person choosing it, or null if it is fine. */
export function passwordProblem(password: string, username: string): string | null {
  if (password.length < MIN_LENGTH) return `Use at least ${MIN_LENGTH} characters`
  if (new TextEncoder().encode(password).length > MAX_BYTES) return `Use at most ${MAX_BYTES} bytes (about ${MAX_BYTES} letters and numbers)`
  if (!/[A-Za-z]/.test(password) || !/\d/.test(password)) return 'Use both letters and at least one number'
  if (COMMON.has(password.toLowerCase())) return 'That password is too common. Choose another'
  if (username.length >= 3 && password.toLowerCase().includes(username.toLowerCase())) return 'Do not put your username in your password'
  return null
}
