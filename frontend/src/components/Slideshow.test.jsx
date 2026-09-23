import { act, render, screen } from '@testing-library/react'
import Slideshow from './Slideshow'

const imgs = [
  { src: '/a.jpg', alt: 'a' },
  { src: '/b.jpg', alt: 'b' },
  { src: '/c.jpg', alt: 'c' },
]

describe('Slideshow', () => {
  beforeEach(() => vi.useFakeTimers())
  afterEach(() => vi.useRealTimers())

  it('is decorative and crossfades through every image', () => {
    render(<Slideshow images={imgs} interval={1000} />)
    const root = screen.getByTestId('slideshow')
    expect(root).toHaveAttribute('aria-hidden', 'true')
    const active = () => [...root.querySelectorAll('img')].findIndex((i) => i.classList.contains('active'))
    expect(active()).toBe(0)
    act(() => vi.advanceTimersByTime(1000))
    expect(active()).toBe(1)
    act(() => vi.advanceTimersByTime(2000))
    expect(active()).toBe(0) // wrapped around
  })

  it('stays on a single still image when the visitor prefers reduced motion', () => {
    window.matchMedia = vi.fn().mockReturnValue({ matches: true })
    render(<Slideshow images={imgs} interval={1000} />)
    act(() => vi.advanceTimersByTime(5000))
    expect(screen.getByTestId('slideshow').querySelector('img.active').getAttribute('src')).toBe('/a.jpg')
    delete window.matchMedia
  })
})
