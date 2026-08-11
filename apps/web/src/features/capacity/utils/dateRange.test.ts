import { describe, expect, it } from 'vitest'
import { nextWeek, resolvePreset, thisMonth, thisWeek } from './dateRange'

describe('thisWeek', () => {
  it('returns Monday-Sunday when today is the Monday', () => {
    expect(thisWeek(new Date(2026, 7, 17))).toEqual({
      start: '2026-08-17',
      end: '2026-08-23',
    })
  })

  it('returns the same week when today is the Sunday', () => {
    expect(thisWeek(new Date(2026, 7, 23))).toEqual({
      start: '2026-08-17',
      end: '2026-08-23',
    })
  })

  it('returns the same week for a midweek date', () => {
    expect(thisWeek(new Date(2026, 7, 19))).toEqual({
      start: '2026-08-17',
      end: '2026-08-23',
    })
  })
})

describe('nextWeek', () => {
  it('returns the following Monday-Sunday', () => {
    expect(nextWeek(new Date(2026, 7, 17))).toEqual({
      start: '2026-08-24',
      end: '2026-08-30',
    })
  })
})

describe('thisMonth', () => {
  it('spans the full calendar month, 31 days', () => {
    expect(thisMonth(new Date(2026, 7, 19))).toEqual({
      start: '2026-08-01',
      end: '2026-08-31',
    })
  })

  it('spans the full calendar month, 30 days', () => {
    expect(thisMonth(new Date(2026, 8, 5))).toEqual({
      start: '2026-09-01',
      end: '2026-09-30',
    })
  })
})

describe('resolvePreset', () => {
  it('resolves this-week/next-week/this-month to concrete ranges', () => {
    const today = new Date(2026, 7, 17)
    expect(resolvePreset('this-week', today)).toEqual(thisWeek(today))
    expect(resolvePreset('next-week', today)).toEqual(nextWeek(today))
    expect(resolvePreset('this-month', today)).toEqual(thisMonth(today))
  })

  it('returns null for custom, meaning "leave the current selection alone"', () => {
    expect(resolvePreset('custom')).toBeNull()
  })
})
