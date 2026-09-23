import { createContext, useCallback, useContext, useEffect, useMemo, useRef, useState } from 'react'
import { api, tokenStore } from './api'

const AuthContext = createContext(null)
export const useAuth = () => useContext(AuthContext)

export function AuthProvider({ children }) {
  const [user, setUser] = useState(null)
  const [ready, setReady] = useState(false)
  const [config, setConfig] = useState({ google_client_id: '', payments_enabled: false, cancel_window_hours: 24 })

  useEffect(() => {
    api.siteConfig().then(setConfig).catch(() => {})
    if (!tokenStore.get()) {
      setReady(true)
      return
    }
    api
      .me()
      .then(setUser)
      .catch(() => tokenStore.set(null))
      .finally(() => setReady(true))
  }, [])

  const startSession = useCallback((session) => {
    tokenStore.set(session.token)
    setUser(session.user)
  }, [])

  const signOut = useCallback(() => {
    tokenStore.set(null)
    setUser(null)
  }, [])

  const value = useMemo(() => ({ user, ready, config, startSession, signOut }), [user, ready, config, startSession, signOut])
  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>
}

let gsiPromise
function loadGoogleScript() {
  gsiPromise ||= new Promise((resolve, reject) => {
    const s = document.createElement('script')
    s.src = 'https://accounts.google.com/gsi/client'
    s.async = true
    s.onload = resolve
    s.onerror = () => reject(new Error('Could not load Google sign-in'))
    document.head.appendChild(s)
  })
  return gsiPromise
}

/** Google sign-in button. Falls back to a dev-only email form when running `npm run dev` without a client ID. */
export function SignIn({ onSignedIn }) {
  const { config, startSession } = useAuth()
  const btn = useRef(null)
  const [error, setError] = useState('')
  const clientId = config.google_client_id || import.meta.env.VITE_GOOGLE_CLIENT_ID || ''

  useEffect(() => {
    if (!clientId || !btn.current) return
    let cancelled = false
    loadGoogleScript()
      .then(() => {
        if (cancelled) return
        window.google.accounts.id.initialize({
          client_id: clientId,
          callback: async ({ credential }) => {
            try {
              const session = await api.googleLogin(credential)
              startSession(session)
              onSignedIn?.(session.user)
            } catch (e) {
              setError(e.message)
            }
          },
        })
        window.google.accounts.id.renderButton(btn.current, { theme: 'filled_black', size: 'large', shape: 'pill', text: 'continue_with' })
      })
      .catch((e) => setError(e.message))
    return () => {
      cancelled = true
    }
  }, [clientId, startSession, onSignedIn])

  if (!clientId && import.meta.env.DEV) return <DevLogin onSignedIn={onSignedIn} />
  if (!clientId) return <p className="error">Sign-in is not configured yet.</p>
  return (
    <div>
      <div ref={btn} />
      {error && <p className="error">{error}</p>}
    </div>
  )
}

function DevLogin({ onSignedIn }) {
  const { startSession } = useAuth()
  const [email, setEmail] = useState('client@example.com')
  const submit = async (e) => {
    e.preventDefault()
    const session = await api.devLogin(email, email.split('@')[0])
    startSession(session)
    onSignedIn?.(session.user)
  }
  return (
    <form onSubmit={submit} className="dev-login">
      <small>Local dev only (Google sign-in is not configured)</small>
      <input type="email" value={email} onChange={(e) => setEmail(e.target.value)} required />
      <button className="btn ghost">Dev sign in</button>
    </form>
  )
}
