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
