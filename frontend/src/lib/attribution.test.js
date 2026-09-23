import { captureSource, getSource } from './attribution'

const fakeStorage = () => {
  const m = new Map()
  return { getItem: (k) => m.get(k) ?? null, setItem: (k, v) => m.set(k, v) }
}

describe('attribution', () => {
  it('defaults to direct', () => {
    expect(getSource(fakeStorage())).toBe('direct')
  })
  it('records the Google Business Profile link', () => {
    const s = fakeStorage()
    captureSource('?utm_source=google&utm_medium=organic&utm_campaign=business-profile', s)
    expect(getSource(s)).toBe('google-organic-business-profile')
  })
  it('sanitises hostile values', () => {
    const s = fakeStorage()
    captureSource('?utm_source=%3Cscript%3Ealert(1)%3C%2Fscript%3E', s)
    expect(getSource(s)).toBe('scriptalert1script')
  })
  it('survives unavailable storage', () => {
    const broken = { getItem: () => { throw new Error('x') }, setItem: () => { throw new Error('x') } }
    expect(() => captureSource('?utm_source=google', broken)).not.toThrow()
    expect(getSource(broken)).toBe('direct')
  })
})
