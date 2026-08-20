/**
 * Clicking the tile opens the agent — asked for 2026-08-19: *"ha kattintok egy
 * területen ami az adott agenthez tartozik de nem gomb, akkor az agentre
 * kellene fokuszálnia és kinyílnia az ablaknak"*.
 *
 * Two halves, because they fail differently. The decision is a pure function
 * and its cases are the things a click-anywhere handler steals: a control's own
 * meaning, a surface inside the tile, and a text selection that ends in a
 * click. The wiring is asserted on the rendered screen, because a decision that
 * is never asked answers nothing — the mechanism-versus-result split this
 * repository keeps paying for.
 */
import { afterEach, describe, expect, it, vi } from 'vitest'
import { cleanup, fireEvent, render, waitFor } from '@testing-library/react'

vi.mock('../../src/components/FleetTerminal', () => ({
  default: ({ label }: { label: string }) => (
    <div data-fleet-terminal={label} data-fleet-own-surface="terminal">
      <span data-stub-terminal-body>screen</span>
    </div>
  ),
}))

import Fleet from '../../src/pages/Fleet'
import { tileClickCollapses, tileClickOpens } from '../../src/lib/fleetTileClick'

afterEach(() => { cleanup(); vi.unstubAllGlobals(); localStorage.clear() })

/** A tile with the three things a click can land on. */
function tile(): { card: HTMLElement; q: (sel: string) => Element } {
  const card = document.createElement('div')
  card.innerHTML = `
    <span data-plain>set-core#a1</span>
    <button data-control>open the log</button>
    <span data-inside-control><b data-deep>icon</b></span>
    <div data-fleet-own-surface="log"><span data-in-log>a line of the log</span></div>
  `
  card.querySelector('[data-inside-control]')!.replaceWith(
    Object.assign(document.createElement('button'), { innerHTML: '<b data-deep>icon</b>' }),
  )
  document.body.appendChild(card)
  return { card, q: (sel: string) => card.querySelector(sel)! }
}

describe('what a click on the tile is allowed to mean', () => {
  it('opens on the tile’s own text', () => {
    const { card, q } = tile()
    expect(tileClickOpens({ target: q('[data-plain]'), card })).toBe(true)
  })

  it('opens on the tile itself, not only on something in it', () => {
    const { card } = tile()
    expect(tileClickOpens({ target: card, card })).toBe(true)
  })

  /**
   * The control already means something, and its click bubbles. Without this,
   * pressing "open the log" would ALSO re-lay out the tile underneath the act
   * the reader asked for.
   */
  it('does nothing on a control', () => {
    const { card, q } = tile()
    expect(tileClickOpens({ target: q('[data-control]'), card })).toBe(false)
  })

  /** The icon inside a button is what a mouse actually hits. */
  it('does nothing on something INSIDE a control', () => {
    const { card, q } = tile()
    expect(tileClickOpens({ target: q('[data-deep]'), card })).toBe(false)
  })

  /**
   * A surface inside the tile is not the tile. Clicking into a terminal is how
   * the keyboard gets there; re-laying out at that moment moves the box out
   * from under hands that are already typing.
   */
  it('does nothing inside a surface of its own', () => {
    const { card, q } = tile()
    expect(tileClickOpens({ target: q('[data-in-log]'), card })).toBe(false)
  })

  /**
   * Dragging across an excerpt to copy it ends in a `click` like any other.
   * Opening there destroys the selection that was the whole point — and only
   * for readers who reached for the text, which is why it survives testing.
   */
  it('does nothing when the click ended a selection', () => {
    const { card, q } = tile()
    expect(tileClickOpens({ target: q('[data-plain]'), card, selection: 'set-core' })).toBe(false)
    // Whitespace is not a selection anybody made on purpose.
    expect(tileClickOpens({ target: q('[data-plain]'), card, selection: '  ' })).toBe(true)
  })

  it('does nothing for a click outside the tile', () => {
    const { card } = tile()
    const outside = document.createElement('div')
    document.body.appendChild(outside)
    expect(tileClickOpens({ target: outside, card })).toBe(false)
    expect(tileClickOpens({ target: null, card })).toBe(false)
  })
})

