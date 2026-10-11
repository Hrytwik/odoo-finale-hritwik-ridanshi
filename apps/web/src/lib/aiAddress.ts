import type { Key } from '@/i18n/en'

/** Why an address cannot work (a translation key), or null. Catches the usual slip: pasting the provider's website instead of its API address. */
export function addressProblem(address: string): Key | null {
  const text = address.trim()
  if (!text) return 'aiset.addr.enter'
  let url: URL
  try {
    url = new URL(text)
  } catch {
    return 'aiset.addr.notWeb'
  }
  if (url.protocol !== 'https:' && url.protocol !== 'http:') return 'aiset.addr.notWeb'
  if (/^(console|platform|www)\./.test(url.hostname) || /\/(keys|api-keys|settings)\/?$/.test(url.pathname)) {
    return 'aiset.addr.page'
  }
  return null
}
