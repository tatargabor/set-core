/**
 * The ORDER in which a re-attached terminal takes its two geometries — B-16.
 *
 * Reported 2026-08-19: *"terminal also status bar elromlik ha projektet valtok,
 * beleirok, majd visszavaltok"* — and then the half that names the cause:
 * *"beiras utan megjavul"*. A keystroke changes nothing about the socket, the
 * pty or the buffer. What it does is make the remote program REPAINT. So the
 * screen was stale rather than lost, and a stale screen after a re-attach means
 * the replay was rendered on a grid it was never composed for.
 *
 * A terminal is a fixed-grid device. The buffered tail is bytes a program laid
 * out for a specific number of columns, so rendering it at another width does
 * not adapt the screen — it destroys it, silently, because the result still
 * looks like a terminal.
 *
 * Two geometries are therefore in play and their ORDER is the whole fix:
 *
 *   1. the pty's, adopted before a single replay byte is written;
 *   2. the tile's, sent back only once the replay has landed.
 *
 * Doing the second first resizes the grid out from under the bytes it is meant
 * to protect, which is the bug one layer down. That is what this file measures,
 * and nothing else here can: `fleetTerminal.test.ts` asserts the decisions and
 * `fleetTerminalSurface.test.tsx` asserts what is on screen — both stay green
 * with the order reversed.
 */
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { cleanup, fireEvent, render, waitFor } from '@testing-library/react'

/** Every call to the emulator, in order — the order IS the subject here. */
const calls: string[] = []

vi.mock('@xterm/xterm/css/xterm.css', () => ({}))
vi.mock('@xterm/addon-fit', () => ({
  FitAddon: class {
    fit() { calls.push('fit') }
  },
}))
vi.mock('@xterm/xterm', () => ({
  Terminal: class {
    cols = 120
    rows = 40
    open() { calls.push('open') }
    loadAddon() { /* the fit addon, stubbed above */ }
    focus() { /* no keyboard in jsdom */ }
    dispose() { /* nothing to release */ }
    resize(cols: number, rows: number) {
      calls.push(`resize:${cols}x${rows}`)
      this.cols = cols
      this.rows = rows
    }
    write(data: Uint8Array) { calls.push(`write:${data.length}`) }
    onData() { return { dispose() { /* no listener to release */ } } }
    /* B-60's two surfaces. Neither is this file's subject — the geometry is —
       but a mock that lacks them makes the component throw before the order
       under test is ever recorded, which would read as a geometry failure. */
    attachCustomKeyEventHandler() { /* the copy key, not exercised here */ }
    getSelection() { return this._sel ?? '' }
    clearSelection() { this._sel = '' }
  },
}))

import FleetTerminal from '../../src/components/FleetTerminal'

/** The one socket the component opens, reachable from the test. */
let socket: FakeSocket
const sent: string[] = []

class FakeSocket {
  static OPEN = 1
  readyState = 1
  binaryType = ''
  onmessage: ((e: { data: unknown }) => void) | null = null
  onerror: (() => void) | null = null
  onclose: (() => void) | null = null
  constructor() { socket = this }
  send(payload: unknown) {
    if (typeof payload === 'string') sent.push(payload)
  }
  close() { /* the component detaches; nothing to tear down here */ }
  /** What the bridge sends first, before a single replay byte. */
  attach(over: Record<string, unknown> = {}) {
    this.onmessage?.({ data: JSON.stringify({
      event: 'attached', attached: 't-1', replayed_bytes: 0,
      replay_truncated: false, viewers: 1, rows: 44, cols: 132, ...over,
    }) })
  }
  replay(bytes: number) {
    this.onmessage?.({ data: new Uint8Array(bytes).buffer })
  }
}

const resizes = () => sent.map(s => JSON.parse(s)).filter(m => m.resize).map(m => m.resize)
/**
 * What the pty is left at. Settling sends TWO sizes, not one — see the repaint
 * nudge at the bottom of this file — so "the size it ended on" is the last one,
 * and a count is asserted only where the count is the subject.
 */
const finalSize = () => resizes()[resizes().length - 1]

beforeEach(() => {
  calls.length = 0
  sent.length = 0
  vi.stubGlobal('WebSocket', FakeSocket)
  vi.stubGlobal('ResizeObserver', class {
    observe() { /* the initial observation is not what this file measures */ }
    disconnect() { /* nothing observed */ }
  })
})
afterEach(() => { cleanup(); vi.unstubAllGlobals(); vi.useRealTimers() })

async function mounted() {
  render(<FleetTerminal label="t-1" onClose={() => {}} />)
  await waitFor(() => expect(socket).toBeTruthy())
  await waitFor(() => expect(calls).toContain('open'))
}

