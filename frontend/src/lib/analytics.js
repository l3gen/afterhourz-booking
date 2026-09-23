import { site } from '../siteConfig'

// GA4 loads only if VITE_GA_ID is set, so local/dev builds never pollute production data.
export function initAnalytics() {
  if (!site.gaId || window.gtag) return
  const s = document.createElement('script')
  s.async = true
  s.src = `https://www.googletagmanager.com/gtag/js?id=${encodeURIComponent(site.gaId)}`
  document.head.appendChild(s)
  window.dataLayer = window.dataLayer || []
  window.gtag = function gtag() {
    window.dataLayer.push(arguments)
  }
  window.gtag('js', new Date())
  window.gtag('config', site.gaId, { send_page_view: false }) // SPA: we send page views ourselves
}

export function pageView(path) {
  if (window.gtag) window.gtag('event', 'page_view', { page_path: path, page_location: window.location.href })
}

export function track(name, params = {}) {
  if (window.gtag) window.gtag('event', name, params)
}
