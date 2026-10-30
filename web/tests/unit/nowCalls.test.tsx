/**
 * The Now card's Calls tab (fleet-now-card section 9), against a stubbed API.
 *
 * As in nowCard.test.tsx and nowGoals.test.tsx, what is asserted is what the owner sees
 * and what is SENT: every answer's request body is read back.
 */
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { act, cleanup, fireEvent, render, screen } from '@testing-library/react'

vi.mock('../../src/hooks/useSonioxAvailable', () => ({
  useSonioxAvailable: () => ({ checked: true, hasKey: false, apiKey: null, micSupported: true }),
}))
vi.mock('../../src/components/VoiceInput', () => ({ default: () => null }))

import Now from '../../src/pages/Now'
import { callsCount, callsFailure, callsNotes, dueLabel } from '../../src/lib/nowCard'
import type { Call, CallsPayload, NowPayload } from '../../src/lib/nowCard'

function nowPayload(locale?: 'en' | 'hu'): NowPayload {
  return {
    item: {
      source: 'owner-queue', id: 'i1', project: 'alpha', sentence: 'Review the draft', why: 'Friday',
      options: [], acceptsText: false, delegable: false, actions: ['done', 'later'], goThere: null,
    },
    following: 0, heldBack: 0,
    sources: [{ name: 'owner-queue', measured: true, reason: null, count: 1 }],
    unmeasured: 0,
    publisher: { state: 'ok', project: 'pub', candidates: ['pub'], reason: null, acceptsActions: true },
    partial: false, malformed: 0, rankedAt: null, rankingAgeSeconds: null, stale: false,
    closedToday: 0, parkedIdeas: 0,
    cue: { play: false, reason: null, variant: null, slowed: false, intervalSeconds: 600 },
    windDown: { active: false, hour: 23, delegableIds: [] },
    tomorrowNote: null, focus: [], focusMax: 3, focusSetToday: false, focusCandidates: [],
    generatedAt: new Date().toISOString(), ...(locale ? { locale } : {}),
  }
}

function call(id: string, extra: Partial<Call> = {}): Call {
  return { id, who: `Person ${id}`, about: `About ${id}`, kind: 'promised', evidence: [], overdue: false, ...extra }
}

function callsPayload(extra: Partial<CallsPayload> = {}): CallsPayload {
  const calls = extra.calls ?? [call('c1'), call('c2', { kind: 'retry' })]
  return {
    publisher: { state: 'ok', project: 'pub', candidates: ['pub'], reason: null, acceptsActions: true },
    measured: true, reason: null, calls, malformed: 0, partial: false, unreadSources: [],
    rankedAt: null, ageSeconds: null, stale: false, acceptsActions: true,
    overdueCount: calls.filter(c => c.overdue).length,
    ...extra,
  }
}

interface Api {
  calls: (CallsPayload | 'fail')[]
  reads: string[]
  sent: Record<string, unknown>[]
  act: (body: Record<string, unknown>) => { status: number; body: unknown }
  locale?: 'en' | 'hu'
}

let api: Api

function stubApi(...calls: (CallsPayload | 'fail')[]) {
  api = {
    calls, reads: [], sent: [],
    act: () => ({ status: 200, body: { delivered: true, outcome: 'Recorded by the publisher.', reason: null, errorClass: null } }),
  }
  vi.stubGlobal('fetch', vi.fn(async (url: string, init?: RequestInit) => {
    const json = (body: unknown, status = 200) => ({ ok: status < 400, status, json: async () => body })
    if (url === '/api/fleet/now') return json(nowPayload(api.locale))
    if (url.startsWith('/api/fleet/now/calls') && !url.startsWith('/api/fleet/now/calls/act')) {
      api.reads.push(url)
      const next = api.calls.length > 1 ? api.calls.shift()! : api.calls[0]
      return next === 'fail' ? json({ detail: 'boom' }, 500) : json(next)
    }
    if (url === '/api/fleet/now/calls/act') {
      const body = JSON.parse(String(init?.body))
      api.sent.push(body)
      const r = api.act(body)
      return json(r.body, r.status)
    }
    return json({}, 404)
  }))
}

const flush = () => act(async () => { await vi.advanceTimersByTimeAsync(1) })

async function mount(...calls: (CallsPayload | 'fail')[]) {
  stubApi(...calls)
  render(<Now />)
  await flush()
}

const callsTab = () => document.querySelector('[data-tab="calls"]') as HTMLElement
const openCalls = () => fireEvent.click(callsTab())
const card = (id: string) => document.querySelector(`[data-call="${id}"]`) as HTMLElement

beforeEach(() => { vi.useFakeTimers() })
afterEach(() => { cleanup(); vi.unstubAllGlobals(); vi.useRealTimers() })

