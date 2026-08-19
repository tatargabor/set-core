/**
 * The conversation view as it is READ — task 7.20, the rendering half.
 *
 * `fleetConversation.test.ts` asserts the model. This asserts what reaches the
 * screen, and every case here is one the previous view got wrong on real data:
 *
 *  - a machine-fed tool result labelled `te`;
 *  - a call and its answer as two rows with a role change between them;
 *  - a failure the compaction may not swallow — including the case where the
 *    failure state was never measured, which must be SAID rather than assumed
 *    clean (`.claude/rules/ui-quality.md`: compacting must never hide a
 *    failure).
 *
 * The negative half is asserted explicitly throughout. A test that only checks
 * "the sentence appears" passes on a build that also prints `te` over every
 * tool result — which is the build this task exists to replace.
 */
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react'

import { buildActs } from '../../src/lib/fleetConversation'
import Fleet from '../../src/pages/Fleet'

type Json = Record<string, unknown>

const agent = (over: Json = {}): Json => ({
  pid: 4242,
  name: 'demo-1',
  project: 'demo',
  branch: 'main',
  session_id: 'abc',
  binding_confirmed: true,
  sources: ['process'],
  kind: 'interactive',
  state: 'quiet',
  tool: null,
  tool_elapsed_seconds: null,
  other_tools: [],
  last_movement_seconds: 5,
  unknown_reason: null,
  population: 'foreign',
  terminal_label: null,
  ...over,
})

const fleet = (agents: Json[]): Json => ({
  agents: agents.length,
  working: 0,
  unknown: 0,
  projects: [{ name: 'demo', root: '/home/x/demo', sources: ['process'], archived: false, agents }],
  quiet_means: 'no outstanding tool call as of the session log’s last flush',
})

function turn(over: Json = {}): Json {
  return {
    role: 'assistant',
    timestamp: '2026-08-19T12:05:00Z',
    text: '',
    thinking: '',
    tools: [],
    results: 0,
    sidechain: false,
    ...over,
  }
}

/** Serves the fleet and one log; everything else answers empty. */
function installFetch(turns: Json[], agents: Json[] = [agent()]) {
  const stub = vi.fn((url: string) => {
    const u = String(url)
    if (u.includes('/api/fleet/layout')) {
      return Promise.resolve({ ok: true, json: () => Promise.resolve({ version: 1, groups: [], parked: [], ungrouped: [], missing: [] }) } as Response)
    }
    if (u.includes('/log')) {
      return Promise.resolve({ ok: true, json: () => Promise.resolve({ turns, total_read: turns.length, truncated: false }) } as Response)
    }
    if (u.includes('/api/fleet')) {
      return Promise.resolve({ ok: true, json: () => Promise.resolve(fleet(agents)) } as Response)
    }
    return Promise.resolve({ ok: true, json: () => Promise.resolve({}) } as Response)
  })
  vi.stubGlobal('fetch', stub)
  return stub
}

/**
 * Renders the fleet and gets the first agent's log on screen.
 *
 * One agent on purpose: the single-agent default (task 7.5) enlarges the tile
 * and opens its log, so the reader lands on the conversation without a click —
 * which is the path this task is about. The click is still handled, so the
 * helper does not break the day that default moves.
 */
async function openLog(turns: Json[], agents?: Json[]) {
  installFetch(turns, agents)
  const view = render(<Fleet />)
  await waitFor(() => expect(view.container.querySelector('[data-fleet-excerpt], [data-log-tab]')).toBeTruthy())
  const opener = screen.queryAllByText('napló megnyitása')
  if (opener.length > 0) fireEvent.click(opener[0])
  await waitFor(() => expect(view.container.querySelectorAll('[data-log-act]').length).toBeGreaterThan(0))
  return view
}

beforeEach(() => {
  vi.useRealTimers()
  try { localStorage.clear() } catch { /* no storage here */ }
})
afterEach(() => { cleanup(); vi.unstubAllGlobals(); vi.restoreAllMocks() })

describe('the screen never says the person said what the runtime fed back', () => {
  it('renders a call and its result as ONE act, with no speaker on it', async () => {
    const { container } = await openLog([
      turn({ tools: [{ name: 'Bash', id: 'x' }] }),
      turn({ role: 'user', results: 1, timestamp: '2026-08-19T12:05:04Z' }),
    ])

    const acts = container.querySelectorAll('[data-log-act]')
    expect(acts).toHaveLength(1)
    expect(acts[0].getAttribute('data-log-act')).toBe('work')

    // The negative half — the whole point of the task. `queryAllByText` with an
    // exact match rather than a regex over `textContent`: the label sits in its
    // own element with the clock glued to it (`you12:05`), so a word-boundary
    // regex would pass on the broken build for the wrong reason.
    expect(container.querySelector('[data-log-speaker]')).toBeNull()
    expect(screen.queryAllByText('you')).toHaveLength(0)
  })

  it('still says `te` where the person actually spoke', async () => {
    const { container } = await openLog([turn({ role: 'user', text: 'indulhat' })])
    const say = container.querySelector('[data-log-act="say"]')!
    expect(say.getAttribute('data-log-speaker')).toBe('person')
    expect(screen.getAllByText('you')).toHaveLength(1)
    expect(say.textContent).toMatch(/indulhat/)
  })

  it('names the runtime where the runtime wrote under the person’s role', async () => {
    const { container } = await openLog([
      turn({ role: 'user', text: '<command-name>/set:status</command-name>' }),
    ])
    const say = container.querySelector('[data-log-act="say"]')!
    expect(say.getAttribute('data-log-speaker')).toBe('runtime')
    expect(say.textContent).toMatch(/runtime/)
    expect(screen.queryAllByText('you')).toHaveLength(0)
  })
})

