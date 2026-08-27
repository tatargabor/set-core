/**
 * B-90 — the hidden sentences must not come along when the screen is copied.
 *
 * Reported by pasting a Ctrl+C of the fleet screen into the chat: what arrived
 * was the tile controls' explanations — *put this panel on the left …*, *stop
 * the agent — a separate, explicit act* — none of which is on screen. They are
 * `sr-only` spans, which `ui-quality.md` asked for on purpose (a reason that
 * lives only in a tooltip is not stated), and `sr-only` only CLIPS: the text
 * stays selectable.
 *
 * Measured 2026-08-27 in Chromium against the running dashboard, selecting the
 * terminal header alone: **668 characters, of which 4 were visible** (`live`).
 * Setting `user-select: none` on those spans took the same selection to 4.
 *
 * ⚠ What this file can and cannot prove, stated because the difference is the
 * whole point of `evidence-discipline.md`. jsdom has no layout and no real
 * selection, so it CANNOT measure what lands on the clipboard — the browser did
 * that, and `tests/e2e/fleet-terminal.spec.ts` keeps doing it. What this file
 * asserts is the property that makes it true and that a future call site can
 * silently lose: **every hidden span the fleet screen renders is unselectable.**
 * It is written against the rendered DOM rather than against `SrOnly` so that a
 * hand-written `<span className="sr-only">` fails it too — which is exactly how
 * all three of the current sites came to exist.
 */
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { cleanup, fireEvent, render, waitFor } from '@testing-library/react'

vi.mock('../../src/components/FleetTerminal', () => ({
  default: ({ label }: { label: string }) => <div data-fleet-terminal={label}>terminal</div>,
}))

import Fleet from '../../src/pages/Fleet'
import SrOnly from '../../src/components/SrOnly'

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
      return Promise.resolve({ ok: true, json: () => Promise.resolve({ turns: [], total_read: 0, truncated: false }) } as Response)
    }
    if (u.includes('/api/fleet')) {
      return Promise.resolve({ ok: true, json: () => Promise.resolve(body) } as Response)
    }
    return Promise.resolve({ ok: true, json: () => Promise.resolve({}) } as Response)
  }))
}

async function show(body: Json) {
  installFetch(body)
  const view = render(<Fleet />)
  await waitFor(() => expect(view.container.querySelector('[data-fleet-ownership]')).toBeTruthy())
  return view
}

/** Every visually-hidden span in the tree, however it was written. */
const hidden = (c: HTMLElement) => [...c.querySelectorAll('.sr-only')] as HTMLElement[]

beforeEach(() => {
  vi.useRealTimers()
  try { localStorage.clear() } catch { /* no storage here */ }
})
afterEach(() => { cleanup(); vi.unstubAllGlobals(); vi.restoreAllMocks() })

describe('hidden text is not selectable', () => {
  it('marks every sr-only span on the fleet screen unselectable', async () => {
    const { container } = await show(fleet([agent(1, 'a1'), agent(2, 'a2')]))

    const spans = hidden(container)
    // A zero here is a shape error, not a pass: if the screen rendered no
    // hidden text at all the assertion below would be vacuously true and this
    // test would go green for the rest of its life while proving nothing.
    expect(spans.length).toBeGreaterThan(0)

    const leaked = spans.filter(s => !s.classList.contains('select-none'))
    expect(leaked.map(s => s.textContent)).toEqual([])
  })

  it('still holds once a tile is opened, which is where most of them live', async () => {
    const { container } = await show(fleet([agent(1, 'a1')]))
    const before = hidden(container).length

    // The tile controls are the sentences that were actually pasted, and they
    // arrive with the terminal. Opening it is what a person did.
    fireEvent.click(container.querySelector('[data-tile-control="terminal"]') as HTMLElement)
    await waitFor(() => expect(container.querySelector('[data-fleet-terminal]')).toBeTruthy())

    const spans = hidden(container)
    expect(spans.length).toBeGreaterThanOrEqual(before)
    expect(spans.filter(s => !s.classList.contains('select-none')).map(s => s.textContent)).toEqual([])
  })

  it('keeps the sentence in the DOM — hiding it from copy must not unsay it', () => {
    // The fail direction that would make this fix worse than the defect:
    // dropping the text, or moving it into an `aria-label`, would satisfy the
    // assertion above and take the accessible name with it.
    const { container } = render(<SrOnly>stop the agent — a separate, explicit act</SrOnly>)
    const span = container.querySelector('span') as HTMLElement
    expect(span.textContent).toBe('stop the agent — a separate, explicit act')
    expect(span.classList.contains('sr-only')).toBe(true)
    expect(span.classList.contains('select-none')).toBe(true)
  })
})
