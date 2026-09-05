/**
 * A maximised BOARD or FILE view must behave like an enlarged agent — asked
 * for 2026-09-05: *"a board nézet is tegye fel magát felülre mintha agent tab
 * fül lenne, mert jelenleg ha a boardot felteszem maximizera akkor eltakar
 * minden mást és nem tudok úgy váltogatni mintha normál agent tab lenne …
 * filesra is ez igaz"*, and *"ezek ugyanúgy kellenek működniük mint az agent
 * layoutoknak"*.
 *
 * What the agent layout already did, and what these tests now hold the board
 * and the file view to:
 *
 * - maximising one thing turns the column into a stack with the tab strip on
 *   top, so everything that is not the big tile stays reachable;
 * - the big thing is NAMED in that strip — a panel tab — the way the enlarged
 *   agent is the strip's selected tab;
 * - one click on any tab switches what the big tile is, and the previous big
 *   thing stands down (ONE big thing at a time, at the setters).
 *
 * jsdom performs no layout, so these assert STATE and MARKS, not pixel sizes:
 * which tab is active, which tile claims `flex-1`, whether agent tiles are
 * hidden into the strip. That the strip is one line and the board gets the
 * room is checkable only by looking — ui-quality.md's rule, done separately.
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

const fleet = (agents: Json[], name = 'demo'): Json => ({
  agents: agents.length,
  working: 0,
  unknown: 0,
  owner_reachable: true,
  projects: [{ name, root: `/home/x/${name}`, sources: ['process'], archived: false, agents }],
  quiet_means: 'no outstanding tool call as of the session log’s last flush',
})

/**
 * The board answers its contract probe, or its tile renders null and there is
 * nothing to maximise — the probe is what stands between the test and the
 * panel's chrome. `opts` lets a test vary the producer's own answers: a
 * contract that declares nothing, or a status answer that carries no board
 * command — the two producer shapes that used to render as blank panes.
 */
function installFetch(body: Json, opts: { contract?: Json; boardCommand?: Json | null } = {}) {
  vi.stubGlobal('fetch', vi.fn((url: string) => {
    const u = String(url)
    if (u.includes('/api/fleet/layout')) {
      return Promise.resolve({ ok: true, json: () => Promise.resolve({ version: 1, groups: [], parked: [], ungrouped: [], missing: [] }) } as Response)
    }
    if (u.includes('/api/fleet/files')) {
      return Promise.resolve({ ok: true, json: () => Promise.resolve({ files: [] }) } as Response)
    }
    if (u.includes('/project-status/contract')) {
      return Promise.resolve({
        ok: true,
        json: () => Promise.resolve(opts.contract ?? {
          configured: true, source: 'manifest', command: 'set-project-status',
          commands: ['board'], writeCommands: [], primary: 'board',
        }),
      } as Response)
    }
    if (u.includes('/project-status')) {
      return Promise.resolve({
        ok: true,
        // The command RESULT carries its own ok and a `data.lanes` array — a
        // result without lanes is drawn as a shape-error strip, not a panel.
        json: () => Promise.resolve({
          project: 'demo', ok: true, gaps: {},
          commands: { board: { ok: true, data: { lanes: [], unknown: 0, total: 0 } }, ...opts.boardCommand },
        }),
      } as Response)
    }
    if (u.includes('/api/fleet')) {
      return Promise.resolve({ ok: true, json: () => Promise.resolve(body) } as Response)
    }
    return Promise.resolve({ ok: true, json: () => Promise.resolve({}) } as Response)
  }))
}

async function show(body: Json, opts: { contract?: Json; boardCommand?: Json | null } = {}) {
  installFetch(body, opts)
  const view = render(<Fleet />)
  await waitFor(() => expect(view.container.querySelector('[data-fleet-ownership]')).toBeTruthy())
  return view
}

