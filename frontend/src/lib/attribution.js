// Remember where a visitor came from so the admin dashboard can show which bookings came
// from Google. Your Google Business Profile "Book" link should be:
//   https://YOURDOMAIN/book?utm_source=google&utm_medium=organic&utm_campaign=business-profile

const KEY = 'ahk_source'

export function captureSource(search = window.location.search, storage = window.sessionStorage) {
  const params = new URLSearchParams(search)
  const src = params.get('utm_source')
  if (src) {
    const value = [src, params.get('utm_medium'), params.get('utm_campaign')].filter(Boolean).join('-')
    try {
      storage.setItem(KEY, value.replace(/[^a-zA-Z0-9_.-]/g, '').slice(0, 80))
    } catch {
      /* storage unavailable, attribution is best-effort */
    }
  }
}

export function getSource(storage = window.sessionStorage) {
  try {
    return storage.getItem(KEY) || 'direct'
  } catch {
    return 'direct'
  }
}
