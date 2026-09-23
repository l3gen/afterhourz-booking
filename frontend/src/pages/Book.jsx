import { useCallback, useEffect, useState } from 'react'
import { useNavigate, useSearchParams } from 'react-router-dom'
import { api } from '../api'
import { SignIn, useAuth } from '../auth'
import { track } from '../lib/analytics'
import { getSource } from '../lib/attribution'
import { dayLabel, longDay, money, timeLabel } from '../lib/format'

export default function Book() {
  const navigate = useNavigate()
  const [params, setParams] = useSearchParams()
  const { user, config } = useAuth()

  const [services, setServices] = useState([])
  const [days, setDays] = useState([])
  const [service, setService] = useState(null)
  const [day, setDay] = useState(null)
  const [times, setTimes] = useState([])
  const [time, setTime] = useState(null)
  const [loadingTimes, setLoadingTimes] = useState(false)
  const [phone, setPhone] = useState('')
  const [notes, setNotes] = useState('')
  const [error, setError] = useState('')
  const [submitting, setSubmitting] = useState(false)

  useEffect(() => {
    Promise.all([api.services(), api.openDays()])
      .then(([s, d]) => {
        setServices(s)
        setDays(d.days.slice(0, 14))
      })
      .catch(() => setError('We could not load availability. Please refresh, or call the shop.'))
  }, [])

  // Returning from an abandoned Stripe checkout: release the held slot right away.
  useEffect(() => {
    const appt = params.get('appt')
    if (params.get('payment') === 'cancelled' && appt && user) {
      api.cancel(appt).catch(() => {})
      setParams({}, { replace: true })
    }
  }, [params, user, setParams])

  const loadTimes = useCallback(async () => {
    if (!service || !day) return
    setLoadingTimes(true)
    try {
      const res = await api.availability(service.id, day)
      setTimes(res.times)
    } catch (e) {
      setError(e.message)
    } finally {
      setLoadingTimes(false)
    }
  }, [service, day])

  useEffect(() => {
    setTime(null)
    setTimes([])
    loadTimes()
  }, [loadTimes])

  const deposit = config.payments_enabled && service ? service.deposit_cents : 0
  const ready = service && day && time && phone.trim().length >= 7

  async function submit(e) {
    e.preventDefault()
    setError('')
    setSubmitting(true)
    try {
      const res = await api.book({ service_id: service.id, date: day, time, phone, notes, source: getSource() })
      track('generate_lead', { service: service.id, value: service.price_cents / 100, currency: 'USD' })
      if (res.checkout_url) {
        track('begin_checkout', { value: deposit / 100, currency: 'USD' })
        window.location.assign(res.checkout_url)
      } else {
        navigate(`/booking/success?appt=${res.appointment.id}`)
      }
    } catch (err) {
      setError(err.message)
      if (err.status === 409) {
        setTime(null)
        loadTimes() // someone else took it: refresh the list
      }
      setSubmitting(false)
    }
  }

  return (
    <div className="panel narrow">
      <h1>Book an appointment</h1>
      {params.get('payment') === 'cancelled' && <p className="notice">Payment cancelled. Pick a time whenever you&apos;re ready.</p>}

      <section aria-labelledby="s1">
        <h2 id="s1">1. Choose a service</h2>
        <div className="choices">
          {services.map((s) => (
            <button
              key={s.id}
              type="button"
              className={`choice${service?.id === s.id ? ' selected' : ''}`}
              aria-pressed={service?.id === s.id}
              onClick={() => setService(s)}
            >
              <strong>{s.name}</strong>
              <span>
                {money(s.price_cents)} · {s.duration_min} min
              </span>
            </button>
          ))}
        </div>
      </section>

      {service && (
        <section aria-labelledby="s2">
          <h2 id="s2">2. Pick a day and time</h2>
          <div className="chips" role="group" aria-label="Day">
            {days.map((d) => (
              <button key={d} type="button" className={`chip${day === d ? ' selected' : ''}`} aria-pressed={day === d} onClick={() => setDay(d)}>
                {dayLabel(d)}
              </button>
            ))}
          </div>
          {day && (
            <>
              <p className="muted">{longDay(day)}</p>
              {loadingTimes && <p className="muted">Loading times…</p>}
              {!loadingTimes && times.length === 0 && <p className="muted">No openings this day. Try another.</p>}
              <div className="chips" role="group" aria-label="Time">
                {times.map((t) => (
                  <button key={t} type="button" className={`chip${time === t ? ' selected' : ''}`} aria-pressed={time === t} onClick={() => setTime(t)}>
                    {timeLabel(t)}
                  </button>
                ))}
              </div>
            </>
          )}
        </section>
      )}

      {service && day && time && (
        <section aria-labelledby="s3">
          <h2 id="s3">3. Your details</h2>
          {!user ? (
            <>
              <p>Sign in with Google so we can send your confirmation and let you manage your booking.</p>
              <SignIn />
            </>
          ) : (
            <form onSubmit={submit} className="form">
              <p>
                Booking as <strong>{user.name || user.email}</strong> ({user.email})
              </p>
              <label>
                Mobile number
                <input type="tel" value={phone} onChange={(e) => setPhone(e.target.value)} placeholder="(305) 555-0100" autoComplete="tel" required />
              </label>
              <label>
                Notes for your barber (optional)
                <textarea value={notes} onChange={(e) => setNotes(e.target.value)} maxLength={500} rows={3} />
              </label>
              <div className="summary">
                <div>
                  {service.name} · {longDay(day)} at {timeLabel(time)}
                </div>
                <div>
                  Total {money(service.price_cents)}
                  {deposit > 0 && <> · Deposit due now {money(deposit)}</>}
                </div>
                {deposit > 0 && (
                  <small className="muted">
                    Deposit is refunded if you cancel at least {config.cancel_window_hours} hours ahead. Your time is held for 30 minutes while you pay.
                  </small>
                )}
              </div>
              <button className="btn big" disabled={!ready || submitting}>
                {submitting ? 'Working…' : deposit > 0 ? `Pay ${money(deposit)} deposit & book` : 'Confirm booking'}
              </button>
            </form>
          )}
        </section>
      )}

      {error && (
        <p className="error" role="alert">
          {error}
        </p>
      )}
    </div>
  )
}
