/**
 * The Now card (fleet-now-card 4.1–4.10), against a stubbed API.
 *
 * What is asserted is what the owner sees and what is SENT — the request body of
 * every action is read back, because a card that shows "done" while sending the
 * wrong id is the defect class of reporting a 200 as an arrival.
 */
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { act, cleanup, fireEvent, render, screen } from '@testing-library/react'

const voice = vi.hoisted(() => ({ available: { checked: true, hasKey: false, apiKey: null as string | null, micSupported: true } }))
vi.mock('../../src/hooks/useSonioxAvailable', () => ({ useSonioxAvailable: () => voice.available }))
vi.mock('../../src/components/VoiceInput', () => ({
  default: ({ onTranscript }: { onTranscript: (t: string) => void }) => (
    <button data-stub-mic onClick={() => onTranscript('spoken words')}>mic</button>
  ),
}))

import Now, { FEEDBACK_MS, POLL_MS } from '../../src/pages/Now'
import { checkView, clockTime, emptyMessage, gapMarkers, hoursAgo, laterChoices, needsReasons, timeLine } from '../../src/lib/nowCard'
import type { NowItem, NowPayload } from '../../src/lib/nowCard'

function item(extra: Partial<NowItem> = {}): NowItem {
  return {
    source: 'owner-queue', id: 'i1', project: 'alpha', sentence: 'Call the supplier back',
    why: 'They hold the order until Friday', options: [], acceptsText: false, delegable: false,
    actions: ['goThere', 'done', 'later'], goThere: { kind: 'project', href: '/p/alpha/status' }, ...extra,
  }
}

function payload(extra: Partial<NowPayload> = {}): NowPayload {
  return {
    item: item(), following: 0, heldBack: 0,
    sources: [{ name: 'owner-queue', measured: true, reason: null, count: 1 },
              { name: 'agent-questions', measured: true, reason: null, count: 0 }],
    unmeasured: 0,
    publisher: { state: 'ok', project: 'pub', candidates: ['pub'], reason: null, acceptsActions: true },
    partial: false, malformed: 0, rankedAt: null, rankingAgeSeconds: null, stale: false,
    closedToday: 2, parkedIdeas: 0,
    cue: { play: false, reason: null, variant: null, slowed: false, intervalSeconds: 600 },
    windDown: { active: false, hour: 21, delegableIds: [] },
    tomorrowNote: null, focus: [], focusMax: 3, focusSetToday: false, focusCandidates: ['alpha', 'beta'],
    generatedAt: new Date().toISOString(), ...extra,
  }
}

interface Api {
  now: NowPayload[]
  act: (body: Record<string, unknown>) => Record<string, unknown>
  sent: Record<string, unknown>[]
  focus: Record<string, unknown>[]
  groups: Record<string, unknown>[]
}

let api: Api

function stubApi(first: NowPayload, ...rest: NowPayload[]) {
  api = {
    now: [first, ...rest],
    act: () => ({ delivered: true, sent: true, outcome: null, reason: null, errorClass: null, closedToday: 3, parkedIdeas: 0 }),
    sent: [], focus: [], groups: [],
  }
  vi.stubGlobal('fetch', vi.fn(async (url: string, init?: RequestInit) => {
    const json = (body: unknown, status = 200) => ({ ok: status < 400, status, json: async () => body })
    if (url === '/api/fleet/now') return json(api.now.length > 1 ? api.now.shift() : api.now[0])
    if (url === '/api/fleet/now/act') {
      const body = JSON.parse(String(init?.body))
      api.sent.push(body)
      return json(api.act(body))
    }
    if (url === '/api/fleet/now/groups') {
      const body = JSON.parse(String(init?.body))
      api.groups.push(body)
      return json({ ok: true, muted: body.muted })
    }
    if (url === '/api/fleet/now/focus') {
      const body = JSON.parse(String(init?.body))
      api.focus.push(body)
      return json({ ok: true, swap: false, focus: body.projects, removed: [] })
    }
    return json({}, 404)
  }))
}

const flush = () => act(async () => { await vi.advanceTimersByTimeAsync(1) })

async function mount(first: NowPayload, ...rest: NowPayload[]) {
  stubApi(first, ...rest)
  render(<Now />)
  await flush()
}

