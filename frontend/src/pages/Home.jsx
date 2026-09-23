import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { api } from '../api'
import { gallery } from '../gallery'
import { money } from '../lib/format'
import { site } from '../siteConfig'

export default function Home() {
  const [services, setServices] = useState([])
  useEffect(() => {
    api.services().then(setServices).catch(() => {})
  }, [])

  return (
    <>
      <section className="hero">
        <h1>{site.name}</h1>
        <p className="lead">{site.tagline}</p>
        <Link to="/book" className="btn big">
          Book your cut
        </Link>
        <p className="muted">Instant confirmation · Free cancellation up to 24h ahead</p>
      </section>

      <section className="panel" aria-labelledby="services-h">
        <h2 id="services-h">Services</h2>
        <ul className="service-list">
          {services.map((s) => (
            <li key={s.id}>
              <div>
                <strong>{s.name}</strong>
                <span className="muted"> · {s.duration_min} min</span>
                <p>{s.description}</p>
              </div>
              <span className="price">{money(s.price_cents)}</span>
            </li>
          ))}
        </ul>
      </section>

      <section className="panel" aria-labelledby="work-h">
        <h2 id="work-h">Fresh work</h2>
        <div className="grid">
          {gallery.map((g) => (
            <img key={g.src} src={g.src} alt={g.alt} loading="lazy" width="800" height="500" />
          ))}
        </div>
        <p>
          More on Instagram:{' '}
          <a href={`https://instagram.com/${site.instagram}`} target="_blank" rel="noreferrer">
            @{site.instagram}
          </a>
        </p>
      </section>

      <section className="panel" aria-labelledby="visit-h">
        <h2 id="visit-h">Visit us</h2>
        <p>
          <a href={site.mapsUrl} target="_blank" rel="noreferrer">
            {site.address}
          </a>
        </p>
        <p>
          Call or text: <a href={`tel:${site.phone.replace(/\D/g, '')}`}>{site.phone}</a>
        </p>
        <p className="muted">Hours are shown when you pick a day to book.</p>
      </section>
    </>
  )
}
