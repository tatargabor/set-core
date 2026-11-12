import { describe, expect, test } from 'claude-code/testing'

import {
  accountEmail,
  answer,
  disabled,
  dueSlot,
  heldByOther,
  isActive,
  parseEntry,
  parseState,
  SNOOZE_MS,
  withState,
} from '../hooks/logic'

const T = ['08:30', '18:30']
const NOW = 1_000_000
const ROOT = '/work/proj'
const doc = (e: object) => JSON.stringify({ projects: { [ROOT]: e } })

describe('opt-in is per account and per project', () => {
  test('off without an entry, off for another account, on for the owner', () => {
    const e = parseEntry(doc({ enabled: true, account: 'owner@example.com' }), ROOT)
    expect(isActive(parseEntry(undefined, ROOT), 'owner@example.com')).toBe(false)
    expect(isActive(e, 'other@example.com')).toBe(false)
    expect(isActive(e, 'OWNER@example.com')).toBe(true)
    expect(isActive(e, '')).toBe(false)
    expect(isActive(parseEntry(doc({ enabled: true, account: 'owner@example.com' }), '/work/other'), 'owner@example.com')).toBe(false)
  })
  test('reads the account e-mail and defaults the times', () => {
    expect(accountEmail(JSON.stringify({ oauthAccount: { emailAddress: 'a@b.c' } }))).toBe('a@b.c')
    expect(accountEmail('not json')).toBe('')
    expect(parseEntry(doc({ enabled: true, account: 'x', times: ['25:00'] }), ROOT)?.times).toEqual(T)
  })
  test('off disables only this project', () => {
    const text = JSON.stringify({ projects: { [ROOT]: { enabled: true, account: 'a' }, '/other': { enabled: true, account: 'a' } } })
    const after = JSON.parse(disabled(text, ROOT))
    expect(after.projects[ROOT].enabled).toBe(false)
    expect(after.projects['/other'].enabled).toBe(true)
  })
})

describe('slots', () => {
  test('nothing before the first time, the morning slot after it, missed slot stays due', () => {
    expect(dueSlot('2026-10-05', '08:00', T, { handled: {} }, NOW)).toBe(null)
    expect(dueSlot('2026-10-05', '08:31', T, { handled: {} }, NOW)).toBe('2026-10-05 08:30')
    expect(dueSlot('2026-10-05', '17:00', T, { handled: {} }, NOW)).toBe('2026-10-05 08:30')
    expect(dueSlot('2026-10-05', '18:30', T, { handled: {} }, NOW)).toBe('2026-10-05 18:30')
  })
  test('snooze silences for an hour', () => {
    const st = answer({ handled: {} }, '2026-10-05 08:30', 'snooze', NOW)
    expect(st.snoozeUntil).toBe(NOW + SNOOZE_MS)
    expect(dueSlot('2026-10-05', '08:40', T, st, NOW + SNOOZE_MS - 1)).toBe(null)
    expect(dueSlot('2026-10-05', '09:40', T, st, NOW + SNOOZE_MS)).toBe('2026-10-05 08:30')
  })
  test('tomorrow silences the rest of the day; run marks the slot', () => {
    const st = answer({ handled: {} }, '2026-10-05 08:30', 'tomorrow', NOW)
    expect(dueSlot('2026-10-05', '18:31', T, st, NOW)).toBe(null)
    expect(dueSlot('2026-10-06', '08:31', T, st, NOW)).toBe('2026-10-06 08:30')
    const ran = answer({ handled: {} }, '2026-10-05 08:30', 'run', NOW)
    expect(dueSlot('2026-10-05', '09:00', T, ran, NOW)).toBe(null)
    expect(dueSlot('2026-10-05', '18:31', T, ran, NOW)).toBe('2026-10-05 18:30')
  })
  test('the lease: another live session holds the slot, an expired lease does not', () => {
    const st = { handled: {}, shown: { slot: 's', by: 'a', at: NOW } }
    expect(heldByOther(st, 's', 'b', NOW + 1000)).toBe(true)
    expect(heldByOther(st, 's', 'a', NOW + 1000)).toBe(false)
    expect(heldByOther(st, 's', 'b', NOW + 31 * 60 * 1000)).toBe(false)
  })
  test('state is per project and other projects survive a write', () => {
    const text = withState(JSON.stringify({ projects: { '/other': { handled: { x: 'run' } } } }), ROOT, { handled: { y: 'skip' } })
    expect(parseState(text, ROOT).handled).toEqual({ y: 'skip' })
    expect(parseState(text, '/other').handled).toEqual({ x: 'run' })
  })
})