describe('the replay renders at the geometry it was drawn at', () => {
  it('adopts the pty’s shape before writing a single replayed byte', async () => {
    await mounted()
    socket.attach({ replayed_bytes: 300 })
    await waitFor(() => expect(calls).toContain('resize:132x44'))
    socket.replay(300)

    const adopted = calls.indexOf('resize:132x44')
    const firstWrite = calls.findIndex(c => c.startsWith('write:'))
    expect(adopted).toBeGreaterThanOrEqual(0)
    expect(firstWrite).toBeGreaterThanOrEqual(0)
    expect(adopted, 'the replay was rendered before the pty’s shape was adopted')
      .toBeLessThan(firstWrite)
  })

  it('does not push its own size while the replay is still arriving', async () => {
    await mounted()
    socket.attach({ replayed_bytes: 300 })
    await waitFor(() => expect(calls).toContain('resize:132x44'))

    socket.replay(100)
    expect(resizes(), 'the grid was resized out from under the replay').toHaveLength(0)

    socket.replay(200)
    await waitFor(() => expect(resizes()).toHaveLength(2))
  })

  /**
   * And the tile's size is not forgotten. Adopting the pty's shape is a step,
   * not a policy: the terminal that ends up on screen is the tile's.
   */
  it('sends the tile’s own size once the replay has landed', async () => {
    await mounted()
    socket.attach({ replayed_bytes: 50 })
    socket.replay(50)
    await waitFor(() => expect(resizes()).toHaveLength(2))
    // The FITTED size, not the ack's — the stub's `fit` leaves the terminal at
    // whatever the last resize set, which is the pty's, so this asserts the
    // message went out at all and that it is what the pty is LEFT at.
    expect(finalSize()).toEqual({ rows: 44, cols: 132 })
  })

  it('sends it immediately when there is nothing to replay', async () => {
    await mounted()
    socket.attach({ replayed_bytes: 0 })
    await waitFor(() => expect(resizes()).toHaveLength(2))
  })

  /**
   * The failure this must not have. A replay that arrives SHORT — a dropped
   * frame, a socket ending mid-burst — would otherwise leave the pty at the
   * size it was found in, for ever, and resizing the tile would silently stop
   * working. Late is the safe direction; never is not.
   */
  it('settles anyway when the replay never finishes arriving', async () => {
    vi.useFakeTimers()
    render(<FleetTerminal label="t-1" onClose={() => {}} />)
    await vi.waitFor(() => expect(socket).toBeTruthy())
    await vi.waitFor(() => expect(calls).toContain('open'))

    socket.attach({ replayed_bytes: 5000 })
    socket.replay(10)
    expect(resizes()).toHaveLength(0)

    await vi.advanceTimersByTimeAsync(1500)
    expect(finalSize(), 'a short replay left the pty stuck at a size nobody chose')
      .toEqual({ rows: 44, cols: 132 })
  })

  /**
   * THE REPAINT — B-76.
   *
   * Reported 2026-08-24 by the user, switching between agent tabs: the status
   * footer comes back partial, and dragging the layout border repairs it. A
   * drag changes the size, and a size change is the only thing here that
   * reaches the remote program at all.
   *
   * The replay is a ring buffer, so a tail that begins mid-stream cannot
   * reconstruct what was drawn before it — and the row drawn last and least
   * often is the footer. Sending the size the pty ALREADY HAS repairs nothing:
   * `TIOCSWINSZ` with an unchanged struct raises no `SIGWINCH`, so the program
   * is never asked to redraw and the stale screen stays.
   *
   * Hence a size that differs, immediately before the real one. This asserts
   * the pair AND the order: a nudge sent after the real size would leave the
   * pty one row short of the tile, which is B-29 rebuilt by hand.
   */
  it('asks the program to repaint even when its size did not change', async () => {
    await mounted()
    socket.attach({ replayed_bytes: 0 })
    await waitFor(() => expect(resizes()).toHaveLength(2))

    expect(resizes()[0], 'nothing differed, so nothing was asked to repaint')
      .toEqual({ rows: 43, cols: 132 })
    expect(resizes()[1], 'the pty was left at a size nobody is looking at')
      .toEqual({ rows: 44, cols: 132 })
  })

  /**
   * And it is never sent at a geometry no terminal can hold. One row is the
   * floor: nudging a one-row terminal to zero would be a resize the pty may
   * refuse, which is a repaint that silently does not happen.
   */
  it('does not nudge a terminal that has no row to spare', async () => {
    await mounted()
    socket.attach({ replayed_bytes: 0, rows: 1, cols: 80 })
    await waitFor(() => expect(resizes()).toHaveLength(1))
    expect(resizes()[0]).toEqual({ rows: 1, cols: 80 })
  })

  /**
   * `null` is not a size. The owner answers `null` when the fd cannot be read,
   * and a viewer that substituted a default would reformat a screen drawn at
   * 200 columns into 80 — applying a guess, which is worse than doing nothing.
   */
  it('leaves its own shape alone when the owner could not measure the pty', async () => {
    await mounted()
    socket.attach({ replayed_bytes: 20, rows: null, cols: null })
    socket.replay(20)
    await waitFor(() => expect(resizes()).toHaveLength(2))
    expect(calls.filter(c => c.startsWith('resize:'))).toHaveLength(0)
  })
})

