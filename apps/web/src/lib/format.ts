import { LANGUAGES, type LangCode } from '@/i18n/languages'

const IST = 'Asia/Kolkata'
const qty = new Intl.NumberFormat('en-IN', { maximumFractionDigits: 1 })
const money = new Intl.NumberFormat('en-IN', { style: 'currency', currency: 'INR', maximumFractionDigits: 0 })

/** The unit words people read in each language: metre, kilo, lakh and crore. English is the base. */
const UNITS: Record<LangCode, { m: string; kg: string; lakh: string; crore: string }> = {
  en: { m: 'm', kg: 'kg', lakh: 'L', crore: 'Cr' },
  hi: { m: 'मी', kg: 'किलो', lakh: 'लाख', crore: 'करोड़' },
  kn: { m: 'ಮೀ', kg: 'ಕೆಜಿ', lakh: 'ಲಕ್ಷ', crore: 'ಕೋಟಿ' },
  ta: { m: 'மீ', kg: 'கிலோ', lakh: 'லட்சம்', crore: 'கோடி' },
  te: { m: 'మీ', kg: 'కిలో', lakh: 'లక్ష', crore: 'కోటి' },
  mr: { m: 'मी', kg: 'किलो', lakh: 'लाख', crore: 'कोटी' },
  bn: { m: 'মি', kg: 'কেজি', lakh: 'লাখ', crore: 'কোটি' },
  gu: { m: 'મી', kg: 'કિલો', lakh: 'લાખ', crore: 'કરોડ' },
  ml: { m: 'മീ', kg: 'കിലോ', lakh: 'ലക്ഷം', crore: 'കോടി' },
  pa: { m: 'ਮੀ', kg: 'ਕਿਲੋ', lakh: 'ਲੱਖ', crore: 'ਕਰੋੜ' },
}

let current: LangCode = 'en'
type DateFormats = { day: Intl.DateTimeFormat; dayTime: Intl.DateTimeFormat }
const dateCache = new Map<LangCode, DateFormats>()

/** Called by the language provider, so numbers keep Latin digits but dates and units read in the chosen language. */
export function setFormatLanguage(code: LangCode) {
  current = code
}

function dates(): DateFormats {
  const hit = dateCache.get(current)
  if (hit) return hit
  const speech = LANGUAGES.find((l) => l.code === current)?.speech ?? 'en-IN'
  const make = (options: Intl.DateTimeFormatOptions) => {
    try {
      return new Intl.DateTimeFormat(`${speech}-u-nu-latn`, { ...options, timeZone: IST })
    } catch {
      return new Intl.DateTimeFormat('en-IN', { ...options, timeZone: IST })
    }
  }
  const formats = {
    day: make({ day: 'numeric', month: 'short', year: 'numeric' }),
    dayTime: make({ day: 'numeric', month: 'short', hour: 'numeric', minute: '2-digit' }),
  }
  dateCache.set(current, formats)
  return formats
}

/** The locale for month names and the like, with Latin digits. */
export const formatLocale = () => `${LANGUAGES.find((l) => l.code === current)?.speech ?? 'en-IN'}-u-nu-latn`

export const formatKg = (n: number) => `${qty.format(n)} ${UNITS[current].kg}`
export const formatMetres = (n: number) => `${qty.format(n)} ${UNITS[current].m}`
export const formatQty = (n: number, unit: 'kg' | 'm') => (unit === 'kg' ? formatKg(n) : formatMetres(n))
export const unitWord = (unit: 'kg' | 'm') => UNITS[current][unit]
export const formatMoney = (n: number) => money.format(n)
export const formatDate = (iso: string) => dates().day.format(new Date(iso))
export const formatDateTime = (iso: string) => dates().dayTime.format(new Date(iso))

/** Money in the way a mill owner says it: ₹42.8 L for lakhs, ₹1.2 Cr for crores, whole rupees below a lakh. */
export function formatLakh(n: number): string {
  const sign = n < 0 ? '-' : ''
  const abs = Math.abs(n)
  const trim = (x: number) => String(Math.round(x * 10) / 10)
  if (abs >= 1e7) return `${sign}₹${trim(abs / 1e7)} ${UNITS[current].crore}`
  if (abs >= 1e5) return `${sign}₹${trim(abs / 1e5)} ${UNITS[current].lakh}`
  return formatMoney(n)
}

/** 0.456 becomes "46%". */
export const formatPercent = (fraction: number) => `${Math.round(fraction * 100)}%`
