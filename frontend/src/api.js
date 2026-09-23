// Tiny fetch wrapper. All API calls are relative (/api/...): same origin in AWS via CloudFront,
// proxied to FastAPI by Vite in development.

const TOKEN_KEY = 'ahk_token'

export const tokenStore = {
  get: () => {
    try {
      return sessionStorage.getItem(TOKEN_KEY)
    } catch {
      return null
    }
  },
  set: (t) => {
    try {
      t ? sessionStorage.setItem(TOKEN_KEY, t) : sessionStorage.removeItem(TOKEN_KEY)
    } catch {
      /* ignore */
    }
  },
}

export class ApiError extends Error {
  constructor(status, message) {
    super(message)
    this.status = status
  }
}

async function request(method, path, body) {
  const headers = {}
  const token = tokenStore.get()
  if (token) headers.Authorization = `Bearer ${token}`
  if (body !== undefined) headers['Content-Type'] = 'application/json'
  const res = await fetch(`/api${path}`, { method, headers, body: body === undefined ? undefined : JSON.stringify(body) })
  const data = await res.json().catch(() => null)
  if (!res.ok) {
    const detail = data?.detail
    const msg = typeof detail === 'string' ? detail : Array.isArray(detail) ? detail.map((d) => d.msg).join('; ') : 'Something went wrong'
    throw new ApiError(res.status, msg)
  }
  return data
}

export const api = {
  siteConfig: () => request('GET', '/site-config'),
  services: () => request('GET', '/services'),
  openDays: () => request('GET', '/open-days'),
  availability: (serviceId, date) => request('GET', `/availability?service_id=${encodeURIComponent(serviceId)}&date=${date}`),
  googleLogin: (credential) => request('POST', '/auth/google', { credential }),
  devLogin: (email, name) => request('POST', '/auth/dev-login', { email, name }),
  me: () => request('GET', '/auth/me'),
  book: (payload) => request('POST', '/appointments', payload),
  mine: () => request('GET', '/appointments/mine'),
  appointment: (id) => request('GET', `/appointments/${id}`),
  cancel: (id) => request('POST', `/appointments/${id}/cancel`),
  adminAppointments: (from, to) => request('GET', `/admin/appointments?from=${from}&to=${to}`),
  adminCancel: (id) => request('POST', `/admin/appointments/${id}/cancel`),
  adminConfig: () => request('GET', '/admin/config'),
  adminSaveConfig: (cfg) => request('PUT', '/admin/config', cfg),
}