describe('the sentence is findable and the machinery is not hidden', () => {
  const noisy = [
    turn({ role: 'user', text: 'kezdd el' }),
    ...Array.from({ length: 6 }).flatMap((_, i) => [
      turn({ tools: [{ name: 'Bash', id: `c${i}` }] }),
      turn({ role: 'user', results: 1 }),
    ]),
    turn({ text: 'kész vagyok' }),
  ]

  it('gives the sentences a different weight from the tool lines', async () => {
    const { container } = await openLog(noisy)
    const says = container.querySelectorAll('[data-log-act="say"]')
    const works = container.querySelectorAll('[data-log-act="work"]')
    expect(says).toHaveLength(2)
    // ONE work row, not six — since 2026-08-19 a run of tool calls between two
    // sentences is one act (B-8). The thing this test is about, the hierarchy
    // between a sentence and a tool line, is unchanged.
    expect(works).toHaveLength(1)

    // Hierarchy, asserted rather than eyeballed: the sentence body is at the
    // reading size and the tool line is a step below it. A build that renders
    // everything at one size — the one measured as unreadable — fails here.
    // The sizes are the design system's own scale (12/14/16); an arbitrary
    // `text-[11px]` would read as more hierarchy and is refused by
    // `designDrift.test.ts`, which is the check that caught it here.
    const body = says[0].querySelector('div:last-child')!
    expect(body.className).toMatch(/\btext-sm\b/)
    expect(works[0].className).toMatch(/\btext-xs\b/)
    expect(works[0].className).not.toMatch(/\btext-sm\b/)
  })

  /**
   * The compaction rule's hard half. Every act stays on screen; nothing is
   * collapsed behind a "show more" that a failed call could sit inside.
   */
  it('leaves every act on screen — whatever the model produced, none of it hidden', async () => {
    // Asserted against the MODEL rather than a number written down here. The
    // count used to be 8 and is 3 since the runs merge, and a hard-coded figure
    // makes a rule change look like a regression while proving nothing about
    // the thing the test is for: that the screen drops none of what was built.
    const { container } = await openLog(noisy)
    const expected = buildActs(noisy as never).length
    expect(container.querySelectorAll('[data-log-act]')).toHaveLength(expected)
    expect(container.querySelector('[data-log-sentences]')?.getAttribute('data-log-sentences')).toBe('2')
  })

  it('says out loud when a window carries no sentence at all', async () => {
    const { container } = await openLog([
      turn({ tools: [{ name: 'Bash', id: 'x' }] }),
      turn({ role: 'user', results: 1 }),
    ])
    expect(container.textContent).toMatch(/not one sentence/)
  })
})

describe('compacting may not hide a failure', () => {
  it('marks the failed call on its own row, in red, where it happened', async () => {
    const { container } = await openLog([
      turn({ tools: [{ name: 'Bash', id: 'a' }] }),
      turn({ role: 'user', results: 1, errors: 1 }),
      turn({ tools: [{ name: 'Read', id: 'b' }] }),
      turn({ role: 'user', results: 1, errors: 0 }),
    ])
    const works = container.querySelectorAll('[data-log-act="work"]')
    expect(works).toHaveLength(2)
    expect(works[0].getAttribute('data-log-errors')).toBe('1')
    expect(works[0].textContent).toMatch(/failed/)
    expect(works[0].className).toMatch(/border-red/)

    // And the clean one is NOT marked — a screen that marks everything marks
    // nothing.
    expect(works[1].getAttribute('data-log-errors')).toBe('0')
    expect(works[1].className).not.toMatch(/border-red/)

    expect(container.querySelector('[data-log-errors-standing]')?.getAttribute('data-log-errors-standing'))
      .toBe('failed')
  })

  /**
   * Today's real case, and the one the false-absence rule is about: the log
   * endpoint reduces a tool result to a COUNT and drops `is_error`. The panel
   * may not therefore report calm — it has to admit it did not look, above the
   * scroll container where the reader is standing.
   */
  it('admits it cannot mark failures when the data carries no error flag', async () => {
    const { container } = await openLog([
      turn({ tools: [{ name: 'Bash', id: 'a' }] }),
      turn({ role: 'user', results: 1 }),
    ])
    const standing = container.querySelector('[data-log-errors-standing]')!
    expect(standing.getAttribute('data-log-errors-standing')).toBe('unknown')
    expect(standing.textContent).toMatch(/failure state not carried/)

    // The negative half: it must not read as a measured clean run.
    expect(container.textContent).not.toMatch(/0 failed calls/)
  })

  it('says nothing about failures when there were no tool results to fail', async () => {
    const { container } = await openLog([turn({ role: 'user', text: 'szia' })])
    expect(container.querySelector('[data-log-errors-standing]')).toBeNull()
  })

  it('shows a call still waiting for its answer as undetermined, not as clean', async () => {
    const { container } = await openLog([turn({ tools: [{ name: 'Bash', id: 'a' }] })])
    const work = container.querySelector('[data-log-act="work"]')!
    expect(work.textContent).toMatch(/awaiting a result/)
  })
})