beforeEach(() => {
  vi.useFakeTimers()
  voice.available = { checked: true, hasKey: false, apiKey: null, micSupported: true }
})
afterEach(() => { cleanup(); vi.unstubAllGlobals(); vi.useRealTimers() })

// --------------------------------------------------------------------------- 4.1

describe('one item, never a list', () => {
  it('AC-1: shows the first item and how many follow, without their titles', async () => {
    await mount(payload({ following: 4 }))
    expect(screen.getByText('Call the supplier back')).toBeTruthy()
    expect(screen.getByText('They hold the order until Friday')).toBeTruthy()
    expect(document.querySelector('[data-following]')!.textContent).toContain('4 more')
    expect(document.querySelectorAll('h1')).toHaveLength(1)
  })

  it('AC-2: nothing waiting, every source read → says so, with the closed count', async () => {
    await mount(payload({ item: null }))
    const empty = document.querySelector('[data-empty]')!.textContent!
    expect(empty).toContain('Nothing is waiting.')
    expect(empty).toContain('2 closed today')
  })

  it('a server older than the card (HTML at the API path) is named, not shown as a parse error', async () => {
    vi.stubGlobal('fetch', vi.fn(async () => ({
      ok: true, status: 200, headers: new Headers({ 'content-type': 'text/html' }),
      json: async () => { throw new SyntaxError('Unexpected token <') },
    })))
    render(<Now />)
    await flush()
    const markers = document.querySelector('[data-markers]')!.textContent!
    expect(markers).toContain('predates the Now card')
    expect(markers).not.toContain('Unexpected token')
    expect(document.body.textContent).not.toContain('Nothing is waiting')
  })

  it('polls again after the interval', async () => {
    await mount(payload(), payload({ item: item({ id: 'i2', sentence: 'Second thing' }) }))
    await act(async () => { await vi.advanceTimersByTimeAsync(POLL_MS) })
    expect(screen.getByText('Second thing')).toBeTruthy()
  })
})

// --------------------------------------------------------------------------- 4.2

describe('gaps are marked on the card', () => {
  it('AC-3: an unreadable owner queue is named, and "nothing waiting" is NOT said', async () => {
    await mount(payload({
      item: null, unmeasured: 1,
      sources: [{ name: 'owner-queue', measured: false, reason: 'the status command exited 2', count: null }],
    }))
    const markers = document.querySelector('[data-markers]')!.textContent!
    expect(markers).toContain('owner-queue — the status command exited 2')
    expect(document.body.textContent).not.toContain('Nothing is waiting')
  })

  it('AC-5: no publisher → "No ranked queue is published"', async () => {
    await mount(payload({ publisher: { state: 'none', project: null, candidates: [], reason: 'none', acceptsActions: false },
      sources: [{ name: 'owner-queue', measured: null, reason: 'none', count: null }] }))
    expect(document.querySelector('[data-markers]')!.textContent).toContain('No ranked queue is published')
  })

  it('AC-25 / AC-15: a stale ranking, a partial queue and slowed cues are all shown', async () => {
    await mount(payload({ stale: true, rankingAgeSeconds: 6 * 3600, partial: true,
      cue: { play: false, reason: null, variant: null, slowed: true, intervalSeconds: 1200 } }))
    const markers = document.querySelector('[data-markers]')!.textContent!
    expect(markers).toContain('ranked 6 h ago')
    expect(markers).toContain('Queue is partial')
    expect(markers).toContain('cues slowed')
  })

  it('the publisher\'s unread sources block the "nothing waiting" sentence', () => {
    const p = payload({ item: null, unreadSources: ['mailbox'] })
    expect(emptyMessage(p)).not.toContain('Nothing is waiting')
    expect(gapMarkers(p).map(m => m.text)).toContain('Publisher could not read: mailbox')
  })

  it('a source unmeasured by design is a quiet note; a failed one is a warning, and both still block "nothing waiting"', () => {
    const p = payload({
      item: null, unmeasured: 2,
      sources: [
        { name: 'project-questions', measured: false, reason: 'not agreed yet', count: 0 },
        { name: 'bus-owner', measured: false, reason: 'sac timed out', count: 0 },
      ],
    })
    const m = gapMarkers(p)
    expect(m).toContainEqual({ tone: 'info', text: 'not set up: project-questions' })
    expect(m.find(x => x.tone === 'warn')!.text).toBe('1 source could not be read: bus-owner — sac timed out')
    expect(emptyMessage(p)).not.toContain('Nothing is waiting')
  })
})

