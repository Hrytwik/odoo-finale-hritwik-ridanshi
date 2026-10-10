/** Why an address cannot work, or null. Catches the usual slip: pasting the provider's website instead of its API address. */
export function addressProblem(address: string): string | null {
  const text = address.trim()
  if (!text) return 'Enter the address of the provider'
  let url: URL
  try {
    url = new URL(text)
  } catch {
    return 'This is not a web address. It should start with https://'
  }
  if (url.protocol !== 'https:' && url.protocol !== 'http:') return 'This is not a web address. It should start with https://'
  if (/^(console|platform|www)\./.test(url.hostname) || /\/(keys|api-keys|settings)\/?$/.test(url.pathname)) {
    return 'That is a website page, not the API address. Click the Groq or OpenAI button below to fill in the right one.'
  }
  return null
}
