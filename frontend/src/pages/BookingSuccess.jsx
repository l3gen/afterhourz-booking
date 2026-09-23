import { useEffect, useState } from 'react'
import { Link, useSearchParams } from 'react-router-dom'
import { api } from '../api'
import { useAuth } from '../auth'
import { track } from '../lib/analytics'
import { longDay, money, timeLabel } from '../lib/format'

// After Stripe redirects back, the webhook that confirms the booking may land a moment later,
// so poll briefly instead of assuming.
export default function BookingSuccess() {
  const [params] = useSearchParams()
  const id = params.get('appt')
  const { user, ready } = useAuth()
  const [appt, setAppt] = useState(null)
  const [gaveUp, setGaveUp] = useState(false)

  useEffect(() => {
    if (!id || !user) return undefined
    let stopped = false
    let tries = 0
    const tick = async () => {
      try {
        const a = await api.appointment(id)
        if (stopped) return
        setAppt(a)
        if (a.status === 'confirmed') {
          track('booking_confirmed', { service: a.service_id, value: a.price_cents / 100, currency: 'USD', source: a.source })
          return
        }
      } catch {
        /* keep trying */
      }
      tries += 1
      if (tries < 15) setTimeout(tick, 2000)
      else setGaveUp(true)
    }
    tick()
    return () => {
      stopped = true
    }
  }, [id, user])

  if (!ready) return null
  if (!user) return <div className="panel narrow"><p>Please sign in to view your booking.</p></div>

  const confirmed = appt?.status === 'confirmed'
  return (
    <div className="panel narrow">
      <h1>{confirmed ? "You\u2019re booked!" : 'Finishing up…'}</h1>
      {!confirmed && !gaveUp && <p>Confirming your payment. This usually takes a few seconds.</p>}
      {!confirmed && gaveUp && (
        <p>
          We haven&apos;t received your payment confirmation yet. Check <Link to="/my-appointments">My appointments</Link> in a minute, or call the shop if you were charged.
        </p>
      )}
      {confirmed && (
        <>
          <p className="big-text">
            {appt.service_name} · {longDay(appt.date)} at {timeLabel(appt.time)}
          </p>
          <p>
            Total {money(appt.price_cents)}
            {appt.deposit_cents > 0 && ` (deposit ${money(appt.deposit_cents)} paid)`}. A confirmation is on its way to {appt.customer_email}.
          </p>
          <Link className="btn" to="/my-appointments">
            Manage my appointments
          </Link>
        </>
      )}
    </div>
  )
}