// --------------------------------------------------------------------------- 4.3 / 4.6

describe('not needed', () => {
  it('asks why in one line and closes the card with that reason', async () => {
    await mount(payload())
    fireEvent.click(document.querySelector('[data-not-needed]')!)
    fireEvent.change(screen.getByLabelText('Why not needed'), { target: { value: 'we moved the domain elsewhere' } })
    fireEvent.click(screen.getByText('Close it'))
    await flush()
    expect(api.sent.at(-1)).toMatchObject({ action: 'done', text: 'Not needed: we moved the domain elsewhere' })
  })
})

describe('go there to a file', () => {
  it('hands a file to the desktop opener, and says so when it cannot', async () => {
    await mount(payload({ item: item({ goThere: { kind: 'file', href: '/x/docs/plan.md' } }) }))
    fireEvent.click(screen.getByText('Go there'))
    await flush()
    const calls = (globalThis.fetch as unknown as { mock: { calls: [string, RequestInit?][] } }).mock.calls
    const open = calls.find(c => c[0] === '/api/desktop/open')!
    expect(JSON.parse(String(open[1]!.body))).toEqual({ path: '/x/docs/plan.md' })
    expect(document.body.textContent).toContain('Could not open /x/docs/plan.md')
  })
})

describe('tag strip', () => {
  const groups = [{ name: 'a', count: 2, muted: false }, { name: 'b', count: 1, muted: true }]

  it('clicking a tag switches it off (or back on) with the whole list, and a switched-off tag keeps its count', async () => {
    const after = [{ name: 'a', count: 2, muted: true }, { name: 'b', count: 1, muted: true }]
    await mount(payload({ groups }), payload({ groups: after }))
    const strip = document.querySelector('[data-tags]')!
    expect(strip.textContent).toContain('b 1')
    fireEvent.click(document.querySelector('[data-tag="a"]')!)
    await flush()
    expect(api.groups.at(-1)).toEqual({ muted: ['b', 'a'] })
    fireEvent.click(document.querySelector('[data-tag="b"]')!)
    await flush()
    expect(api.groups.at(-1)).toEqual({ muted: ['a'] })
  })

  it('"all on" clears every switch', async () => {
    await mount(payload({ groups }))
    fireEvent.click(document.querySelector('[data-tags-all]')!)
    await flush()
    expect(api.groups.at(-1)).toEqual({ muted: [] })
  })

  it('hidden cards are counted under the card and in the empty state — never "nothing is waiting"', async () => {
    await mount(payload({ groups, mutedHidden: 4 }))
    expect(document.querySelector('[data-following]')!.textContent).toContain('4 hidden by switched-off tags')
    const empty = payload({ item: null, groups, mutedHidden: 4 })
    expect(emptyMessage(empty)).toBe('Nothing in the switched-on tags — 4 hidden by switched-off ones.')
  })
})

describe('help', () => {
  it('the ? button opens a legend over the card that names every control, and the card stays', async () => {
    await mount(payload())
    expect(document.querySelector('[data-help]')).toBeNull()
    fireEvent.click(screen.getByLabelText('Help'))
    const legend = document.querySelector('[data-help]')!.textContent!
    for (const term of ['Blue buttons', 'Text field', 'Go there', 'Done', 'Later', 'focus', 'Grey note', 'Yellow note']) {
      expect(legend).toContain(term)
    }
    expect(document.querySelector('[data-now-item]')).not.toBeNull()
  })

  it('the header numbers say what they count', async () => {
    await mount(payload({ closedToday: 2, parkedIdeas: 1 }))
    expect(document.querySelector('[data-closed]')!.textContent).toContain('2 closed')
    expect(document.querySelector('[data-parked]')!.textContent).toContain('1 parked')
  })
})

