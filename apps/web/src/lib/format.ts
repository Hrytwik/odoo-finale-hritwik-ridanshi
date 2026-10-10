const IST = 'Asia/Kolkata'
const qty = new Intl.NumberFormat('en-IN', { maximumFractionDigits: 1 })
const money = new Intl.NumberFormat('en-IN', { style: 'currency', currency: 'INR', maximumFractionDigits: 0 })
const day = new Intl.DateTimeFormat('en-IN', { day: 'numeric', month: 'short', year: 'numeric', timeZone: IST })
const dayTime = new Intl.DateTimeFormat('en-IN', {
  day: 'numeric',
  month: 'short',
  hour: 'numeric',
  minute: '2-digit',
  timeZone: IST,
})

export const formatKg = (n: number) => `${qty.format(n)} kg`
export const formatMetres = (n: number) => `${qty.format(n)} m`
export const formatQty = (n: number, unit: 'kg' | 'm') => (unit === 'kg' ? formatKg(n) : formatMetres(n))
export const formatMoney = (n: number) => money.format(n)
export const formatDate = (iso: string) => day.format(new Date(iso))
export const formatDateTime = (iso: string) => dayTime.format(new Date(iso))

/** Money in the way a mill owner says it: ₹42.8 L for lakhs, ₹1.2 Cr for crores, whole rupees below a lakh. */
export function formatLakh(n: number): string {
  const sign = n < 0 ? '-' : ''
  const abs = Math.abs(n)
  const trim = (x: number) => String(Math.round(x * 10) / 10)
  if (abs >= 1e7) return `${sign}₹${trim(abs / 1e7)} Cr`
  if (abs >= 1e5) return `${sign}₹${trim(abs / 1e5)} L`
  return formatMoney(n)
}

/** 0.456 becomes "46%". */
export const formatPercent = (fraction: number) => `${Math.round(fraction * 100)}%`
