import { dayLabel, money, parseDay, timeLabel, toIso } from './format'

describe('format helpers', () => {
  it('formats money, dropping .00', () => {
    expect(money(3500)).toBe('$35')
    expect(money(1250)).toBe('$12.50')
  })
  it('formats 24h times as 12h', () => {
    expect(timeLabel('00:00')).toBe('12:00 AM')
    expect(timeLabel('10:30')).toBe('10:30 AM')
    expect(timeLabel('12:00')).toBe('12:00 PM')
    expect(timeLabel('18:30')).toBe('6:30 PM')
  })
  it('parses ISO dates as local days (no timezone shift)', () => {
    const d = parseDay('2026-09-22')
    expect([d.getFullYear(), d.getMonth(), d.getDate()]).toEqual([2026, 8, 22])
    expect(toIso(d)).toBe('2026-09-22')
    expect(dayLabel('2026-09-22')).toBe('Tue, Sep 22')
  })
})
