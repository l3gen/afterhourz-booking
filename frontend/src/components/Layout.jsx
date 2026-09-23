import { useEffect } from 'react'
import { Link, NavLink, Outlet, useLocation } from 'react-router-dom'
import { useAuth } from '../auth'
import { pageView } from '../lib/analytics'
import { site } from '../siteConfig'
import Slideshow from './Slideshow'

export default function Layout() {
  const { user, signOut } = useAuth()
  const { pathname } = useLocation()

  useEffect(() => {
    pageView(pathname)
    window.scrollTo(0, 0)
  }, [pathname])

  return (
    <>
      <Slideshow />
      <header className="site-header">
        <Link to="/" className="brand">
          After<span>Hourz</span>Kutz
        </Link>
        <nav aria-label="Main">
          <NavLink to="/book" className="btn small">
            Book now
          </NavLink>
          {user && <NavLink to="/my-appointments">My appointments</NavLink>}
          {user?.is_admin && <NavLink to="/admin">Admin</NavLink>}
          {user && (
            <button className="linklike" onClick={signOut}>
              Sign out
            </button>
          )}
        </nav>
      </header>
      <main>
        <Outlet />
      </main>
      <footer className="site-footer">
        <p>
          © {new Date().getFullYear()} {site.name} · {site.city} ·{' '}
          <a href={`https://instagram.com/${site.instagram}`} target="_blank" rel="noreferrer">
            @{site.instagram}
          </a>
        </p>
      </footer>
    </>
  )
}
