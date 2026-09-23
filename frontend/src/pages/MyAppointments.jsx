import { useCallback, useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { api } from '../api'
import { SignIn, useAuth } from '../auth'
import { longDay, money, timeLabel, toIso } from '../lib/format'

export default function MyAppointments() {
  const { user, ready, config } = useAuth()
  const [items, setItems] = useState(null)
  const [message, setMessage] = useState('')

  const load = useCallback(
    () =>
      api
        .mine()
        .then(setItems)
        .catch((e) => setMessage(e.message)),
    [],
  )
  useEffect(() => {
    if (user) load()
  }, [user, load])

  async function cancel(a) {
    const policy = a.payment_intent_id
      ? `\n\nYour deposit is refunded if this is at least ${config.cancel_window_hours} hours away.`
      : ''
    if (!window.confirm(`Cancel ${a.service_name} on ${longDay(a.date)} at ${timeLabel(a.time)}?${policy}`)) return
    try {
      const res = await api.cancel(a.id)
      setMessage(res.refunded ? 'Cancelled. Your deposit is being refunded.' : 'Cancelled.')
      load()
    } catch (e) {
      setMessage(e.message)
    }
  }

  if (!ready) return null
  if (!user)
    return (
      <div className="dock-bottom">
        <div className="panel compact">
          <h1>My appointments</h1>
          <p>Sign in to see your bookings.</p>
          <SignIn />
        </div>
      </div>
    )

  const today = toIso(new Date())
  // Small card docked at the bottom so the haircut photos behind it stay visible.
  return (
    <div className="dock-bottom">
      <div className="panel compact">
        <h1>My appointments</h1>
        {message && <p className="notice">{message}</p>}
        {items === null && <p className="muted">Loading…</p>}
        {items?.length === 0 && (
          <p>
            Nothing booked yet. <Link to="/book">Book a cut</Link>
          </p>
        )}
        <ul className="appt-list">
          {items?.map((a) => (
            <li key={a.id} className={a.status === 'cancelled' ? 'dim' : ''}>
              <div>
                <strong>{a.service_name}</strong>
                <div>
                  {longDay(a.date)} at {timeLabel(a.time)}
                </div>
                <small className="muted">
                  {a.status.replace('_', ' ')} · {money(a.price_cents)}
                  {a.refunded && ' · deposit refunded'}
                </small>
              </div>
              {['confirmed', 'pending_payment'].includes(a.status) && a.date >= today && (
                <button className="btn ghost small" onClick={() => cancel(a)}>
                  Cancel
                </button>
              )}
            </li>
          ))}
        </ul>
      </div>
    </div>
  )
}
