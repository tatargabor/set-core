/**
 * The panel as a workspace: several terminals at once, one agent alone, and
 * where the keyboard is — asserted on what reaches the screen.
 *
 * `fleetWorkspaceState.test.ts` asserts the decisions; this asserts the wiring,
 * and the two differ exactly when the surface is wrong. The terminal component
 * is STUBBED here — it loads a ~300 KB emulator and opens a WebSocket, neither
 * of which belongs in a jsdom unit test — so what this file measures is the
 * panel's side of the contract: how many terminals are mounted, which one is
 * told it is full screen, and what the tile does with the focus the terminal
 * reports. The emulator's own focus handling is not covered here and is not
 * claimed to be.
 */
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react'

vi.mock('../../src/components/FleetTerminal', () => ({
  default: ({ label, full, onToggleFull, onFocusChange }: {
    label: string
    full?: boolean
    onToggleFull?: () => void
    onFocusChange?: (on: boolean) => void
  }) => (
    <div data-fleet-terminal={label} data-fleet-terminal-full={full ? 'on' : 'off'}>
      <button data-stub-full={label} onClick={onToggleFull}>full</button>
      <button data-stub-focus={label} onClick={() => onFocusChange?.(true)}>focus</button>
    </div>
  ),
}))

import Fleet from '../../src/pages/Fleet'

type Json = Record<string, unknown>

function agent(pid: number, name: string, extra: Json = {}): Json {
  return {
    pid, name, project: 'demo', branch: 'main', session_id: `s${pid}`, binding_confirmed: true,
    sources: ['process'], kind: 'interactive', state: 'quiet', tool: null,
    tool_elapsed_seconds: null, other_tools: [], last_movement_seconds: 5,
    unknown_reason: null, waiting_for: null, declaration_ignored: null,
    population: 'started-here', terminal_label: `t-${pid}`,
    ...extra,
  }
}