describe('one-tap answers and their feedback', () => {
  it('AC-24 / AC-6 / AC-12: an option is sent with the id, the outcome shows, then closes after 10 s', async () => {
    const opts = [{ id: 'a', label: 'Approve' }, { id: 'b', label: 'Hold' }, { id: 'c', label: 'Ask again' }]
    await mount(payload({ item: item({ options: opts, actions: ['goThere', 'done', 'later', 'answer'] }) }))
    expect(document.querySelectorAll('[data-options] button')).toHaveLength(3)
    api.act = () => ({ delivered: true, sent: true, outcome: 'the agent resumed', reason: null, errorClass: null, closedToday: 3, parkedIdeas: 0 })
    fireEvent.click(screen.getByText('Hold'))
    await flush()
    expect(api.sent[0]).toMatchObject({ id: 'i1', source: 'owner-queue', action: 'answer', option: 'b' })
    const toast = document.querySelector('[data-feedback="ok"]')!
    expect(toast.textContent).toContain('the agent resumed')
    expect(toast.textContent).toContain('3 closed today')
    await act(async () => { await vi.advanceTimersByTimeAsync(FEEDBACK_MS + 10) })
    expect(document.querySelector('[data-feedback]')).toBeNull()
  })

  it('AC-7: a refusal shows the project\'s reason, stays past 10 s, and the item stays', async () => {
    await mount(payload())
    api.act = () => ({ delivered: false, sent: true, outcome: null, reason: 'already closed elsewhere', errorClass: 'nonzero-exit', closedToday: 2, parkedIdeas: 0 })
    fireEvent.click(screen.getByText('Done'))
    await flush()
    await act(async () => { await vi.advanceTimersByTimeAsync(FEEDBACK_MS * 2) })
    expect(document.querySelector('[data-feedback="fail"]')!.textContent).toContain('already closed elsewhere')
    expect(screen.getByText('Call the supplier back')).toBeTruthy()
    fireEvent.click(screen.getByLabelText('Dismiss'))
    expect(document.querySelector('[data-feedback]')).toBeNull()
  })

  it('4.6: no streaks, points, or loss framing anywhere', async () => {
    await mount(payload())
    fireEvent.click(screen.getByText('Done'))
    await flush()
    expect(document.body.textContent).not.toMatch(/streak|points?\b|lost|missed|broke|in a row/i)
  })
})

// --------------------------------------------------------------------------- 4.4

describe('go there and dictate', () => {
  it('AC-8: an agent item opens the fleet focused on that agent', async () => {
    const open = vi.fn()
    vi.stubGlobal('open', open)
    await mount(payload({ item: item({ source: 'agent-questions', sessionId: 's-1', goThere: { kind: 'agent', href: '/?agent=s-1' } }) }))
    fireEvent.click(screen.getByText('Go there'))
    expect(open).toHaveBeenCalledWith(`${window.location.origin}/?agent=s-1`, 'set-fleet')
  })

  it('an external link opens in a new tab', async () => {
    const open = vi.fn()
    vi.stubGlobal('open', open)
    await mount(payload({ item: item({ goThere: { kind: 'link', href: 'https://example.test/x' } }) }))
    fireEvent.click(screen.getByText('Go there'))
    expect(open).toHaveBeenCalledWith('https://example.test/x', '_blank', 'noopener')
  })

  it('AC-9: no speech service → no dictate control, a typed field instead', async () => {
    await mount(payload({ item: item({ acceptsText: true, actions: ['goThere', 'done', 'later', 'text'] }) }))
    expect(document.querySelector('[data-dictate]')).toBeNull()
    fireEvent.change(screen.getByLabelText('Answer'), { target: { value: 'go ahead' } })
    fireEvent.click(screen.getByLabelText('Send answer'))
    await flush()
    expect(api.sent[0]).toMatchObject({ action: 'answer', text: 'go ahead' })
  })

  it('with a speech service the transcript lands in the field and is sent the same way', async () => {
    voice.available = { checked: true, hasKey: true, apiKey: 'k', micSupported: true }
    await mount(payload({ item: item({ source: 'agent-questions', sessionId: 's-9', acceptsText: true,
      actions: ['goThere', 'done', 'later', 'text'] }) }))
    fireEvent.click(document.querySelector('[data-stub-mic]')!)
    expect((screen.getByLabelText('Answer') as HTMLInputElement).value).toBe('spoken words')
    fireEvent.click(screen.getByLabelText('Send answer'))
    await flush()
    expect(api.sent[0]).toMatchObject({ action: 'answer', text: 'spoken words', sessionId: 's-9', source: 'agent-questions' })
  })
})

