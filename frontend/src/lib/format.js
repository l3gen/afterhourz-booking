export const money = (cents) => `$${(cents / 100).toFixed(cents % 100 === 0 ? 0 : 2)}`

export function timeLabel(hhmm) {
  const [h, m] = hhmm.split(':').map(Number)
  const suffix = h >= 12 ? 'PM' : 'AM'
  const h12 = h % 12 === 0 ? 12 : h % 12
  return `${h12}:${String(m).padStart(2, '0')} ${suffix}`
}

// Parse YYYY-MM-DD as a local date (new Date('YYYY-MM-DD') would shift by timezone).
export function parseDay(iso) {
  const [y, m, d] = iso.split('-').map(Number)
  return new Date(y, m - 1, d)
}

export const dayLabel = (iso, opts = { weekday: 'short', month: 'short', day: 'numeric' }) =>
  parseDay(iso).toLocaleDateString('en-US', opts)

export const longDay = (iso) => dayLabel(iso, { weekday: 'long', month: 'long', day: 'numeric' })

export function toIso(date) {
  const p = (n) => String(n).padStart(2, '0')
  return `${date.getFullYear()}-${p(date.getMonth() + 1)}-${p(date.getDate())}`
}

export const WEEKDAYS = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday']