describe('what a click on an OPEN tile is allowed to mean', () => {
  /** The same tile, with a title bar around the name. */
  function headed(): { card: HTMLElement; q: (sel: string) => Element } {
    const { card, q } = tile()
    const head = document.createElement('div')
    head.setAttribute('data-fleet-tile-head', '1')
    head.append(q('[data-plain]'), q('[data-control]'))
    card.prepend(head)
    return { card, q: (sel: string) => card.querySelector(sel)! }
  }

  it('collapses on the title bar’s own text', () => {
    const { card, q } = headed()
    expect(tileClickCollapses({ target: q('[data-plain]'), card })).toBe(true)
  })

  it('does nothing in the body, which is what was opened to be read', () => {
    const { card, q } = headed()
    expect(tileClickOpens({ target: q('[data-in-log]'), card })).toBe(false)
    expect(tileClickCollapses({ target: q('[data-in-log]'), card })).toBe(false)
  })

  it('does nothing on a control INSIDE the title bar', () => {
    const { card, q } = headed()
    expect(tileClickCollapses({ target: q('[data-control]'), card })).toBe(false)
  })

  it('does nothing when the click ended a selection', () => {
    const { card, q } = headed()
    expect(tileClickCollapses({ target: q('[data-plain]'), card, selection: 'set-core' })).toBe(false)
  })
})

type Json = Record<string, unknown>

function agent(pid: number, extra: Json = {}): Json {
  return {
    pid, name: `a${pid}`, project: 'demo', branch: 'main', session_id: `s${pid}`,
    binding_confirmed: true, sources: ['process'], kind: 'interactive', state: 'quiet',
    tool: null, tool_elapsed_seconds: null, other_tools: [], last_movement_seconds: 5,
    unknown_reason: null, waiting_for: null, declaration_ignored: null,
    population: 'started-here', terminal_label: `t-${pid}`, ...extra,
  }
}

async function show(agents: Json[]) {
  vi.stubGlobal('fetch', vi.fn((url: string) => {
    const u = String(url)
    if (u.includes('/api/fleet/layout')) {
      return Promise.resolve({ ok: true, json: () => Promise.resolve({ version: 1, groups: [], parked: [], ungrouped: [], missing: [] }) } as Response)
    }
    if (u.includes('/log')) {
      return Promise.resolve({ ok: true, json: () => Promise.resolve({ turns: [], total_read: 0, truncated: false }) } as Response)
    }
    if (u.includes('/api/fleet')) {
      return Promise.resolve({ ok: true, json: () => Promise.resolve({
        agents: agents.length, working: 0, unknown: 0, owner_reachable: true,
        projects: [{ name: 'demo', root: '/home/x/demo', sources: ['process'], archived: false, agents }],
        quiet_means: 'no outstanding tool call as of the session log’s last flush',
      }) } as Response)
    }
    return Promise.resolve({ ok: true, json: () => Promise.resolve({}) } as Response)
  }))
  const view = render(<Fleet />)
  await waitFor(() => expect(view.container.querySelector('[data-fleet-ownership]')).toBeTruthy())
  return view
}

const enlargedPid = (c: HTMLElement) => c.querySelector('[data-fleet-enlarged]')?.getAttribute('data-fleet-enlarged') ?? null

