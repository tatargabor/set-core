/**
 * The Now card's Goals tab (fleet-now-card 7.4), against a stubbed API.
 *
 * As in nowCard.test.tsx, what is asserted is what the owner sees and what is SENT:
 * every verdict's request body is read back.
 */
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { act, cleanup, fireEvent, render, screen } from '@testing-library/react'

vi.mock('../../src/hooks/useSonioxAvailable', () => ({
  useSonioxAvailable: () => ({ checked: true, hasKey: false, apiKey: null, micSupported: true }),
}))
vi.mock('../../src/components/VoiceInput', () => ({ default: () => null }))

import Now, { FEEDBACK_MS, GOALS_POLL_MS, POLL_MS } from '../../src/pages/Now'
import { evidenceTarget, goalsFailure, goalsNotes, progressPercent } from '../../src/lib/nowCard'
import type { Goal, GoalAdvice, GoalsPayload, NowPayload } from '../../src/lib/nowCard'

function nowPayload(): NowPayload {
  return {
    item: {
      source: 'owner-queue', id: 'i1', project: 'alpha', sentence: 'Call the supplier back', why: 'Friday',
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
    generatedAt: new Date().toISOString(),
  }
}

function goal(id: string, extra: Partial<Goal> = {}): Goal {
  return { id, title: `Goal ${id}`, status: 'proposed', projects: [], evidence: [], ...extra }
}

function advice(id: string, extra: Partial<GoalAdvice> = {}): GoalAdvice {
  return { id, kind: 'merge', sentence: `Suggestion ${id}`, why: `Because ${id}`, ...extra }
}

function goalsPayload(extra: Partial<GoalsPayload> = {}): GoalsPayload {
  const goals = extra.goals ?? [goal('g1'), goal('g2', { status: 'confirmed' })]
  return {
    publisher: { state: 'ok', project: 'pub', candidates: ['pub'], reason: null, acceptsActions: true },
    measured: true, reason: null, goals, advice: [],
    malformedGoals: 0, malformedAdvice: 0, partial: false, unreadSources: [],
    synthesizedAt: null, ageSeconds: null, stale: false, acceptsVerdicts: true,
    proposedCount: goals.filter(g => g.status === 'proposed').length,
    ...extra,
  }
}

interface Api {
  goals: (GoalsPayload | 'fail')[]
  goalReads: string[]
  sent: Record<string, unknown>[]
  act: (body: Record<string, unknown>) => { status: number; body: unknown }
}

let api: Api

function stubApi(...goals: (GoalsPayload | 'fail')[]) {
  api = {
    goals, goalReads: [], sent: [],
    act: () => ({ status: 200, body: { delivered: true, outcome: null, reason: null, errorClass: null } }),
  }
  vi.stubGlobal('fetch', vi.fn(async (url: string, init?: RequestInit) => {
    const json = (body: unknown, status = 200) => ({ ok: status < 400, status, json: async () => body })
    if (url === '/api/fleet/now') return json(nowPayload())
    if (url.startsWith('/api/fleet/now/goals') && !url.startsWith('/api/fleet/now/goals/act')) {
      api.goalReads.push(url)
      const next = api.goals.length > 1 ? api.goals.shift()! : api.goals[0]
      return next === 'fail' ? json({ detail: 'boom' }, 500) : json(next)
    }
    if (url === '/api/fleet/now/goals/act') {
      const body = JSON.parse(String(init?.body))
      api.sent.push(body)
      const r = api.act(body)
      return json(r.body, r.status)
    }
    return json({}, 404)
  }))
}

const flush = () => act(async () => { await vi.advanceTimersByTimeAsync(1) })

async function mount(...goals: (GoalsPayload | 'fail')[]) {
  stubApi(...goals)
  render(<Now />)
  await flush()
}

const goalsTab = () => document.querySelector('[data-tab="goals"]') as HTMLElement
const openGoals = () => fireEvent.click(goalsTab())

beforeEach(() => { vi.useFakeTimers() })
afterEach(() => { cleanup(); vi.unstubAllGlobals(); vi.useRealTimers() })

describe('the tab strip', () => {
  it('AC-40 (unit half): Now is the default; Goals replaces the item in the same window and Now brings it back', async () => {
    await mount(goalsPayload())
    expect(document.querySelector('[data-tab="now"]')!.getAttribute('aria-selected')).toBe('true')
    expect(document.querySelector('[data-now-item]')).not.toBeNull()
    expect(document.querySelector('[data-goals-view]')).toBeNull()

    const strip = document.querySelector('[data-tabs]')!
    openGoals()
    expect(goalsTab().getAttribute('aria-selected')).toBe('true')
    expect(document.querySelector('[data-now-item]')).toBeNull()
    expect(document.querySelector('[data-goals-view]')).not.toBeNull()
    expect(screen.getByText('Goal g1')).toBeTruthy()
    // The same strip element, still the header's first child: switching did not rebuild or move it.
    expect(document.querySelector('[data-tabs]')).toBe(strip)
    expect(strip.parentElement!.firstElementChild).toBe(strip)

    fireEvent.click(document.querySelector('[data-tab="now"]')!)
    expect(document.querySelector('[data-now-item]')).not.toBeNull()
    expect(document.querySelector('[data-goals-view]')).toBeNull()
  })

  it('both tabs have the same classes apart from the active colour — no weight or padding change', async () => {
    await mount(goalsPayload())
    const cls = (el: Element) => el.className.split(' ').filter(c => !/^(border-status|border-transparent|bg-|text-|hover:|shadow)/.test(c)).sort()
    const nowTab = document.querySelector('[data-tab="now"]')!
    expect(cls(nowTab)).toEqual(cls(goalsTab()))
  })

  it('AC-41: three proposed goals are counted on the Goals label while Now is open', async () => {
    await mount(goalsPayload({ goals: [goal('a'), goal('b'), goal('c'), goal('d', { status: 'confirmed' })] }))
    expect(document.querySelector('[data-tab="now"]')!.getAttribute('aria-selected')).toBe('true')
    expect(goalsTab().textContent).toContain('Goals')
    expect(document.querySelector('[data-goals-count]')!.textContent).toBe('3')
    expect(goalsTab().getAttribute('title')).toContain('3 proposed goals await your verdict')
  })

  it('no proposed goals → no count on the label', async () => {
    await mount(goalsPayload({ goals: [goal('a', { status: 'confirmed' })] }))
    expect(document.querySelector('[data-goals-count]')).toBeNull()
  })

  it('AC-37: a failed goals read puts a failure marker on the Goals label, visible from the Now tab', async () => {
    await mount('fail')
    expect(document.querySelector('[data-tab="now"]')!.getAttribute('aria-selected')).toBe('true')
    expect(goalsTab().querySelector('[data-goals-fail]')).not.toBeNull()
    expect(goalsTab().getAttribute('title')).toContain('Goals could not load')
    openGoals()
    expect(document.querySelector('[data-goals-error]')!.textContent).toContain('HTTP 500')
  })

  it('AC-37: an unmeasured answer (the publisher command failed) is marked the same way', async () => {
    await mount(goalsPayload({ measured: false, reason: 'the project did not answer within 30s', goals: [], proposedCount: 0 }))
    expect(goalsTab().querySelector('[data-goals-fail]')).not.toBeNull()
    openGoals()
    expect(document.querySelector('[data-goals-error]')!.textContent).toContain('did not answer within 30s')
  })

  it('a later failure keeps the last good goals on screen, marked as failed', async () => {
    await mount(goalsPayload(), 'fail')
    await act(async () => { await vi.advanceTimersByTimeAsync(GOALS_POLL_MS) })
    openGoals()
    expect(screen.getByText('Goal g1')).toBeTruthy()
    expect(document.querySelector('[data-goals-error]')).not.toBeNull()
  })

  it('goals are read on load and then at most once a minute, even though the card polls faster', async () => {
    await mount(goalsPayload())
    expect(GOALS_POLL_MS).toBeGreaterThanOrEqual(60_000)
    expect(api.goalReads).toHaveLength(1)
    await act(async () => { await vi.advanceTimersByTimeAsync(POLL_MS) })
    expect(api.goalReads).toHaveLength(1)
    await act(async () => { await vi.advanceTimersByTimeAsync(GOALS_POLL_MS - POLL_MS) })
    expect(api.goalReads).toHaveLength(2)
  })

  it('AC-34: no publisher → "No goals are published", no failure marker, and the Now tab is unaffected', async () => {
    await mount(goalsPayload({
      publisher: { state: 'none', project: null, candidates: [], reason: "no registered project declares 'owner-goals'", acceptsActions: false },
      measured: null, reason: "no registered project declares 'owner-goals'", goals: [], proposedCount: 0, acceptsVerdicts: false,
    }))
    expect(goalsTab().querySelector('[data-goals-fail]')).toBeNull()
    expect(document.querySelector('[data-now-item]')).not.toBeNull()
    openGoals()
    expect(document.querySelector('[data-goals-none]')!.textContent).toContain('No goals are published')
  })
})

describe('the goals list', () => {
  it('AC-35: a proposed goal is marked unconfirmed with Keep, Not a goal and Rename; a confirmed one only Not a goal', async () => {
    await mount(goalsPayload())
    openGoals()
    const proposed = document.querySelector('[data-goal="g1"]')!
    expect(proposed.querySelector('[data-unconfirmed]')!.textContent).toBe('unconfirmed')
    const labels = Array.from(proposed.querySelectorAll('[data-goal-actions] button')).map(b => b.textContent)
    expect(labels).toEqual(['Keep', 'Rename', 'Not a goal'])
    const confirmed = document.querySelector('[data-goal="g2"]')!
    expect(confirmed.querySelector('[data-unconfirmed]')).toBeNull()
    expect(confirmed.querySelector('[data-goal-actions]')).toBeNull()
    expect(confirmed.querySelector('[data-goal-drop]')!.textContent).toBe('Not a goal')
  })

  it('shows serves, deadline, projects, progress with a bar, open items and evidence', async () => {
    await mount(goalsPayload({ goals: [goal('g1', {
      serves: 'Grow the service line', deadline: '2027-03-01', projects: ['publisher-app', 'site'],
      progress: { text: '3 of 4 milestones', done: 3, total: 4 }, openItems: 5,
      evidence: [{ label: 'plan', link: '/x/docs/plan.md' }, { label: 'call notes' }],
    })] }))
    openGoals()
    const row = document.querySelector('[data-goal="g1"]')!
    expect(row.querySelector('[data-goal-meta]')!.textContent).toBe('serves: Grow the service line · publisher-app, site')
    expect(row.textContent).toContain('due 2027-03-01')
    expect(row.querySelector('[data-progress]')!.textContent).toContain('3 of 4 milestones')
    expect((row.querySelector('[data-progress] [style]') as HTMLElement).style.width).toBe('75%')
    expect(row.querySelector('[data-open-items]')!.textContent).toBe('5 open cards')
    expect(row.querySelector('[data-evidence]')!.textContent).toContain('call notes')
  })

  it('an evidence file path goes to the desktop opener, as file links on the card do', async () => {
    await mount(goalsPayload({ goals: [goal('g1', { evidence: [{ label: 'plan', link: '/x/docs/plan.md' }] })] }))
    openGoals()
    fireEvent.click(screen.getByText('plan'))
    await flush()
    const calls = (globalThis.fetch as unknown as { mock: { calls: [string, RequestInit?][] } }).mock.calls
    const open = calls.find(c => c[0] === '/api/desktop/open')!
    expect(JSON.parse(String(open[1]!.body))).toEqual({ path: '/x/docs/plan.md' })
  })

  it('AC-38: Keep sends {id, action: keep}, shows the outcome, and re-reads with refresh', async () => {
    await mount(goalsPayload(), goalsPayload({ goals: [goal('g1', { status: 'confirmed' })] }))
    api.act = () => ({ status: 200, body: { delivered: true, outcome: 'Kept as a goal', reason: null, errorClass: null } })
    openGoals()
    fireEvent.click(screen.getByText('Keep'))
    await flush()
    expect(api.sent).toEqual([{ id: 'g1', action: 'keep' }])
    expect(api.goalReads.at(-1)).toBe('/api/fleet/now/goals?refresh=true')
    expect(document.querySelector('[data-feedback="ok"]')!.textContent).toContain('Kept as a goal')
    expect(document.querySelector('[data-goal="g1"]')!.getAttribute('data-status')).toBe('confirmed')
    await act(async () => { await vi.advanceTimersByTimeAsync(FEEDBACK_MS) })
    expect(document.querySelector('[data-feedback]')).toBeNull()
  })

  it('Not a goal sends drop, on a proposed and on a confirmed goal', async () => {
    await mount(goalsPayload())
    openGoals()
    fireEvent.click(document.querySelector('[data-goal="g1"] [data-goal-actions] button:nth-child(3)')!)
    await flush()
    fireEvent.click(document.querySelector('[data-goal="g2"] [data-goal-drop]')!)
    await flush()
    expect(api.sent).toEqual([{ id: 'g1', action: 'drop' }, { id: 'g2', action: 'drop' }])
  })

  it('Rename opens an inline field; Enter sends the new text; an unchanged title sends nothing', async () => {
    await mount(goalsPayload())
    openGoals()
    fireEvent.click(screen.getByText('Rename'))
    const field = screen.getByLabelText('New goal title') as HTMLInputElement
    expect(field.value).toBe('Goal g1')
    fireEvent.keyDown(field, { key: 'Enter' })
    await flush()
    expect(api.sent).toEqual([])
    fireEvent.change(field, { target: { value: '  Ship the pilot  ' } })
    fireEvent.keyDown(field, { key: 'Enter' })
    await flush()
    expect(api.sent).toEqual([{ id: 'g1', action: 'rename', text: 'Ship the pilot' }])
  })

  it('a refusal shows the publisher\'s reason and stays past 10 s', async () => {
    await mount(goalsPayload())
    api.act = () => ({ status: 409, body: { detail: 'that goal is no longer in the publisher\'s answer' } })
    openGoals()
    fireEvent.click(screen.getByText('Keep'))
    await flush()
    await act(async () => { await vi.advanceTimersByTimeAsync(FEEDBACK_MS + 1000) })
    expect(document.querySelector('[data-feedback="fail"]')!.textContent).toContain('no longer in the publisher')
  })
})

describe('suggestions', () => {
  it('AC-36: advice shows under Suggestions with kind, sentence, reason, and Accept / Decline send their verdicts', async () => {
    await mount(goalsPayload({ advice: [advice('a1', { goalId: 'g1' }), advice('a2', { kind: 'neglected' })] }))
    openGoals()
    const section = document.querySelector('[data-suggestions]')!
    expect(section.textContent).toContain('Suggestions')
    const first = section.querySelector('[data-advice="a1"]')!
    expect(first.querySelector('[data-kind]')!.textContent).toBe('merge')
    expect(first.textContent).toContain('Suggestion a1')
    expect(first.textContent).toContain('on "Goal g1" — Because a1')
    fireEvent.click(first.querySelector('button')!)                 // Accept
    await flush()
    fireEvent.click(section.querySelector('[data-advice="a2"] button:nth-child(2)')!)  // Decline
    await flush()
    expect(api.sent).toEqual([{ id: 'a1', action: 'accept' }, { id: 'a2', action: 'decline' }])
  })

  it('no advice → no Suggestions section', async () => {
    await mount(goalsPayload())
    openGoals()
    expect(document.querySelector('[data-suggestions]')).toBeNull()
  })
})

describe('read-only and incomplete answers', () => {
  it('AC-39: without a write command the goals are shown read-only with the reason, and no verdict buttons', async () => {
    await mount(goalsPayload({
      acceptsVerdicts: false,
      publisher: { state: 'ok', project: 'pub', candidates: ['pub'], reason: null, acceptsActions: false },
      advice: [advice('a1')],
    }))
    openGoals()
    expect(document.querySelector('[data-goals-readonly]')!.textContent).toContain('accepts no verdicts')
    expect(screen.getByText('Goal g1')).toBeTruthy()
    expect(document.querySelector('[data-goal="g1"] [data-unconfirmed]')).not.toBeNull()
    expect(document.querySelector('[data-goal-actions]')).toBeNull()
    expect(document.querySelector('[data-goal-drop]')).toBeNull()
    expect(document.querySelector('[data-suggestions] button')).toBeNull()
  })

  it('partial, stale, unread sources and malformed counts are a muted line; nothing is hidden', async () => {
    await mount(goalsPayload({ partial: true, unreadSources: ['mailbox — token expired'], stale: true,
      ageSeconds: 40 * 3600, malformedGoals: 2, malformedAdvice: 1 }))
    openGoals()
    const notes = document.querySelector('[data-goals-notes]')!.textContent!
    expect(notes).toContain('partial — the publisher could not read: mailbox — token expired')
    expect(notes).toContain('synthesised 40 h ago')
    expect(notes).toContain('2 goals and 1 suggestion unreadable, skipped')
    expect(screen.getByText('Goal g1')).toBeTruthy()
    // A partial answer is a note, not a read failure: the label carries no failure marker.
    expect(goalsTab().querySelector('[data-goals-fail]')).toBeNull()
  })
})

describe('pure helpers', () => {
  it('goalsFailure: not declared is not a failure; unmeasured and a load error are', () => {
    expect(goalsFailure(goalsPayload({ measured: null }), null)).toBeNull()
    expect(goalsFailure(goalsPayload(), null)).toBeNull()
    expect(goalsFailure(goalsPayload({ measured: false, reason: 'x' }), null)).toBe('Goals could not be read: x')
    expect(goalsFailure(null, 'HTTP 502')).toBe('Goals could not load: HTTP 502')
  })

  it('goalsNotes: a complete, fresh answer has no notes; a partial one without names still says so', () => {
    expect(goalsNotes(goalsPayload())).toEqual([])
    expect(goalsNotes(goalsPayload({ partial: true }))).toEqual(['partial — the publisher says this list is incomplete'])
  })

  it('progressPercent and evidenceTarget', () => {
    expect(progressPercent({ text: 't' })).toBeNull()
    expect(progressPercent({ text: 't', done: 1, total: 0 })).toBeNull()
    expect(progressPercent({ text: 't', done: 5, total: 4 })).toBe(100)
    expect(evidenceTarget('/x/docs/a.md')).toEqual({ kind: 'file', href: '/x/docs/a.md' })
    expect(evidenceTarget('/p/alpha/status')).toEqual({ kind: 'link', href: '/p/alpha/status' })
    expect(evidenceTarget('https://example.test/a')).toEqual({ kind: 'link', href: 'https://example.test/a' })
  })
})
