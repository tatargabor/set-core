/**
 * Copying out of a terminal — B-65, fourth round.
 *
 * Every previous round passed all its tests and failed a real hand:
 *
 *  - B-60 chose `Ctrl+Shift+C`, which Chrome claims for its inspector, so the
 *    handler never ran.
 *  - B-64 had the panel copy via the clipboard APIs; the async one never
 *    answered and the synchronous one was refused — but that was measured in a
 *    HIDDEN automation tab, a context no reader is ever in.
 *  - B-65 drew the wrong conclusion from that measurement — "let the browser do
 *    the copy" — and the reader refuted it in their own visible tab on
 *    2026-09-01: Ctrl+C and right-click copy BOTH failed on the served, fixed
 *    bundle. The reason was structural: **xterm's selection is not a DOM
 *    selection**, so the browser never had anything to copy; and the
 *    right-button mousedown clears the xterm selection before any menu opens.
 *
 * Round 4: the panel performs the copy itself, synchronously, inside the
 * gesture — from a real keystroke or contextmenu, transient activation is
 * intact, which is the context `execCommand` has always worked in. The
 * properties below are the ones that must survive any rewrite:
 *
 *   1. The copy runs INSIDE the keydown / contextmenu call stack, not after a
 *      timeout — and `copySelection` tries its synchronous write first.
 *   2. The outcome is never silent — success, refusal, or (when the agent owns
 *      the mouse and nothing is selected) the instruction to Shift-drag.
 *   3. The selection is cleared only AFTER the copy's outcome, so the
 *      interrupt stays one keystroke away.
 *   4. A right-click with a selection IS the copy; without one, the browser
 *      menu is left completely alone.
 */
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { cleanup, render, waitFor } from '@testing-library/react'

let handler: ((e: KeyboardEvent) => boolean) | null = null
let term: any = null
let opened: string[] = []
let execCommand: ReturnType<typeof vi.fn>

vi.mock('@xterm/xterm/css/xterm.css', () => ({}))
vi.mock('@xterm/addon-fit', () => ({ FitAddon: class { fit() { /* geometry is elsewhere */ } } }))
vi.mock('@xterm/xterm', () => ({
  Terminal: class {
    cols = 120
    rows = 40
    _sel = ''
    constructor() { term = this }
    open() { opened.push('open') }
    loadAddon() { /* stubbed */ }
    focus() { /* no keyboard in jsdom */ }
    dispose() { /* nothing to release */ }
    resize() { /* geometry is elsewhere */ }
    write() { /* no bytes here */ }
    onData() { return { dispose() { /* no listener */ } } }
    attachCustomKeyEventHandler(fn: (e: KeyboardEvent) => boolean) { handler = fn }
    getSelection() { return this._sel }
    clearSelection() { this._sel = '' }
  },
}))

import FleetTerminal from '../../src/components/FleetTerminal'

class FakeSocket {
  static OPEN = 1
  readyState = 1
  binaryType = ''
  onmessage: ((e: { data: unknown }) => void) | null = null
  onerror: (() => void) | null = null
  onclose: (() => void) | null = null
  send() { /* nothing measured here */ }
  close() { /* nothing to tear down */ }
}

const key = (over: Partial<KeyboardEvent>) =>
  ({ type: 'keydown', ctrlKey: false, shiftKey: false, altKey: false, metaKey: false, key: 'a', ...over }) as KeyboardEvent

const host = () => document.querySelector('[data-fleet-terminal-host]') as HTMLElement

/** A `copy` event shaped the way the browser fires one when it asks who owns the data. */
function fireCopy() {
  const written: Record<string, string> = {}
  const ev = new Event('copy', { bubbles: true, cancelable: true }) as ClipboardEvent
  Object.defineProperty(ev, 'clipboardData', {
    value: { setData: (t: string, v: string) => { written[t] = v } },
  })
  host().dispatchEvent(ev)
  return { ev, written }
}

/** The mouse-tracking class the agent's TUI sets, on the element the component reads. */
function agentTakesTheMouse() {
  host().insertAdjacentHTML('beforeend', '<div class="terminal xterm enable-mouse-events"></div>')
}

const notice = () => document.querySelector('[data-fleet-terminal-copied]')

beforeEach(async () => {
  handler = null; term = null; opened = []
  // jsdom does not implement execCommand; the stub stands in for the real
  // browser's synchronous copy. The REFUSAL path flips this to `false`.
  execCommand = vi.fn(() => true)
  document.execCommand = execCommand as unknown as typeof document.execCommand
  vi.stubGlobal('WebSocket', FakeSocket)
  vi.stubGlobal('ResizeObserver', class {
    observe() { /* not this file's subject */ }
    disconnect() { /* nothing observed */ }
  })
  render(<FleetTerminal label="t-1" onClose={() => {}} />)
  await waitFor(() => expect(opened).toContain('open'))
  await waitFor(() => expect(handler).toBeTruthy())
})
afterEach(() => { cleanup(); vi.unstubAllGlobals(); vi.useRealTimers() })