describe('the wiring — the tile actually asks', () => {
  it('a click on the tile’s body enlarges that agent', async () => {
    const { container } = await show([agent(11), agent(22)])
    expect(enlargedPid(container)).toBe(null)
    const card = container.querySelector('[data-fleet-opens="22"]')!
    fireEvent.click(card.querySelector('.text-sm.text-fg-strong')!)
    await waitFor(() => expect(enlargedPid(container)).toBe('22'))
  })

  /**
   * Asymmetric on purpose, and the asymmetry is the whole design — asked for
   * 2026-08-20: *"ha megint rákattintok, azt kéne, hogy visszamenjen, mint egy
   * minimize"*. Opening is click-anywhere; closing is click-on-the-title-bar,
   * because the body is what the reader enlarged the tile in order to read.
   */
  it('a click on the open tile’s title bar puts it back', async () => {
    const { container } = await show([agent(11), agent(22)])
    fireEvent.click(container.querySelector('[data-fleet-opens="22"] .text-sm.text-fg-strong')!)
    await waitFor(() => expect(enlargedPid(container)).toBe('22'))
    // The same element, clicked again: the name in the title bar.
    fireEvent.click(container.querySelector('[data-fleet-collapses="22"] .text-sm.text-fg-strong')!)
    await waitFor(() => expect(enlargedPid(container)).toBe(null))
  })

  /**
   * The half that keeps the old decision alive. `tileClickOpens` already lets a
   * click through anywhere in the tile, so if the collapse were wired to the
   * card instead of the head, this test is the only thing that would notice —
   * and what it protects is a reader mid-log losing what they were reading.
   */
  it('a click in the open tile’s BODY leaves it open', async () => {
    const { container } = await show([agent(11), agent(22)])
    fireEvent.click(container.querySelector('[data-fleet-opens="22"] .text-sm.text-fg-strong')!)
    await waitFor(() => expect(enlargedPid(container)).toBe('22'))
    const card = container.querySelector('[data-fleet-collapses="22"]')!
    // A part of the tile that is NOT the head — and asserted to be one a click
    // would otherwise act on, so a body that happens to refuse every click
    // cannot make this pass without measuring anything.
    const body = Array.from(card.children).find(el => !el.hasAttribute('data-fleet-tile-head'))!
    expect(body).toBeTruthy()
    expect(tileClickOpens({ target: body, card })).toBe(true)
    fireEvent.click(body)
    expect(enlargedPid(container)).toBe('22')
  })

  /**
   * The load-bearing wiring case: a control's click must not ALSO be read as a
   * request to open. Asserted through the real control, not the helper — the
   * two differ exactly when the handler is attached in the wrong place.
   */
  it('pressing a control does not enlarge the tile as a side effect', async () => {
    const { container } = await show([agent(11), agent(22)])
    const log = container.querySelector('[data-fleet-opens="22"] [data-tile-control="log"]')!
    fireEvent.click(log)
    await waitFor(() => expect(container.querySelector('[data-fleet-own-surface="log"]')).toBeTruthy())
    expect(enlargedPid(container)).toBe(null)
  })

  /**
   * The log opens where the tile already is, so a tile can carry a log AND
   * still be openable — which is exactly when a click in the log body would
   * re-lay out the page under the line being read.
   */
  it('reading the log does not move the tile', async () => {
    const { container } = await show([agent(11), agent(22)])
    fireEvent.click(container.querySelector('[data-fleet-opens="22"] [data-tile-control="log"]')!)
    await waitFor(() => expect(container.querySelector('[data-fleet-own-surface="log"]')).toBeTruthy())
    fireEvent.click(container.querySelector('[data-fleet-own-surface="log"] [role="tablist"]')!)
    expect(enlargedPid(container)).toBe(null)
  })

  /**
   * Two agents, because ONE auto-enlarges (`resolveEnlarged`) — the first
   * version of this test asked a screen where the tile was already open, so it
   * was measuring the layout rather than the click.
   */
  it('typing into the instruction box does not move the tile', async () => {
    const { container } = await show([agent(11, { instructable: true, seat: 'demo#a' }), agent(22)])
    expect(enlargedPid(container)).toBe(null)
    const box = container.querySelector('[data-fleet-own-surface="instruct"] textarea')!
    fireEvent.click(box)
    expect(enlargedPid(container)).toBe(null)
  })
})