// --------------------------------------------------------------------------- 4.5

describe('done, later, delegate', () => {
  it('AC-23: a minimal item offers Go there, Done, Not needed and Later, nothing else', async () => {
    await mount(payload())
    const labels = Array.from(document.querySelectorAll('[data-actions] button')).map(b => b.textContent!.trim())
    expect(labels).toEqual(['Done', 'Go there', 'Not needed…', 'Later'])
  })

  it('AC-27: without a write command only Go there and Later', async () => {
    await mount(payload({ item: item({ actions: ['goThere', 'later'] }),
      publisher: { state: 'ok', project: 'pub', candidates: ['pub'], reason: null, acceptsActions: false } }))
    const labels = Array.from(document.querySelectorAll('[data-actions] button')).map(b => b.textContent!.trim())
    expect(labels).toEqual(['Go there', 'Later'])
    expect(document.querySelector('[data-markers]')!.textContent).toContain('accepts no actions')
  })

  it('AC-10: Done on a delegable item asks for at most two reasons and sends them', async () => {
    await mount(payload({ item: item({ delegable: true, actions: ['goThere', 'done', 'later', 'delegate'] }) }))
    fireEvent.click(screen.getByText('Done'))
    expect(api.sent).toHaveLength(0)
    const overlay = document.querySelector('[data-overlay="reasons"]')!
    expect(overlay.querySelectorAll('input')).toHaveLength(2)
    expect((screen.getByText('Keep it') as HTMLButtonElement).disabled).toBe(true)
    fireEvent.change(screen.getByLabelText('Reason'), { target: { value: 'only I know the client' } })
    fireEvent.click(screen.getByText('Keep it'))
    await flush()
    expect(api.sent[0]).toMatchObject({ action: 'done', reasons: ['only I know the client'] })
  })

  it('Delegate is sent directly', async () => {
    await mount(payload({ item: item({ delegable: true, actions: ['goThere', 'done', 'later', 'delegate'] }) }))
    fireEvent.click(screen.getByText('Delegate'))
    await flush()
    expect(api.sent[0]).toMatchObject({ action: 'delegate', id: 'i1' })
  })

  it('AC-11: Later for two hours sends laterSeconds=7200', async () => {
    await mount(payload())
    fireEvent.click(screen.getByText('Later'))
    fireEvent.click(screen.getByText('2 h'))
    await flush()
    expect(api.sent[0]).toMatchObject({ action: 'later', laterSeconds: 7200 })
  })

  it('laterChoices: "Tomorrow" lands at 08:00 the next day', () => {
    const now = new Date(2026, 9, 29, 22, 0, 0)
    const t = laterChoices(now).find(c => c.label === 'Tomorrow')!
    expect(t.seconds).toBe(10 * 3600)
    expect(needsReasons(item({ delegable: true }), 'done')).toBe(true)
    expect(needsReasons(item({ delegable: true }), 'delegate')).toBe(false)
    expect(hoursAgo(1.5 * 3600)).toBe('1.5 h')
  })
})

// --------------------------------------------------------------------------- 4.7

describe('sound', () => {
  function stubAudio() {
    const started: number[] = []
    class FakeCtx {
      currentTime = 0
      destination = {}
      resume() { return Promise.resolve() }
      createOscillator() {
        return { type: '', frequency: { setValueAtTime: (f: number) => started.push(f) }, connect() {}, start() {}, stop() {} }
      }
      createGain() {
        return { gain: { setValueAtTime() {}, exponentialRampToValueAtTime() {} }, connect() {} }
      }
    }
    vi.stubGlobal('AudioContext', FakeCtx)
    return started
  }

  it('is off until the first click, then a server-decided cue plays', async () => {
    const tones = stubAudio()
    const cue = { play: true, reason: 'switch', variant: 2, slowed: false, intervalSeconds: 600 }
    await mount(payload({ cue }), payload({ cue, generatedAt: 'later' }))
    expect(document.querySelector('[data-sound="off"]')).toBeTruthy()
    expect(tones).toHaveLength(0)
    fireEvent.click(document.querySelector('[data-now-root]')!)
    expect(document.querySelector('[data-sound="on"]')).toBeTruthy()
    await act(async () => { await vi.advanceTimersByTimeAsync(POLL_MS) })
    expect(tones).toEqual([523, 659, 784])
  })

  it('cue variants sound different', async () => {
    const { cueShape } = await import('../../src/lib/nowSound')
    expect(cueShape(0)).not.toEqual(cueShape(1))
  })
})

