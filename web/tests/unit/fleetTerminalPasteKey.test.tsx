/**
 * The keystroke the panel must DECLINE — B-62.
 *
 * Reported 2026-08-22: *"ctrl-c és ctrl-v nem mukodik most agent terminalban"*.
 * The measurement, with a capture-phase probe on the live fleet screen, is what
 * this file freezes: `Ctrl+V` reached the helper textarea with
 * `defaultPrevented: true` and produced **zero** `paste` events, while
 * `Ctrl+Shift+V` reached it uncancelled and produced one.
 *
 * The cause is the emulator's, and it decides the shape of the fix. xterm 6 maps
 * a plain `Ctrl`+letter to `String.fromCharCode(keyCode - 64)`, so `Ctrl+V`
 * becomes `\x16`; `_keyDown` sends that to the pty and then calls
 * `preventDefault()`, which cancels the browser's own paste before it starts.
 * But `_keyDown` consults the custom handler FIRST and returns immediately when
 * it says `false` — so declining the keystroke is the entire repair, and doing
 * anything else here (reading the clipboard ourselves, writing to the socket)
 * would be a second path to keep in step with the first.
 *
 * `fleetTerminal.test.ts` asserts the DECISION — which keys are a paste request.
 * This file asserts the WIRING, which is where the defect actually lived: the
 * component gave xterm a handler that answered `true` for every key it did not
 * recognise as a copy, and `true` is the answer that lets the cancel happen.
 */
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { cleanup, render, waitFor } from '@testing-library/react'

/** The handler the component hands to the emulator — the subject of this file. */
let handler: ((e: KeyboardEvent) => boolean) | null = null
const opened: string[] = []

vi.mock('@xterm/xterm/css/xterm.css', () => ({}))
vi.mock('@xterm/addon-fit', () => ({ FitAddon: class { fit() { /* geometry is elsewhere */ } } }))
vi.mock('@xterm/xterm', () => ({
  Terminal: class {
    cols = 120
    rows = 40
    open() { opened.push('open') }
    loadAddon() { /* stubbed above */ }
    focus() { /* no keyboard in jsdom */ }
    dispose() { /* nothing to release */ }
    resize() { /* geometry is measured in fleetTerminalReplayGeometry */ }
    write() { /* no bytes in this file */ }
    onData() { return { dispose() { /* no listener */ } } }
    attachCustomKeyEventHandler(fn: (e: KeyboardEvent) => boolean) { handler = fn }
    getSelection() { return '' }
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
  send() { /* nothing is sent in this file */ }
  close() { /* nothing to tear down */ }
}

const key = (over: Partial<KeyboardEvent>) =>
  ({
    type: 'keydown',
    ctrlKey: false,
    shiftKey: false,
    altKey: false,
    metaKey: false,
    key: 'a',
    ...over,
  }) as KeyboardEvent

beforeEach(async () => {
  handler = null
  opened.length = 0
  vi.stubGlobal('WebSocket', FakeSocket)
  vi.stubGlobal('ResizeObserver', class {
    observe() { /* not this file's subject */ }
    disconnect() { /* nothing observed */ }
  })
  render(<FleetTerminal label="t-1" onClose={() => {}} />)
  await waitFor(() => expect(opened).toContain('open'))
  await waitFor(() => expect(handler).toBeTruthy())
})
afterEach(() => { cleanup(); vi.unstubAllGlobals() })

describe('the paste keystroke the emulator would otherwise swallow', () => {
  it('answers FALSE to Ctrl+V, which is what leaves the browser paste alive', () => {
    // `false` here is not "ignore this key" — it is xterm returning from
    // `_keyDown` before `preventDefault()`, which is the only reason the
    // browser's own paste ever runs. `true` would restore the reported defect.
    expect(handler!(key({ ctrlKey: true, key: 'v' }))).toBe(false)
    expect(handler!(key({ shiftKey: true, key: 'Insert' }))).toBe(false)
  })

  it('answers TRUE to the keys that must keep reaching the agent', () => {
    // Ctrl+C stays SIGINT (B-60): these are long-lived sessions and an
    // accidental interrupt costs real work.
    expect(handler!(key({ ctrlKey: true, key: 'c' }))).toBe(true)
    expect(handler!(key({ key: 'a' }))).toBe(true)
    // Ctrl+Shift+V already works untouched — measured on the live terminal.
    expect(handler!(key({ ctrlKey: true, shiftKey: true, key: 'V' }))).toBe(true)
  })

  it('still answers FALSE to the copy key, and for the other reason', () => {
    // Both keys are declined, and a handler that stopped telling them apart
    // would look identical here — so the copy key is asserted alongside, to
    // keep this file from being read as "declining everything is fine".
    expect(handler!(key({ ctrlKey: true, shiftKey: true, key: 'C' }))).toBe(false)
  })
})