describe('the Calls tab label', () => {
  it('counts the calls to make while the Now tab is open', async () => {
    await mount(callsPayload())
    expect(document.querySelector('[data-tab="now"]')!.getAttribute('aria-selected')).toBe('true')
    const badge = document.querySelector('[data-calls-count]')!
    expect(badge.textContent).toBe('2')
    expect(badge.getAttribute('data-overdue')).toBe('no')
    expect(callsTab().title).toBe('2 calls to make')
  })

  it('turns red and says so when a call is overdue', async () => {
    await mount(callsPayload({ calls: [call('c1', { overdue: true, due: '2026-10-28' }), call('c2')] }))
    expect(document.querySelector('[data-calls-count]')!.getAttribute('data-overdue')).toBe('yes')
    expect(callsTab().title).toBe('2 calls to make — 1 overdue')
  })

  it('a failed read is marked on the tab, never shown as calm', async () => {
    await mount('fail')
    expect(document.querySelector('[data-calls-fail]')).not.toBeNull()
    expect(document.querySelector('[data-calls-count]')).toBeNull()
    openCalls()
    expect(document.querySelector('[data-calls-error]')!.textContent).toContain('HTTP 500')
  })

  it('no badge for an empty list, and the empty view says so', async () => {
    await mount(callsPayload({ calls: [] }))
    expect(document.querySelector('[data-calls-count]')).toBeNull()
    openCalls()
    expect(document.querySelector('[data-calls-empty]')!.textContent).toContain('No calls to make.')
  })

  it('an undeclared publisher is not a failure', async () => {
    await mount(callsPayload({ publisher: { state: 'none', project: null, candidates: [], reason: 'no registered project declares owner-calls', acceptsActions: false }, measured: null, calls: [] }))
    expect(document.querySelector('[data-calls-fail]')).toBeNull()
    openCalls()
    expect(document.querySelector('[data-calls-none]')!.textContent).toContain('No call list is published')
  })
})

describe('a call card', () => {
  it('shows who, about, kind, due, phone as tel:, attempts and evidence', async () => {
    await mount(callsPayload({ calls: [call('c1', {
      kind: 'retry', due: '2026-11-02', phone: '+36 1 555 0101', attempts: 2,
      evidence: [{ label: 'mail 10-29', link: 'https://example.test/m/1' }],
    })] }))
    openCalls()
    const c = card('c1')
    expect(c.querySelector('[data-who]')!.textContent).toBe('Person c1')
    expect(c.querySelector('[data-about]')!.textContent).toBe('About c1')
    expect(c.querySelector('[data-call-kind]')!.textContent).toBe('again')
    expect(c.querySelector('[data-due]')!.textContent).toBe('due 11-02')
    expect(c.querySelector('[data-due]')!.getAttribute('data-overdue')).toBe('no')
    const phone = c.querySelector('[data-phone]') as HTMLAnchorElement
    expect(phone.getAttribute('href')).toBe('tel:+3615550101')
    expect(phone.textContent).toContain('+36 1 555 0101')
    expect(c.querySelector('[data-attempts]')!.textContent).toBe('2× no answer')
    expect(c.textContent).toContain('mail 10-29')
  })

  it('an overdue call has a red due chip', async () => {
    await mount(callsPayload({ calls: [call('c1', { due: '2026-10-28', overdue: true })] }))
    openCalls()
    const due = card('c1').querySelector('[data-due]')!
    expect(due.getAttribute('data-overdue')).toBe('yes')
    expect(due.textContent).toBe('overdue 10-28')
    expect(due.className).toContain('text-status-fail')
  })

  it('a read-only publisher gets no buttons, and says why', async () => {
    await mount(callsPayload({ acceptsActions: false }))
    openCalls()
    expect(document.querySelector('[data-call-actions]')).toBeNull()
    expect(document.querySelector('[data-calls-readonly]')).not.toBeNull()
  })
})

