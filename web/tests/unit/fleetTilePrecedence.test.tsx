/**
 * What a tile shows when TWO views want the same space — and the header row
 * that used to be five.
 *
 * All three defects here were reported from one screenshot on 2026-08-19, and
 * none of them was visible to a structural count: every element rendered, no
 * error was thrown, and the suite was green. They are layout and precedence
 * faults, which `ui-quality.md` says only a human looking at it catches — so
 * what this file does is turn that look into something a machine can fail on.
 *
 * The terminal component is STUBBED in the precedence tests (a ~300 KB emulator
 * and a WebSocket do not belong in jsdom); the header test renders the real one
 * with no socket, which is enough to assert what its controls ARE.
 */
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { cleanup, fireEvent, render, waitFor } from '@testing-library/react'

vi.mock('../../src/components/FleetTerminal', () => ({
  default: ({ label }: { label: string }) => <div data-fleet-terminal={label}>terminal</div>,
}))

import Fleet from '../../src/pages/Fleet'

type Json = Record<string, unknown>

function agent(pid: number, name: string, extra: Json = {}): Json {
  return {
    pid, name, project: 'demo', branch: 'main', session_id: `s${pid}`, binding_confirmed: true,
    sources: ['process'], kind: 'interactive', state: 'quiet', tool: null,
    tool_elapsed_seconds: null, other_tools: [], last_movement_seconds: 5,
    unknown_reason: null, waiting_for: null, declaration_ignored: null,
    population: 'started-here', terminal_label: `t-${pid}`, instructable: false,
    ...extra,
  }
}

const fleet = (agents: Json[]): Json => ({
  agents: agents.length,
  working: 0,
  unknown: 0,
  owner_reachable: true,
  projects: [{ name: 'demo', root: '/home/x/demo', sources: ['process'], archived: false, agents }],
  quiet_means: 'no outstanding tool call as of the session log’s last flush',
})

function installFetch(body: Json) {
  vi.stubGlobal('fetch', vi.fn((url: string) => {
    const u = String(url)
    if (u.includes('/api/fleet/layout')) {
      return Promise.resolve({ ok: true, json: () => Promise.resolve({ version: 1, groups: [], parked: [], ungrouped: [], missing: [] }) } as Response)
    }
    if (u.includes('/log')) {
      return Promise.resolve({ ok: true, json: () => Promise.resolve({ turns: LOG_TURNS, total_read: 0, truncated: false }) } as Response)
    }
    if (u.includes('/api/fleet')) {
      return Promise.resolve({ ok: true, json: () => Promise.resolve(body) } as Response)
    }
    return Promise.resolve({ ok: true, json: () => Promise.resolve({}) } as Response)
  }))
}

/** What the log endpoint answers. Set per test; reset in `beforeEach`. */
let LOG_TURNS: unknown[] = []

async function show(body: Json, log?: { turns: unknown[] }) {
  LOG_TURNS = log?.turns ?? []
  installFetch(body)
  const view = render(<Fleet />)
  await waitFor(() => expect(view.container.querySelector('[data-fleet-ownership]')).toBeTruthy())
  return view
}

const logPanel = (c: HTMLElement) => c.querySelector('[data-fleet-log]') ?? c.querySelector('[data-fleet-own-surface="log"]')
const terminal = (c: HTMLElement) => c.querySelector('[data-fleet-terminal]')
const logControl = (c: HTMLElement) => c.querySelector('[data-tile-control="log"]') as HTMLElement
const termControl = (c: HTMLElement) => c.querySelector('[data-tile-control="terminal"]') as HTMLElement

beforeEach(() => {
  vi.useRealTimers()
  try { localStorage.clear() } catch { /* no storage here */ }
  LOG_TURNS = []
})
afterEach(() => { cleanup(); vi.unstubAllGlobals(); vi.restoreAllMocks() })