const fleet = (agents: Json[], over: Json = {}): Json => ({
  agents: agents.length,
  working: 0,
  unknown: agents.filter(a => a.state === 'unknown').length,
  owner_reachable: true,
  projects: [{ name: 'demo', root: '/home/x/demo', sources: ['process'], archived: false, agents }],
  quiet_means: 'no outstanding tool call as of the session log’s last flush',
  ...over,
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

const openTerminals = (c: HTMLElement) => [...c.querySelectorAll('[data-fleet-terminal]')]
  .map(e => e.getAttribute('data-fleet-terminal'))

beforeEach(() => {
  vi.useRealTimers()
  try { localStorage.clear() } catch { /* no storage here */ }
})
afterEach(() => { cleanup(); vi.unstubAllGlobals(); vi.restoreAllMocks() })

describe('more than one terminal at a time', () => {
  it('opens a second terminal without closing the first', async () => {
    const { container } = await show(fleet([agent(1, 'a1'), agent(2, 'a2')]))

    // The CLOSED one: with icons, an open terminal's control stays in place and
    // becomes "close", so `[0]` would toggle the first one shut instead of
    // opening the second. The state is in the attribute, so ask for it.
    const closed = () => container.querySelectorAll('[data-tile-control="terminal"]:not([data-tile-control-active="on"])')
    fireEvent.click(closed()[0])
    await waitFor(() => expect(openTerminals(container)).toEqual(['t-1']))

    fireEvent.click(container.querySelectorAll('[data-tile-control="terminal"]:not([data-tile-control-active="on"])')[0])
    await waitFor(() => expect(openTerminals(container).sort()).toEqual(['t-1', 't-2']))
  })

  it('closes one and leaves the other attached', async () => {
    const { container } = await show(fleet([agent(1, 'a1'), agent(2, 'a2')]))
    fireEvent.click(container.querySelectorAll('[data-tile-control="terminal"]:not([data-tile-control-active="on"])')[0])
    await waitFor(() => expect(openTerminals(container)).toEqual(['t-1']))
    fireEvent.click(container.querySelectorAll('[data-tile-control="terminal"]:not([data-tile-control-active="on"])')[0])
    await waitFor(() => expect(openTerminals(container)).toHaveLength(2))

    fireEvent.click(container.querySelector('[data-tile-control="terminal"][data-tile-control-active="on"]')!)
    await waitFor(() => expect(openTerminals(container)).toEqual(['t-2']))
  })

  it('offers no terminal for a foreign agent, however many are open', async () => {
    const { container } = await show(fleet([agent(1, 'a1'), agent(2, 'a2', { population: 'foreign', terminal_label: null })]))
    fireEvent.click(container.querySelectorAll('[data-tile-control="terminal"]:not([data-tile-control-active="on"])')[0])
    await waitFor(() => expect(openTerminals(container)).toEqual(['t-1']))
    expect(container.querySelectorAll('[data-tile-control="terminal"]')).toHaveLength(1)
  })
})

describe('one agent alone, and what that covers', () => {
  it('shows only the focused agent', async () => {
    const { container } = await show(fleet([agent(1, 'a1'), agent(2, 'a2')]))
    expect(container.querySelectorAll('[data-fleet-ownership]')).toHaveLength(2)

    fireEvent.click(container.querySelectorAll('[data-tile-controls="1"] [data-tile-control="focus"]')[0])
    await waitFor(() => expect(container.querySelector('[data-fleet-focused="1"]')).toBeTruthy())
    expect(container.querySelectorAll('[data-fleet-ownership]')).toHaveLength(1)
  })

  /**
   * The rule that outranks the layout (`ui-quality.md`): compacting must never
   * hide a failure. A full screen hides the most of any layout here, so what it
   * covers is counted where the reader is standing — and the states that need
   * acting on are named, not just totalled.
   */
  it('says how many agents it is covering, and marks the ones in a state worth acting on', async () => {
    const { container } = await show(fleet([
      agent(1, 'a1'),
      agent(2, 'a2', { state: 'unknown', unknown_reason: 'no session log' }),
      agent(3, 'a3', { state: 'waiting', waiting_for: 'approval' }),
    ]))
    fireEvent.click(container.querySelectorAll('[data-tile-controls="1"] [data-tile-control="focus"]')[0])

    await waitFor(() => expect(container.querySelector('[data-fleet-focus-cover]')).toBeTruthy())
    expect(container.querySelector('[data-fleet-focus-cover]')!.getAttribute('data-fleet-focus-cover')).toBe('2')
    expect(container.querySelector('[data-fleet-focus-hidden="unknown"]')!.textContent).toMatch(/1 unknown/)
    expect(container.querySelector('[data-fleet-focus-hidden="waiting"]')!.textContent).toMatch(/1 waiting/)
  })

  it('does not announce hidden states it does not have', async () => {
    const { container } = await show(fleet([agent(1, 'a1'), agent(2, 'a2')]))
    fireEvent.click(container.querySelectorAll('[data-tile-controls="1"] [data-tile-control="focus"]')[0])
    await waitFor(() => expect(container.querySelector('[data-fleet-focus-cover]')).toBeTruthy())
    expect(container.querySelector('[data-fleet-focus-hidden="unknown"]')).toBeNull()
    expect(container.querySelector('[data-fleet-focus-hidden="waiting"]')).toBeNull()
  })

  it('comes back to the grid, with every agent again', async () => {
    const { container } = await show(fleet([agent(1, 'a1'), agent(2, 'a2')]))
    fireEvent.click(container.querySelectorAll('[data-tile-controls="1"] [data-tile-control="focus"]')[0])
    await waitFor(() => expect(container.querySelectorAll('[data-fleet-ownership]')).toHaveLength(1))
    fireEvent.click(container.querySelector('[data-fleet-focus-exit')!)
    await waitFor(() => expect(container.querySelectorAll('[data-fleet-ownership]')).toHaveLength(2))
  })

  it('tells the focused agent’s terminal it is full screen, and the others that they are not', async () => {
    const { container } = await show(fleet([agent(1, 'a1'), agent(2, 'a2')]))
    fireEvent.click(container.querySelectorAll('[data-tile-control="terminal"]:not([data-tile-control-active="on"])')[0])
    await waitFor(() => expect(openTerminals(container)).toEqual(['t-1']))
    expect(container.querySelector('[data-fleet-terminal="t-1"]')!.getAttribute('data-fleet-terminal-full')).toBe('off')

    fireEvent.click(container.querySelectorAll('[data-tile-controls="1"] [data-tile-control="focus"]')[0])
    await waitFor(() => expect(
      container.querySelector('[data-fleet-terminal="t-1"]')!.getAttribute('data-fleet-terminal-full'),
    ).toBe('on'))
  })
})

describe('where the keyboard is', () => {
  it('marks the tile whose terminal has the focus, and only that one', async () => {
    const { container } = await show(fleet([agent(1, 'a1'), agent(2, 'a2')]))
    fireEvent.click(container.querySelectorAll('[data-tile-control="terminal"]:not([data-tile-control-active="on"])')[0])
    await waitFor(() => expect(openTerminals(container)).toEqual(['t-1']))
    fireEvent.click(container.querySelectorAll('[data-tile-control="terminal"]:not([data-tile-control-active="on"])')[0])
    await waitFor(() => expect(openTerminals(container)).toHaveLength(2))

    expect(container.querySelector('[data-fleet-typing]')).toBeNull()

    fireEvent.click(container.querySelector('[data-stub-focus="t-2"]')!)
    await waitFor(() => expect(container.querySelectorAll('[data-fleet-typing]')).toHaveLength(1))
    expect(container.querySelector('[data-fleet-typing]')!.getAttribute('data-fleet-typing')).toBe('2')
  })
})

describe('a log opens where the tile already is', () => {
  /**
   * Before this, opening a log meant enlarging the tile: one log at a time, and
   * every other agent collapsed to a row. Raised 2026-08-19 — the grid tiles
   * were too small to read anything in, and the fix for that must not be "hide
   * the others".
   */
  it('opens two logs at once, in the grid, with every tile still a tile', async () => {
    const { container } = await show(fleet([agent(1, 'a1'), agent(2, 'a2'), agent(3, 'a3')]))
    fireEvent.click(container.querySelectorAll('[data-tile-controls="1"] [data-tile-control="log"]')[0])
    fireEvent.click(container.querySelectorAll('[data-tile-controls="2"] [data-tile-control="log"]')[0])

    await waitFor(() => expect(container.querySelectorAll('[data-log-tab="conversation"]')).toHaveLength(2))
    // The negative half: nothing collapsed to a row, and nothing was enlarged.
    expect(container.querySelectorAll('[data-fleet-row]')).toHaveLength(0)
    expect(container.querySelector('[data-fleet-enlarged]')).toBeNull()
    expect(container.querySelectorAll('[data-fleet-ownership]')).toHaveLength(3)
  })

  it('closes one log and leaves the other open', async () => {
    const { container } = await show(fleet([agent(1, 'a1'), agent(2, 'a2')]))
    fireEvent.click(container.querySelectorAll('[data-tile-controls="1"] [data-tile-control="log"]')[0])
    fireEvent.click(container.querySelectorAll('[data-tile-controls="2"] [data-tile-control="log"]')[0])
    await waitFor(() => expect(container.querySelectorAll('[data-log-tab="conversation"]')).toHaveLength(2))

    fireEvent.click(container.querySelectorAll('[data-tile-controls="1"] [data-tile-control="log"]')[0])
    await waitFor(() => expect(container.querySelectorAll('[data-log-tab="conversation"]')).toHaveLength(1))
  })

  it('keeps enlarging as its own act, which still leaves the others as rows', async () => {
    const { container } = await show(fleet([agent(1, 'a1'), agent(2, 'a2')]))
    fireEvent.click(container.querySelectorAll('[data-tile-controls="1"] [data-tile-control="enlarge"]')[0])
    await waitFor(() => expect(container.querySelector('[data-fleet-enlarged="1"]')).toBeTruthy())
    expect(container.querySelectorAll('[data-fleet-row]')).toHaveLength(1)
  })
})

describe('ownership is on the tile, not only in a sentence', () => {
  it('marks each tile with what the producer measured', async () => {
    const { container } = await show(fleet([
      agent(1, 'ours'),
      agent(2, 'foreign', { population: 'foreign', terminal_label: null }),
      agent(3, 'silent', { population: undefined, terminal_label: null }),
    ]))
    const marks = [...container.querySelectorAll('[data-fleet-ownership]')]
      .map(e => e.getAttribute('data-fleet-ownership'))
    expect(marks).toEqual(['ours', 'foreign', 'unknown'])
  })
})