describe('the answers send the right body', () => {
  it('Called opens a note; Enter sends it with the text, and the publisher\'s sentence is shown', async () => {
    await mount(callsPayload())
    openCalls()
    fireEvent.click(screen.getAllByText('Called')[0])
    const input = screen.getByLabelText('How did it go? (optional)')
    fireEvent.change(input, { target: { value: 'they send it Monday' } })
    fireEvent.keyDown(input, { key: 'Enter' })
    await flush()
    expect(api.sent).toEqual([{ id: 'c1', action: 'called', text: 'they send it Monday' }])
    expect(document.querySelector('[data-feedback="ok"]')!.textContent).toContain('Recorded by the publisher.')
    // The list is re-read with refresh after a delivered answer.
    expect(api.reads.at(-1)).toBe('/api/fleet/now/calls?refresh=true')
  })

  it('Called with an empty note sends no text', async () => {
    await mount(callsPayload())
    openCalls()
    fireEvent.click(screen.getAllByText('Called')[0])
    fireEvent.click(screen.getByText('Done'))
    await flush()
    expect(api.sent).toEqual([{ id: 'c1', action: 'called' }])
  })

  it('No answer and Not needed send their action', async () => {
    await mount(callsPayload())
    openCalls()
    fireEvent.click(card('c2').querySelector('[data-call-actions]')!.querySelectorAll('button')[1])
    await flush()
    fireEvent.click(screen.getAllByText('Not needed')[0])
    await flush()
    expect(api.sent).toEqual([{ id: 'c2', action: 'no-answer' }, { id: 'c1', action: 'not-needed' }])
  })

  it('Later offers the choices and sends an until', async () => {
    vi.setSystemTime(new Date('2026-10-30T10:00:00Z'))
    await mount(callsPayload())
    openCalls()
    fireEvent.click(screen.getAllByText('Later')[0])
    fireEvent.click(card('c1').querySelector('[data-call-later]')!.querySelectorAll('button')[1])
    await flush()
    expect(api.sent).toHaveLength(1)
    expect(api.sent[0]).toMatchObject({ id: 'c1', action: 'later' })
    expect(Date.parse(String(api.sent[0].until)) - Date.parse('2026-10-30T10:00:00Z')).toBeGreaterThanOrEqual(3600_000)
  })

  it('a refusal stays on screen with the publisher\'s reason', async () => {
    await mount(callsPayload())
    api.act = () => ({ status: 409, body: { detail: 'that call is no longer in the publisher\'s answer' } })
    openCalls()
    fireEvent.click(screen.getAllByText('Not needed')[0])
    await flush()
    expect(document.querySelector('[data-feedback="fail"]')!.textContent).toContain('no longer in the publisher')
  })
})

describe('Hungarian locale', () => {
  it('labels the tab, the kinds and the buttons in Hungarian; the publisher\'s text is untouched', async () => {
    stubApi(callsPayload({ calls: [call('c1', { kind: 'missed', attempts: 2 }), call('c2', { kind: 'follow-up' })] }))
    api.locale = 'hu'
    render(<Now />)
    await flush()
    expect(callsTab().textContent).toContain('Hívások')
    openCalls()
    expect(card('c1').querySelector('[data-call-kind]')!.textContent).toBe('nem vettem fel')
    expect(card('c2').querySelector('[data-call-kind]')!.textContent).toBe('folytatás')
    expect(card('c1').querySelector('[data-attempts]')!.textContent).toBe('2× nem vette fel')
    for (const label of ['Felhívtam', 'Nem vette fel', 'Később', 'Nem kell']) {
      expect(screen.getAllByText(label).length).toBeGreaterThan(0)
    }
    expect(card('c1').querySelector('[data-who]')!.textContent).toBe('Person c1')
  })
})

describe('helpers', () => {
  it('callsCount counts only a measured answer', () => {
    expect(callsCount(null)).toEqual({ open: 0, overdue: 0 })
    expect(callsCount(callsPayload({ measured: false, calls: [] }))).toEqual({ open: 0, overdue: 0 })
    expect(callsCount(callsPayload({ calls: [call('a', { overdue: true }), call('b')] }))).toEqual({ open: 2, overdue: 1 })
  })

  it('callsFailure: a load error and an unmeasured read are failures; not declared is not', () => {
    expect(callsFailure(null, 'HTTP 500')).toContain('HTTP 500')
    expect(callsFailure(callsPayload({ measured: false, reason: 'exit 2' }), null)).toContain('exit 2')
    expect(callsFailure(callsPayload({ measured: null }), null)).toBeNull()
  })

  it('callsNotes names partial, stale and malformed', () => {
    const notes = callsNotes(callsPayload({ partial: true, unreadSources: ['mailbox'], stale: true, ageSeconds: 9 * 3600, malformed: 2 }))
    expect(notes).toHaveLength(3)
    expect(notes[0]).toBe('partial — the publisher could not read: mailbox')
    expect(notes[1]).toMatch(/^listed 9/)
    expect(notes[2]).toBe('2 calls unreadable, skipped')
  })

  it('dueLabel: a bare date as MM-DD, a datetime in the card clock format', () => {
    expect(dueLabel('2026-11-02')).toBe('11-02')
    const now = new Date('2026-10-30T12:00:00')
    expect(dueLabel('2026-10-30T15:30:00', now)).toBe('15:30')
    expect(dueLabel('2026-11-03T09:05:00', now)).toBe('11-03 09:05')
    expect(dueLabel('soon')).toBe('soon')
  })
})