/** Open the board panel and wait until its chrome — not just its wrapper — is up. */
async function openBoard(container: HTMLElement) {
  fireEvent.click(container.querySelector('[data-fleet-board-open]')!)
  await waitFor(() => expect(container.querySelector('[data-tile-control="board-max"]')).toBeTruthy())
}

async function openFiles(container: HTMLElement) {
  fireEvent.click(container.querySelector('[data-fleet-files-open]')!)
  await waitFor(() => expect(container.querySelector('[data-tile-control="file-max"]')).toBeTruthy())
}

const boardTile = (c: HTMLElement) => c.querySelector('[data-fleet-board-tile]')
const fileTile = (c: HTMLElement) => c.querySelector('[data-fleet-file-tile]')
const boardMax = (c: HTMLElement) => c.querySelector('[data-tile-control="board-max"]') as HTMLElement
const fileMax = (c: HTMLElement) => c.querySelector('[data-tile-control="file-max"]') as HTMLElement
const strip = (c: HTMLElement) => c.querySelector('[data-fleet-agent-tabs]')
const panelTab = (c: HTMLElement, key: string) => c.querySelector(`[data-fleet-panel-tab="${key}"]`) as HTMLElement
const agentTiles = (c: HTMLElement) => c.querySelectorAll('[data-tile-controls]')

beforeEach(() => {
  vi.useRealTimers()
  try { localStorage.clear() } catch { /* no storage here */ }
})
afterEach(() => { cleanup(); vi.unstubAllGlobals(); vi.restoreAllMocks() })

describe('a maximised board joins the tab strip', () => {
  it('puts the strip up with the board named as its active panel tab', async () => {
    const { container } = await show(fleet([agent(1, 'a1'), agent(2, 'a2')]))
    await openBoard(container)
    fireEvent.click(boardMax(container))

    await waitFor(() => expect(strip(container)).toBeTruthy())
    expect(panelTab(container, 'board').getAttribute('data-fleet-panel-tab-active')).toBe('on')
    expect(boardTile(container)!.getAttribute('data-fleet-board-max')).toBe('on')
  })

  /** The agents are IN the strip, not gone — the false-absence direction. */
  it('hides the agent tiles only because the strip holds every one of them', async () => {
    const { container } = await show(fleet([agent(1, 'a1'), agent(2, 'a2')]))
    await openBoard(container)
    fireEvent.click(boardMax(container))

    await waitFor(() => expect(agentTiles(container)).toHaveLength(0))
    expect(container.querySelectorAll('[data-fleet-agent-tab]')).toHaveLength(2)
  })

  /** The switch the user could not make: from the big board back to an agent. */
  it('stands the board down and enlarges the agent when an agent tab is clicked', async () => {
    const { container } = await show(fleet([agent(1, 'a1'), agent(2, 'a2')]))
    await openBoard(container)
    fireEvent.click(boardMax(container))
    await waitFor(() => expect(strip(container)).toBeTruthy())

    fireEvent.click(container.querySelector('[data-fleet-agent-tab="2"]')!)
    await waitFor(() => expect(boardTile(container)!.getAttribute('data-fleet-board-max')).toBe('off'))
    expect(container.querySelector('[data-fleet-agent-tab="2"]')!.getAttribute('data-fleet-agent-tab-active')).toBe('on')
  })

  /** …and back: from an enlarged agent, one click on the board tab. */
  it('switches the big tile to the board when its panel tab is clicked from an enlarged agent', async () => {
    const { container } = await show(fleet([agent(1, 'a1'), agent(2, 'a2')]))
    await openBoard(container)
    fireEvent.click(container.querySelector('[data-tile-controls="1"] [data-tile-control="enlarge"]')!)
    await waitFor(() => expect(strip(container)).toBeTruthy())
    expect(panelTab(container, 'board').getAttribute('data-fleet-panel-tab-active')).toBeNull()

    fireEvent.click(panelTab(container, 'board'))
    await waitFor(() => expect(boardTile(container)!.getAttribute('data-fleet-board-max')).toBe('on'))
    expect(container.querySelector('[data-fleet-agent-tab="1"]')!.getAttribute('data-fleet-agent-tab-active')).toBeNull()
  })

  /** ONE big thing at a time — board and files may not both claim the space. */
  it('stands a maximised file view down when the board tab switches the big tile', async () => {
    const { container } = await show(fleet([agent(1, 'a1')]))
    await openBoard(container)
    await openFiles(container)
    fireEvent.click(fileMax(container))
    await waitFor(() => expect(fileTile(container)!.getAttribute('data-fleet-file-max')).toBe('on'))

    fireEvent.click(panelTab(container, 'board'))
    await waitFor(() => expect(boardTile(container)!.getAttribute('data-fleet-board-max')).toBe('on'))
    expect(fileTile(container)!.getAttribute('data-fleet-file-max')).toBe('off')
  })
})