/**
 * Requirement 5.4 on the SURFACE — AC-93.
 *
 * The server half is proven in `test_fleet_ownerd.py::test_a_viewer_detaching_
 * leaves_the_agent_held_and_running`: a detach never stops the agent. That test
 * says nothing about the screen, and the screen is where the mistake gets made
 * — a single ✕ doing both would make every reader who wanted to stop watching
 * kill the thing they were watching.
 *
 * So: two controls, never one, and the destructive one takes two clicks.
 */
describe('closing the view is not stopping the agent', () => {
  it('offers a stop and a close as two separate controls', async () => {
    await mounted()
    socket.attach({ replayed_bytes: 0 })
    await waitFor(() => expect(resizes()).toHaveLength(2))

    const stop = document.querySelector('[data-fleet-terminal-stop]')
    const close = document.querySelector('[data-fleet-terminal-close]')
    expect(stop, 'no stop control').toBeTruthy()
    expect(close, 'no close control').toBeTruthy()
    expect(stop).not.toBe(close)
  })

  it('closes without asking the server to stop anything', async () => {
    const closed = vi.fn()
    render(<FleetTerminal label="t-1" onClose={closed} />)
    await waitFor(() => expect(socket).toBeTruthy())
    await waitFor(() => expect(calls).toContain('open'))
    socket.attach({ replayed_bytes: 0 })

    const fetched = vi.fn(() => Promise.resolve({ ok: true, json: () => Promise.resolve({}) } as Response))
    vi.stubGlobal('fetch', fetched)
    fireEvent.click(document.querySelector('[data-fleet-terminal-close]')!)

    expect(closed).toHaveBeenCalled()
    expect(fetched, 'closing the view reached the stop endpoint').not.toHaveBeenCalled()
  })

  /**
   * And the stop does not fire on the first click. An icon that stops a running
   * agent the instant it is touched is the same hazard as one control doing
   * both — the confirm step is what an icon alone could not carry, which is why
   * it survived the change to icons.
   */
  it('does not stop the agent on the first click', async () => {
    await mounted()
    socket.attach({ replayed_bytes: 0 })

    const fetched = vi.fn(() => Promise.resolve({ ok: true, json: () => Promise.resolve({}) } as Response))
    vi.stubGlobal('fetch', fetched)
    fireEvent.click(document.querySelector('[data-fleet-terminal-stop]')!)
    expect(fetched, 'one click stopped a running agent').not.toHaveBeenCalled()

    // Armed, and now it is a different control.
    await waitFor(() => expect(document.querySelector('[data-fleet-terminal-stop-confirm]')).toBeTruthy())
    fireEvent.click(document.querySelector('[data-fleet-terminal-stop-confirm]')!)
    await waitFor(() => expect(fetched).toHaveBeenCalled())
    expect(String(fetched.mock.calls[0][0])).toContain('/stop')
  })
})

/**
 * WHERE the status row is drawn — asked for 2026-08-22: *"egy sorba kerüljön a
 * csempe ikonja és a layout ikon"*.
 *
 * The tile carried two icon rows for one agent, one directly under the other.
 * The row now moves into the tile's title bar through a portal, and the portal
 * is what this measures: the same row, the same owner of the state, a different
 * parent. Asserted in BOTH directions, because a component that only draws its
 * header when someone remembers to pass a slot is a component that will one day
 * render headerless and say nothing about it.
 */
describe('the terminal status row lands where the tile puts it', () => {
  it('draws into the given slot, and inside itself when there is none', async () => {
    const slot = document.createElement('span')
    document.body.appendChild(slot)
    const { unmount } = render(<FleetTerminal label="t-1" onClose={() => {}} headerSlot={slot} />)
    await waitFor(() => expect(socket).toBeTruthy())
    socket.attach({ replayed_bytes: 0 })

    await waitFor(() => expect(slot.querySelector('[data-fleet-terminal-header]')).toBeTruthy())
    expect(slot.querySelector('[data-fleet-terminal-header]')!.getAttribute('data-fleet-terminal-header')).toBe('merged')
    // The controls go WITH it — a merged row that left the close button behind
    // would be a row that says what is happening and cannot be acted on.
    expect(slot.querySelector('[data-fleet-terminal-close]')).toBeTruthy()
    // And the terminal's own body no longer holds a header of its own.
    const body = document.querySelector('[data-fleet-terminal="t-1"]')!
    expect(body.querySelector('[data-fleet-terminal-header]')).toBeNull()
    unmount()
    slot.remove()

    render(<FleetTerminal label="t-2" onClose={() => {}} />)
    await waitFor(() => expect(document.querySelector('[data-fleet-terminal="t-2"] [data-fleet-terminal-header]')).toBeTruthy())
    expect(document.querySelector('[data-fleet-terminal="t-2"] [data-fleet-terminal-header]')!
      .getAttribute('data-fleet-terminal-header')).toBe('own-row')
  })
})