// --------------------------------------------------------------------------- 4.8

describe('focus', () => {
  it('AC-16: a fourth focus project asks which one to swap out', async () => {
    await mount(payload({ focus: ['a', 'b', 'c'], focusCandidates: ['a', 'b', 'c', 'd'] }))
    fireEvent.click(screen.getByLabelText("Today's focus projects"))
    fireEvent.click(screen.getByText('d'))
    expect(document.querySelector('[data-swap]')!.textContent).toContain('swap out which one for d')
    fireEvent.click(screen.getByText('b'))
    fireEvent.click(screen.getByText('Save focus'))
    // b left the focus → a resume note is asked for first
    fireEvent.change(screen.getByLabelText('Resume note for b'), { target: { value: 'rerun the import' } })
    fireEvent.click(screen.getByText('Save focus'))
    await flush()
    expect(api.focus[0]).toEqual({ projects: ['a', 'd', 'c'], notes: { b: 'rerun the import' } })
  })

  it('AC-17: a resume note shows on the card', async () => {
    await mount(payload({ item: item({ resumeNote: 'rerun the import' }) }))
    expect(document.querySelector('[data-resume-note]')!.textContent).toContain('rerun the import')
  })
})

// --------------------------------------------------------------------------- 4.9 / 4.10

describe('wind-down and ideas', () => {
  it('AC-18: after the hour, wind-down actions are offered and the queue stays reachable', async () => {
    await mount(payload({ windDown: { active: true, hour: 21, delegableIds: ['i1', 'i2'] } }))
    const panel = document.querySelector('[data-wind-down]')!.textContent!
    expect(panel).toContain('It is past 21:00.')
    expect(panel).toContain("Write tomorrow's first card")
    expect(panel).toContain('Hand off 2 delegable')
    fireEvent.click(screen.getByText('Hand off 2 delegable'))
    await flush()
    await flush()
    expect(api.sent.map(b => [b.id, b.action])).toEqual([['i1', 'wind-down-handoff'], ['i2', 'wind-down-handoff']])
    fireEvent.click(screen.getByText('Show the queue'))
    expect(screen.getByText('Call the supplier back')).toBeTruthy()
  })

  it('AC-19: parking an idea sends it; only the count is shown', async () => {
    await mount(payload(), payload({ parkedIdeas: 1 }))
    fireEvent.click(screen.getByLabelText('Park an idea'))
    fireEvent.change(screen.getByLabelText('Idea'), { target: { value: 'a voice-only mode' } })
    fireEvent.click(screen.getByText('Park it'))
    await flush()
    expect(api.sent[0]).toMatchObject({ action: 'park-idea', text: 'a voice-only mode', source: 'owner-queue' })
    expect(document.querySelector('[data-parked]')!.textContent).toContain('1')
    expect(document.body.textContent).not.toContain('a voice-only mode')
  })
})