describe('a board that is not there says so — seen 2026-09-06 on a real project', () => {
  /**
   * A project whose contract answers `configured: false` (this repository's
   * own answer, measured live) used to render as a BLANK maximised pane under
   * an active "board" tab — no title bar, no message, nothing. A gap is not a
   * zero, and a deliberate "no" is not a blank either.
   */
  it('names a project that declares no board instead of rendering a blank pane', async () => {
    const { container } = await show(fleet([agent(1, 'a1')]), {
      contract: { configured: false, source: null, command: null, commands: [], writeCommands: [], primary: null },
    })
    // NOT `openBoard`: these two cases render a strip INSTEAD of the panel
    // chrome, so the maximise control these tests wait on never arrives —
    // that absence is the point under test.
    fireEvent.click(container.querySelector('[data-fleet-board-open]')!)
    await waitFor(() => expect(container.querySelector('[data-fleet-board-strip="not-declared"]')).toBeTruthy())
  })

  /**
   * The contract SAID there is a board, the route answered, the answer carried
   * no board command — `result` stays null forever, which used to mean a blank
   * pane under a promised board. The contradiction belongs on screen.
   */
  it('says the contract moved when the answer carries no board command', async () => {
    // A DIFFERENT project than the tests above: the answer cache is
    // module-level and by design renders its last valid board instantly on
    // remount — reusing 'demo' would show test 1's cached board, not the gap.
    const { container } = await show(fleet([agent(11, 'p2-a1')], 'demo-two'), { boardCommand: { board: null } })
    fireEvent.click(container.querySelector('[data-fleet-board-open]')!)
    await waitFor(() => expect(container.querySelector('[data-fleet-board-strip="no-command"]')).toBeTruthy())
  })
})

describe('the full-screen board is not a sealed room', () => {
  /**
   * The overlay covers the whole window ON PURPOSE — that is what full screen
   * means here — but covering is not sealing: the strip travels with it, so
   * the reader can still leave with one click to anything the strip names.
   * Reported the same day as the maximise fix: *"nem tudok úgy váltogatni
   * mintha normál agent tab lenne"*.
   */
  it('carries the tab strip, and an agent tab leaves full screen', async () => {
    const { container } = await show(fleet([agent(1, 'a1'), agent(2, 'a2')]))
    await openBoard(container)
    fireEvent.click(container.querySelector('[data-tile-control="board-fullscreen"]')!)
    await waitFor(() => expect(container.querySelector('[data-fleet-board-fullscreen-root]')).toBeTruthy())
    expect(panelTab(container, 'board').getAttribute('data-fleet-panel-tab-active')).toBe('on')

    fireEvent.click(container.querySelector('[data-fleet-agent-tab="1"]')!)
    await waitFor(() => expect(container.querySelector('[data-fleet-board-fullscreen-root]')).toBeNull())
    expect(container.querySelector('[data-fleet-agent-tab="1"]')!.getAttribute('data-fleet-agent-tab-active')).toBe('on')
  })
})