describe('the terminal outranks the log', () => {
  /**
   * The reported case, and the reason it needs a test rather than a fix note:
   * NEITHER half was wrong on its own. Starting an agent opens its terminal,
   * and `resolveLogs` opens the enlarged tile's log while no choice has been
   * made — a default with its own test one file over. A newly started agent is
   * both at once, and the tile stacked an empty log panel on the live terminal.
   */
  it('shows the terminal and not the log when both are open', async () => {
    // No click opens the log here, and that is the POINT: a lone agent is the
    // enlarged one, so `resolveLogs` has already opened its log. This is the
    // reported situation reproduced exactly, not a set-up approximating it.
    const { container } = await show(fleet([agent(1, 'a1')]))
    await waitFor(() => expect(logPanel(container)).toBeTruthy())

    fireEvent.click(termControl(container))
    await waitFor(() => expect(terminal(container)).toBeTruthy())
    expect(logPanel(container)).toBeNull()
  })

  /** The log is not DISCARDED — it is covered, and it comes back. */
  it('brings the log back when the terminal closes', async () => {
    const { container } = await show(fleet([agent(1, 'a1')]))
    await waitFor(() => expect(logPanel(container)).toBeTruthy())
    fireEvent.click(termControl(container))
    await waitFor(() => expect(logPanel(container)).toBeNull())

    fireEvent.click(termControl(container))
    await waitFor(() => expect(terminal(container)).toBeNull())
    expect(logPanel(container)).toBeTruthy()
  })

  /**
   * A marker outranks the body: a lit log icon over a tile showing no log is
   * the same defect as a count whose breakdown is empty. `logOpen` must be what
   * is SHOWN, never what is stored.
   */
  it('does not light the log control for a log the terminal is covering', async () => {
    const { container } = await show(fleet([agent(1, 'a1')]))
    await waitFor(() => expect(logControl(container).getAttribute('data-tile-control-active')).toBe('on'))

    fireEvent.click(termControl(container))
    await waitFor(() => expect(terminal(container)).toBeTruthy())
    expect(logControl(container).getAttribute('data-tile-control-active')).toBeNull()
  })

  /**
   * Precedence is the DEFAULT, not a prohibition. An explicit click is a
   * choice, and a choice outranks a default — otherwise the control is inert,
   * which `TileControls` already refuses elsewhere ("inert is worse than
   * absent").
   */
  it('lets an explicit log click close the terminal', async () => {
    const { container } = await show(fleet([agent(1, 'a1')]))
    fireEvent.click(termControl(container))
    await waitFor(() => expect(terminal(container)).toBeTruthy())

    fireEvent.click(logControl(container))
    await waitFor(() => expect(terminal(container)).toBeNull())
    expect(logPanel(container)).toBeTruthy()
  })
})

describe('what a tile stops saying while its terminal is up', () => {
  /**
   * FALSE ABSENCE, and it was on screen: *"no input: this session has no seat
   * on the messaging bus"* directly above a live terminal that takes
   * keystrokes. True about the bus, false about what the reader takes from it.
   */
  it('does not say there is no input while a terminal takes keystrokes', async () => {
    const { container } = await show(fleet([agent(1, 'a1', { instructable: false })]))
    // B-61 collapsed the instruction BOX behind a control, and deliberately not
    // this: an agent with no seat has no box to open, so its reason still stands
    // where the box would be. That is what keeps the subject below measurable.
    await waitFor(() => expect(container.querySelector('[data-fleet-instruct="refused"]')).toBeTruthy())

    fireEvent.click(termControl(container))
    await waitFor(() => expect(terminal(container)).toBeTruthy())
    expect(container.querySelector('[data-fleet-instruct="refused"]')).toBeNull()
  })

  /**
   * The excerpt is *the last thing actually said*. The terminal shows it live
   * and the log's newest act IS it, so on an open tile the line is a second
   * copy of what sits two rows below.
   *
   * TWO agents, deliberately: a lone agent is auto-enlarged and its log opens
   * by default, so a one-agent fixture starts in the state this test is trying
   * to reach and would pass without measuring anything.
   */
  const withExcerpt = () => fleet([
    agent(1, 'a1', { excerpt: 'a sentence', excerpt_from: 'agent' }),
    agent(2, 'a2', { excerpt: 'another', excerpt_from: 'agent' }),
  ])

  /**
   * ⚠ FOUND BY LOOKING at the running screen on 2026-08-20, and no structural
   * count could have seen it: both copies were correct, every element rendered,
   * 675 tests were green.
   *
   * The excerpt used to render on the tile under `!terminalOpen && !logShown`
   * — character for character the condition `TileActivity` renders under. So it
   * was never on screen WITHOUT the activity view beneath it, and that view's
   * newest `say` row is the same sentence. Every open tile said the same thing
   * twice, two rows apart.
   *
   * The fixture answers the log endpoint with a conversation, because that is
   * the state the duplication happened in. The empty-log case is the next test.
   */
  it('says the newest sentence once, not once as an excerpt and again as an act', async () => {
    const { container } = await show(withExcerpt(), { turns: [
      { role: 'assistant', timestamp: '2026-08-20T10:00:00Z', text: 'a sentence',
        thinking: '', tools: [], results: 0, sidechain: false },
    ] })
    await waitFor(() => expect(container.querySelector('[data-fleet-tile-activity]')).toBeTruthy())
    expect(
      container.querySelectorAll('[data-fleet-excerpt]'),
      'the excerpt is back beside a conversation that already contains it',
    ).toHaveLength(0)
  })

  /**
   * And it is NOT simply deleted. `TileActivity` reads the log ENDPOINT; the
   * excerpt comes from the fleet payload's state pass. The two fail
   * independently, so a tile whose log cannot be read still has something to
   * say — which is exactly when the fallback must appear.
   */
  it('keeps the excerpt where the activity view has no conversation to show', async () => {
    const { container } = await show(withExcerpt())
    await waitFor(() => expect(container.querySelectorAll('[data-fleet-excerpt]')).toHaveLength(2))
  })

  it('drops the excerpt the terminal is already showing', async () => {
    const { container } = await show(withExcerpt())
    await waitFor(() => expect(container.querySelectorAll('[data-fleet-excerpt]')).toHaveLength(2))

    fireEvent.click(termControl(container))
    await waitFor(() => expect(terminal(container)).toBeTruthy())
    expect(container.querySelectorAll('[data-fleet-excerpt]')).toHaveLength(1)
  })

  it('drops the excerpt the log panel is already showing', async () => {
    const { container } = await show(withExcerpt())
    await waitFor(() => expect(container.querySelectorAll('[data-fleet-excerpt]')).toHaveLength(2))

    fireEvent.click(logControl(container))
    await waitFor(() => expect(logPanel(container)).toBeTruthy())
    expect(container.querySelectorAll('[data-fleet-excerpt]')).toHaveLength(1)
  })
})