// --------------------------------------------------------------------------- 7.7
describe('exact times and the "Still current?" check', () => {
  const at = (h: number, m: number, dayOffset = 0) => {
    const d = new Date()
    d.setDate(d.getDate() + dayOffset)
    d.setHours(h, m, 0, 0)
    return d.toISOString()
  }

  it('clockTime: today is a clock time, yesterday says so, older days carry the date', () => {
    expect(clockTime(at(14, 2))).toBe('14:02')
    expect(clockTime(at(9, 5, -1))).toBe('yesterday 09:05')
    const old = new Date(at(8, 0, -3))
    const pad = (n: number) => String(n).padStart(2, '0')
    expect(clockTime(old.toISOString())).toBe(`${pad(old.getMonth() + 1)}-${pad(old.getDate())} 08:00`)
    expect(clockTime('not a date')).toBeNull()
    expect(clockTime(null)).toBeNull()
  })

  it('AC-44: the time line names when it was recommended and when it was ranked', () => {
    expect(timeLine(item({ firstSeen: at(9, 5, -1) }), at(8, 27))).toBe('recommended yesterday 09:05 · ranked 08:27')
    expect(timeLine(item({ source: 'agent-questions' }), at(8, 27))).toBeNull()
  })

  it('checkView: a stale and a failed check are warnings, a standing one is ok', () => {
    expect(checkView({ state: 'stale', at: at(10, 46), evidence: 'sent on 10-29' })).toEqual(
      { tone: 'warn', label: 'No longer current — checked · 10:46', evidence: 'sent on 10-29' })
    expect(checkView({ state: 'stands', at: at(10, 46) })!.tone).toBe('ok')
    expect(checkView({ state: 'failed' })!.tone).toBe('warn')
    expect(checkView(undefined)).toBeNull()
  })

  it('AC-44: the card shows both clock times', async () => {
    await mount(payload({ item: item({ firstSeen: at(9, 5, -1) }), rankedAt: at(8, 27) }))
    expect(document.querySelector('[data-time-line]')!.textContent).toBe('recommended yesterday 09:05 · ranked 08:27')
  })

  it('AC-42: "Still current?" sends a recheck for this item, shows the outcome, and the card stays', async () => {
    await mount(payload({ item: item({ actions: ['goThere', 'done', 'later', 'recheck'] }) }))
    api.act = () => ({ delivered: true, sent: true, outcome: 'Checking in the background', reason: null, errorClass: null, closedToday: 2, parkedIdeas: 0 })
    fireEvent.click(document.querySelector('[data-recheck]')!)
    await flush()
    expect(api.sent).toEqual([expect.objectContaining({ id: 'i1', source: 'owner-queue', action: 'recheck' })])
    expect(document.querySelector('[data-feedback="ok"]')!.textContent).toContain('Checking in the background')
    expect(document.querySelector('[data-feedback="ok"]')!.textContent).not.toContain('closed today')
    expect(document.querySelector('[data-now-item="i1"]')).toBeTruthy()
  })

  it('a refused recheck (a daily limit) shows the publisher\'s reason and stays', async () => {
    await mount(payload({ item: item({ actions: ['done', 'later', 'recheck'] }) }))
    api.act = () => ({ delivered: false, sent: true, outcome: null, reason: "today's 20 on-demand checks are used up", errorClass: 'exit', closedToday: 2, parkedIdeas: 0 })
    fireEvent.click(document.querySelector('[data-recheck]')!)
    await flush()
    expect(document.querySelector('[data-feedback="fail"]')!.textContent).toContain('checks are used up')
  })

  it('no button without the recheck action, and none while a check is running', async () => {
    await mount(payload({ item: item({ actions: ['done', 'later'] }) }))
    expect(document.querySelector('[data-recheck]')).toBeNull()
    cleanup()
    await mount(payload({ item: item({ actions: ['done', 'later', 'recheck'], check: { state: 'running', startedAt: at(10, 45) } }) }))
    expect(document.querySelector('[data-recheck]')).toBeNull()
    expect(document.querySelector('[data-check="running"]')!.textContent).toContain('Checking whether it is still current')
  })

  it('AC-43: a stale check says why and when, keeps the card, and offers a one-tap close', async () => {
    await mount(payload({ item: item({ actions: ['done', 'later', 'recheck'],
      check: { state: 'stale', startedAt: at(10, 45), at: at(10, 46), evidence: 'The mail went out on 10-29' } }) }))
    const box = document.querySelector('[data-check="stale"]')!
    expect(box.textContent).toContain('No longer current')
    expect(box.textContent).toContain('10:46')
    expect(box.querySelector('[data-check-evidence]')!.textContent).toBe('The mail went out on 10-29')
    expect(document.querySelector('[data-now-item="i1"]')).toBeTruthy()
    expect(api.sent).toEqual([])
    fireEvent.click(box.querySelector('[data-check-close]')!)
    await flush()
    expect(api.sent).toEqual([expect.objectContaining({ id: 'i1', action: 'done', text: 'Not needed: no longer current (checked 10:46)' })])
  })
})
