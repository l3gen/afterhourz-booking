import { useEffect, useState } from 'react'
import { gallery } from '../gallery'

function prefersReducedMotion() {
  return typeof window !== 'undefined' && !!window.matchMedia?.('(prefers-reduced-motion: reduce)').matches
}

/**
 * Full-screen background of crossfading haircut photos.
 *
 * Deliberately a slow, smooth crossfade rather than hard "flashing": rapid flashing can trigger
 * seizures in photosensitive people (WCAG 2.3.1) and looks cheap. Also: pauses while the tab is
 * hidden, and shows a single still image for visitors who request reduced motion.
 */
export default function Slideshow({ images = gallery, interval = 6000 }) {
  const [active, setActive] = useState(0)
  const reduced = prefersReducedMotion()

  useEffect(() => {
    if (reduced || images.length < 2) return undefined
    let timer
    const start = () => {
      timer = setInterval(() => setActive((i) => (i + 1) % images.length), interval)
    }
    const stop = () => clearInterval(timer)
    const onVisibility = () => (document.hidden ? stop() : start())
    start()
    document.addEventListener('visibilitychange', onVisibility)
    return () => {
      stop()
      document.removeEventListener('visibilitychange', onVisibility)
    }
  }, [images.length, interval, reduced])

  return (
    <div className="slideshow" aria-hidden="true" data-testid="slideshow">
      {images.map((img, i) => (
        <img
          key={img.src}
          src={img.src}
          alt=""
          className={`slide${i === active ? ' active' : ''}`}
          loading={i === 0 ? 'eager' : 'lazy'}
          decoding="async"
        />
      ))}
      <div className="slideshow-scrim" />
    </div>
  )
}
