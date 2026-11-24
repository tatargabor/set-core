/**
 * The watchdog on the fleet header (fleet-watchdog, task 5.3): the four badge states — STALE
 * distinct from zero — the parser refusing an unknown shape, and the panel's actions. Whether
 * the panel moves anything is a measurement taken in the browser (task 5.4), not here.
 */
import { afterEach, describe, expect, it, vi } from 'vitest'
import { cleanup, fireEvent, render, waitFor } from '@testing-library/react'

import FleetWatchdog from '../../src/components/FleetWatchdog'
import { canDispatch, dispatchLabel, parseWatchdog, verdictLabel, watchdogTitle } from '../../src/lib/fleetWatchdog'

afterEach(() => { cleanup(); vi.unstubAllGlobals() })

const NOW = Date.now() / 1000
const FINDING = {
  fp: '0123456789abcdef', probe: 'service-health', severity: 'fail', subject: 'unit:x.service',
  summary: 'user unit x.service is failed', first_seen: NOW - 600, last_seen: NOW - 10, resolved_at: null,
  triage: { verdict: 'real', owner: 'proj', brief: 'restart it' }, dispatch: null, muted: false,
}
function state(over: Record<string, unknown> = {}) {
  return {
    schema: 'set-watchdog/1', enabled: true, badge: 'red', last_tick_at: NOW - 60, last_tick_age_s: 60, interval_s: 300,
    counts: { open: 1, fail: 1, warn: 0, untriaged: 0, dispatched: 0, muted: 0, resolved_24h: 0 },
    open: [FINDING], muted: [], resolved: [], ...over,
  }
}

function stubFetch(answer: unknown, calls: Array<[string, RequestInit | undefined]> = []) {
  vi.stubGlobal('fetch', vi.fn((url: string, init?: RequestInit) => {
    calls.push([url, init])
    const body = url.endsWith('/api/fleet/watchdog') ? answer : { ok: true }
    return Promise.resolve({ ok: true, json: () => Promise.resolve(body) })
  }))
  return calls
}

describe('parseWatchdog', () => {
  it('refuses an unknown shape instead of reading it as calm', () => {
    expect(parseWatchdog({ badge: 'ok' })).toBeNull()
    expect(parseWatchdog({ ...state(), badge: 'weird' })).toBeNull()
  })
  it('keeps untriaged visible', () => {
    const s = parseWatchdog(state({ open: [{ ...FINDING, triage: null }] }))!
    expect(s.open[0].untriaged).toBe(true)
    expect(verdictLabel(s.open[0])).toBe('untriaged')
  })
})

describe('labels', () => {
  it('names every state in the title, stale included', () => {
    const stale = parseWatchdog(state({ badge: 'stale', last_tick_age_s: 2400 }))!
    expect(watchdogTitle(stale, null, '40m')).toContain('STALE')
    const never = parseWatchdog(state({ badge: 'stale', last_tick_at: null, last_tick_age_s: null }))!
    expect(watchdogTitle(never, null, '—')).toContain('never ticked')
    expect(watchdogTitle(null, 'HTTP 500', '—')).toContain('not read')
  })
  it('shows a hold reason and a known id', () => {
    const f = parseWatchdog(state())!.open[0]
    expect(dispatchLabel({ ...f, dispatch: { state: 'held', reason: 'daily cap' } })).toBe('held: daily cap')
    expect(verdictLabel({ ...f, triage: { verdict: 'known:B-214', owner: null, brief: '' } })).toBe('B-214')
    expect(canDispatch(f)).toBe(true)
    expect(canDispatch({ ...f, dispatch: { state: 'dispatched' } })).toBe(false)
  })
})

describe('FleetWatchdog badge', () => {
  it.each([
    ['red', { badge: 'red' }, '1'],
    ['count', { badge: 'count', counts: { ...state().counts, fail: 0, warn: 1 } }, '1'],
    ['ok', { badge: 'ok', open: [], counts: { ...state().counts, open: 0, fail: 0 } }, ''],
  ])('%s', async (badge, over, text) => {
    stubFetch(state(over))
    const { container } = render(<FleetWatchdog />)
    await waitFor(() => expect(container.querySelector(`[data-fleet-watchdog-badge="${badge}"]`)).not.toBeNull())
    expect(container.querySelector('[data-fleet-watchdog-open]')?.textContent ?? '').toBe(text)
  })

  it('stale is drawn as stale, not as zero (AC-12)', async () => {
    stubFetch(state({ badge: 'stale', last_tick_age_s: 2400, open: [], counts: { ...state().counts, open: 0, fail: 0 } }))
    const { container } = render(<FleetWatchdog />)
    await waitFor(() => expect(container.querySelector('[data-fleet-watchdog-stale]')).not.toBeNull())
    expect(container.querySelector('[data-fleet-watchdog-open]')).toBeNull()
  })

  it('an unreadable answer is unread, never ok', async () => {
    vi.stubGlobal('fetch', vi.fn(() => Promise.resolve({ ok: false, status: 502, json: () => Promise.resolve({}) })))
    const { container } = render(<FleetWatchdog />)
    await waitFor(() => expect(container.querySelector('[data-fleet-watchdog-badge="unread"]')).not.toBeNull())
  })

  it('the panel opens, mutes and dispatches', async () => {
    const calls = stubFetch(state())
    const { container } = render(<FleetWatchdog />)
    await waitFor(() => expect(container.querySelector('[data-fleet-watchdog-badge="red"]')).not.toBeNull())
    fireEvent.click(container.querySelector('[data-fleet-watchdog-badge]')!)
    expect(container.querySelector('[data-fleet-watchdog-panel="red"]')).not.toBeNull()
    fireEvent.click(container.querySelector('[data-fleet-watchdog-dispatch]')!)
    await waitFor(() =>
      expect(calls.some(([u, i]) => u.endsWith(`/${FINDING.fp}/dispatch`) && i?.method === 'POST')).toBe(true))
    // While a post is in flight the actions are disabled; the next one waits for it.
    const mute = () => container.querySelector(`[data-fleet-watchdog-mute="${FINDING.fp}:7"]`) as HTMLButtonElement
    await waitFor(() => expect(mute().disabled).toBe(false))
    fireEvent.click(mute())
    await waitFor(() =>
      expect(calls.some(([u, i]) => u.endsWith(`/${FINDING.fp}/mute`) && String(i?.body).includes('"days":7'))).toBe(true))
    fireEvent.keyDown(document, { key: 'Escape' })
    expect(container.querySelector('[data-fleet-watchdog-panel]')).toBeNull()
  })
})
