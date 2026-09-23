import { useCallback, useEffect, useMemo, useState } from 'react'
import { api } from '../api'
import { SignIn, useAuth } from '../auth'
import { WEEKDAYS, dayLabel, longDay, timeLabel, toIso } from '../lib/format'

const TIME_OPTIONS = Array.from({ length: 37 }, (_, i) => {
  const m = 6 * 60 + i * 30 // 06:00 .. 24:00
  return `${String(Math.floor(m / 60)).padStart(2, '0')}:${String(m % 60).padStart(2, '0')}`
})

export default function Admin() {
  const { user, ready } = useAuth()
  if (!ready) return null
  if (!user)
    return (
      <div className="panel narrow">
        <h1>Admin</h1>
        <SignIn />
      </div>
    )
  if (!user.is_admin) return <div className="panel narrow"><p>This account does not have admin access.</p></div>
  return (
    <div className="panel">
      <h1>Dashboard</h1>
      <Schedule />
      <Hours />
    </div>
  )
}

function Schedule() {
  const [start, setStart] = useState(toIso(new Date()))
  const [items, setItems] = useState(null)
  const [error, setError] = useState('')

  const end = useMemo(() => {
    const [y, m, d] = start.split('-').map(Number)
    return toIso(new Date(y, m - 1, d + 6))
  }, [start])

  const load = useCallback(() => {
    setItems(null)
    api.adminAppointments(start, end).then(setItems).catch((e) => setError(e.message))
  }, [start, end])
  useEffect(load, [load])

  async function cancel(a) {
    if (!window.confirm(`Cancel ${a.customer_name || a.customer_email} on ${longDay(a.date)} at ${timeLabel(a.time)}? Their deposit will be refunded.`)) return
    try {
      await api.adminCancel(a.id)
      load()
    } catch (e) {
      setError(e.message)
    }
  }

  const byDay = (items || []).reduce((acc, a) => {
    if (a.status === 'cancelled') return acc
    ;(acc[a.date] ||= []).push(a)
    return acc
  }, {})

  return (
    <section aria-labelledby="sched-h">
      <h2 id="sched-h">Schedule (7 days)</h2>
      <label className="inline">
        Starting
        <input type="date" value={start} onChange={(e) => e.target.value && setStart(e.target.value)} />
      </label>
      {error && <p className="error">{error}</p>}
      {items === null && <p className="muted">Loading…</p>}
      {items && Object.keys(byDay).length === 0 && <p className="muted">No appointments in this range.</p>}
      {Object.keys(byDay)
        .sort()
        .map((d) => (
          <div key={d} className="day-block">
            <h3>{dayLabel(d, { weekday: 'long', month: 'short', day: 'numeric' })}</h3>
            <ul className="appt-list">
              {byDay[d].map((a) => (
                <li key={a.id}>
                  <div>
                    <strong>{timeLabel(a.time)}</strong> · {a.service_name} · {a.customer_name || a.customer_email}
                    <div>
                      <small>
                        <a href={`tel:${a.phone}`}>{a.phone}</a> · {a.status.replace('_', ' ')} · via {a.source}
                      </small>
                    </div>
                    {a.notes && <small className="muted">“{a.notes}”</small>}
                  </div>
                  <button className="btn ghost small" onClick={() => cancel(a)}>
                    Cancel
                  </button>
                </li>
              ))}
            </ul>
          </div>
        ))}
    </section>
  )
}

function Hours() {
  const [cfg, setCfg] = useState(null)
  const [newClosed, setNewClosed] = useState('')
  const [status, setStatus] = useState('')

  useEffect(() => {
    api.adminConfig().then(setCfg).catch((e) => setStatus(e.message))
  }, [])
  if (!cfg) return <p className="muted">{status || 'Loading hours…'}</p>

  const setDay = (wd, value) => setCfg((c) => {
    const hours = { ...c.hours }
    if (value) hours[wd] = value
    else delete hours[wd]
    return { ...c, hours }
  })

  async function save() {
    setStatus('Saving…')
    try {
      setCfg(await api.adminSaveConfig(cfg))
      setStatus('Saved.')
    } catch (e) {
      setStatus(e.message)
    }
  }

  return (
    <section aria-labelledby="hours-h">
      <h2 id="hours-h">Opening hours</h2>
      <div className="hours">
        {WEEKDAYS.map((name, wd) => {
          const h = cfg.hours[String(wd)]
          return (
            <div key={name} className="hours-row">
              <label>
                <input type="checkbox" checked={!!h} onChange={(e) => setDay(String(wd), e.target.checked ? { open: '10:00', close: '19:00' } : null)} /> {name}
              </label>
              {h ? (
                <>
                  <select aria-label={`${name} opens`} value={h.open} onChange={(e) => setDay(String(wd), { ...h, open: e.target.value })}>
                    {TIME_OPTIONS.slice(0, -1).map((t) => <option key={t} value={t}>{timeLabel(t)}</option>)}
                  </select>
                  to
                  <select aria-label={`${name} closes`} value={h.close} onChange={(e) => setDay(String(wd), { ...h, close: e.target.value })}>
                    {TIME_OPTIONS.slice(1).map((t) => <option key={t} value={t}>{t === '24:00' ? 'Midnight' : timeLabel(t)}</option>)}
                  </select>
                </>
              ) : (
                <span className="muted">Closed</span>
              )}
            </div>
          )
        })}
      </div>

      <h3>Days off</h3>
      <div className="chips">
        {cfg.closed_dates.map((d) => (
          <button key={d} className="chip selected" onClick={() => setCfg({ ...cfg, closed_dates: cfg.closed_dates.filter((x) => x !== d) })} aria-label={`Remove ${d}`}>
            {dayLabel(d)} ✕
          </button>
        ))}
      </div>
      <div className="inline">
        <input type="date" value={newClosed} onChange={(e) => setNewClosed(e.target.value)} aria-label="Add day off" />
        <button className="btn ghost small" disabled={!newClosed} onClick={() => { setCfg({ ...cfg, closed_dates: [...new Set([...cfg.closed_dates, newClosed])].sort() }); setNewClosed('') }}>
          Add day off
        </button>
      </div>
      <p>
        <button className="btn" onClick={save}>Save hours</button> <span className="muted">{status}</span>
      </p>
    </section>
  )
}