describe('round 4 — the panel copies, inside the gesture', () => {
  it('copies synchronously during the Ctrl+C keydown, not after a timeout', async () => {
    term._sel = 'the line the reader picked'
    expect(handler!(key({ ctrlKey: true, key: 'c' }))).toBe(false)
    // Round 3's refuted pattern was trusting the browser to copy afterwards;
    // the panel now does it while the keystroke's activation is alive.
    expect(execCommand).toHaveBeenCalled()
    await waitFor(() => expect(notice()?.getAttribute('data-fleet-terminal-copied')).toBe('yes'))
    expect(notice()?.textContent).toContain('26')
  })

  it('clears the selection only AFTER the outcome, so the interrupt comes back', async () => {
    term._sel = 'exactly this'
    handler!(key({ ctrlKey: true, key: 'c' }))
    expect(term.getSelection()).toBe('exactly this')
    await waitFor(() => expect(term.getSelection()).toBe(''))
    expect(handler!(key({ ctrlKey: true, key: 'c' }))).toBe(true)
  })

  it('ANNOUNCES a refused synchronous write instead of reporting a copy', async () => {
    execCommand.mockReturnValue(false)
    term._sel = 'doomed to be refused'
    handler!(key({ ctrlKey: true, key: 'c' }))
    await waitFor(() => expect(notice()?.getAttribute('data-fleet-terminal-copied')).toBe('no'))
    expect(notice()!.textContent!.length).toBeGreaterThan(0)
  })

  it('does not reach the clipboard APIs when the synchronous write succeeded', async () => {
    const writeText = vi.fn()
    vi.stubGlobal('navigator', { ...navigator, clipboard: { writeText } })
    term._sel = 'already on the clipboard'
    handler!(key({ ctrlKey: true, key: 'c' }))
    await waitFor(() => expect(notice()?.getAttribute('data-fleet-terminal-copied')).toBe('yes'))
    expect(writeText).not.toHaveBeenCalled()
  })
})

describe('the empty-selection Ctrl+C is not silent', () => {
  it('teaches Shift-drag when the agent owns the mouse — and still interrupts', async () => {
    agentTakesTheMouse()
    term._sel = ''
    expect(handler!(key({ ctrlKey: true, key: 'c' }))).toBe(true)
    await waitFor(() => expect(notice()?.textContent).toContain('Shift'))
  })

  it('stays the designed silence when the reader owns the mouse', () => {
    term._sel = ''
    expect(handler!(key({ ctrlKey: true, key: 'c' }))).toBe(true)
    expect(notice()).toBeNull()
  })
})

describe('right-click with a selection IS the copy', () => {
  const rightDown = () =>
    host().dispatchEvent(new MouseEvent('mousedown', { bubbles: true, cancelable: true, button: 2 }))
  const contextMenu = () => {
    const ev = new MouseEvent('contextmenu', { bubbles: true, cancelable: true, button: 2 })
    host().dispatchEvent(ev)
    return ev
  }

  it('captures the selection on the way down and copies it, even after the emulator cleared it', async () => {
    term._sel = 'selected before the right-click'
    rightDown()
    // The real emulator clears the selection on mousedown — the reader measured
    // exactly that. The copy must survive the clearing.
    term._sel = ''
    const ev = contextMenu()
    expect(ev.defaultPrevented).toBe(true)
    await waitFor(() => expect(notice()?.getAttribute('data-fleet-terminal-copied')).toBe('yes'))
    expect(notice()?.textContent).toContain('31')
  })

  it('copies the still-live selection when the emulator did not clear it', async () => {
    term._sel = 'still here'
    const ev = contextMenu()
    expect(ev.defaultPrevented).toBe(true)
    await waitFor(() => expect(notice()?.getAttribute('data-fleet-terminal-copied')).toBe('yes'))
  })

  it('leaves the browser menu completely alone when nothing is selected', () => {
    term._sel = ''
    const ev = contextMenu()
    expect(ev.defaultPrevented).toBe(false)
    expect(notice()).toBeNull()
  })

  it('does not copy on an ordinary left-click', async () => {
    host().dispatchEvent(new MouseEvent('mousedown', { bubbles: true, cancelable: true, button: 0 }))
    term._sel = ''
    const ev = contextMenu()
    expect(ev.defaultPrevented).toBe(false)
  })
})

describe('the copy event stays as the browser-driven safety net', () => {
  it('hands the terminal selection to the browser and says so', async () => {
    term._sel = 'exactly this'
    const { ev, written } = fireCopy()
    expect(written['text/plain']).toBe('exactly this')
    expect(ev.defaultPrevented).toBe(true)
    await waitFor(() => expect(notice()?.getAttribute('data-fleet-terminal-copied')).toBe('yes'))
    expect(notice()?.textContent).toContain('12')
  })

  it('ignores a copy event when the terminal has nothing selected', () => {
    term._sel = ''
    const { ev, written } = fireCopy()
    // Somebody else on the page owns that copy — taking it would replace their
    // clipboard content with nothing.
    expect(written['text/plain']).toBeUndefined()
    expect(ev.defaultPrevented).toBe(false)
  })
})