describe('one font size for the state word', () => {
  /**
   * Asked as *"quiet main feliratok kulon fontméret?????"* — and it was three
   * sizes, not two: the name at `text-sm`, the branch at `text-xs`, and the
   * state word inheriting the browser's 16px because nothing on the chain set
   * one.
   *
   * This asserts the CLASS, not the instance: every branch of `StateLine` must
   * declare a size, so a branch added later cannot silently inherit again.
   */
  it('declares a size on every state, so none inherits the page default', async () => {
    for (const state of ['quiet', 'working', 'waiting', 'unknown', 'something-new']) {
      cleanup()
      const { container } = await show(fleet([agent(1, 'a1', { state })]))
      const word = container.querySelector('[data-fleet-ownership] .inline-flex.items-center')
      expect(word, `no state word rendered for ${state}`).toBeTruthy()
      expect(
        [...word!.classList].some(c => /^text-(xs|sm|base|lg)$/.test(c)),
        `state "${state}" renders with no font size of its own: ${word!.className}`,
      ).toBe(true)
    }
  })
})

/**
 * The tab strip is ONE line, whatever the fleet's size — AC-130.
 *
 * ⚠ ASSERTED ON THE SOURCE, NOT ON A LAYOUT, and the limit is in the name of
 * this describe block rather than only in this comment. jsdom performs no
 * layout: every element is 0×0, so a test that asked *does this wrap* would
 * measure nothing and pass on a strip that wraps into eight rows. What is
 * checkable here is the DECLARATION — sideways scrolling, and tabs that refuse
 * to shrink — which is what makes wrapping impossible.
 *
 * The result itself is checkable only by looking, which `ui-quality.md` now
 * requires of every UI change. This guard exists so that a later edit removing
 * the declaration fails immediately instead of waiting for somebody to notice a
 * strip that has quietly become the row list it replaced.
 */
describe('the strip declares itself un-wrappable (source-level guard)', () => {
  it('scrolls sideways and holds its tabs at their own width', async () => {
    const { container } = await show(fleet([agent(1, 'a1'), agent(2, 'a2'), agent(3, 'a3')]))
    fireEvent.click(container.querySelector('[data-tile-controls="1"] [data-tile-control="enlarge"]')!)
    await waitFor(() => expect(container.querySelector('[data-fleet-agent-tabs]')).toBeTruthy())

    const strip = container.querySelector('[data-fleet-agent-tabs]') as HTMLElement
    expect(strip.className).toContain('overflow-x-auto')
    expect(strip.className, 'a wrapping strip is the row list again').not.toContain('flex-wrap')
    for (const tab of container.querySelectorAll('[data-fleet-agent-tab]')) {
      expect((tab as HTMLElement).className).toContain('shrink-0')
    }
  })

  /** Every agent is in the strip, including the one that is enlarged. */
  it('lists the whole project, so the count is the fleet’s and not the fleet minus one', async () => {
    const { container } = await show(fleet([agent(1, 'a1'), agent(2, 'a2'), agent(3, 'a3')]))
    fireEvent.click(container.querySelector('[data-tile-controls="1"] [data-tile-control="enlarge"]')!)
    await waitFor(() => expect(container.querySelector('[data-fleet-agent-tabs]')).toBeTruthy())
    expect(container.querySelectorAll('[data-fleet-agent-tab]')).toHaveLength(3)
    expect(container.querySelector('[data-fleet-agent-tabs]')!.getAttribute('data-fleet-agent-tabs')).toBe('3')
  })
})
