import { describe, expect, it } from 'vitest'

import {
  canBringBack, idleMode, idleTitle, parseIdleClose, thresholdLabel, whenLabel,
} from '../../src/lib/fleetIdleClose'

const answer = {
  threshold_hours: 48,
  threshold_error: null,
  timer: { known: true, installed: true, enabled: true, next_run: 1_794_106_800, last_run: null },
  upcoming: [{ label: 'a', project: 'p', session_id: 's1', idle_hours: 50, busy: false }, { nope: 1 }],
  closed: [{ label: 'b', project: 'p', session_id: 's2', idle_hours: 60, running: false, ts: '2026-11-07T23:44:00+0100' }],
  liveness_known: true,
}

describe('parseIdleClose', () => {
  it('keeps well-formed rows and drops the rest', () => {
    const s = parseIdleClose(answer)!
    expect(s.upcoming.map(r => r.session_id)).toEqual(['s1'])
    expect(s.closed.map(r => r.session_id)).toEqual(['s2'])
    expect(s.timer.next_run).toBe(1_794_106_800)
  })
  it('refuses an answer without a threshold or a timer', () => {
    expect(parseIdleClose({ timer: {} })).toBeNull()
    expect(parseIdleClose({ threshold_hours: 48 })).toBeNull()
    expect(parseIdleClose(null)).toBeNull()
  })
})

describe('idleMode', () => {
  it('an unreadable timer is unknown, never off', () => {
    const s = parseIdleClose({ ...answer, timer: { known: false, installed: null, enabled: null } })!
    expect(idleMode(s)).toBe('unknown')
    expect(idleMode(parseIdleClose({ ...answer, timer: { ...answer.timer, enabled: false } })!)).toBe('off')
    expect(idleMode(parseIdleClose(answer)!)).toBe('on')
  })
  it('the title names the threshold and the coming closes', () => {
    expect(idleTitle(parseIdleClose(answer)!)).toMatch(/2 days.*1 will close/)
  })
})

describe('labels', () => {
  it('says the threshold the way a person does', () => {
    expect(thresholdLabel(24)).toBe('24 h')
    expect(thresholdLabel(48)).toBe('2 days')
    expect(thresholdLabel(168)).toBe('1 week')
    expect(thresholdLabel(30)).toBe('30 h')
  })
  it('names today and tomorrow', () => {
    const now = new Date(2026, 10, 8, 0, 5)
    expect(whenLabel(new Date(2026, 10, 8, 4, 0).getTime() / 1000, now)).toMatch(/^today /)
    expect(whenLabel(new Date(2026, 10, 9, 4, 0).getTime() / 1000, now)).toMatch(/^tomorrow /)
    expect(whenLabel(null, now)).toBe('—')
  })
})

describe('canBringBack', () => {
  it('only when the session is known not to be running', () => {
    expect(canBringBack({ session_id: 's', label: 'x', project: 'p', idle_hours: 1, running: false })).toBe(true)
    expect(canBringBack({ session_id: 's', label: 'x', project: 'p', idle_hours: 1, running: true })).toBe(false)
    expect(canBringBack({ session_id: 's', label: 'x', project: 'p', idle_hours: 1, running: null })).toBe(false)
    expect(canBringBack({ session_id: 's', label: 'x', project: null, idle_hours: 1, running: false })).toBe(false)
  })
})
