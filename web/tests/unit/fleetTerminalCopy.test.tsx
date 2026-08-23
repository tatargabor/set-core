/**
 * Copying out of a terminal — B-65, and the third attempt at it.
 *
 * The first two failed in the browser while passing every test, and the shape of
 * the failure is why this file exists. B-60 chose `Ctrl+Shift+C`, which Chrome
 * claims for its own inspector, so the handler never ran. B-64 moved onto
 * `Ctrl+C` and had the panel perform the copy itself — the async clipboard API
 * never answered, and the synchronous one is refused wherever the browser does
 * not consider the document eligible. Both times the tests were green.
 *
 * What redirected it was the reader's observation that **the mouse fails too**:
 * *"ha egér jobb gomb akkor is eltűnik a kijelölés de nem másolja"*. A path that
 * fails for the key and the mouse alike is not a keyboard problem — it is the
 * panel doing work the browser was going to do.
 *
 * So copy now works the way paste was fixed: BY GETTING OUT OF THE WAY. The two
 * properties below are the ones that must survive any rewrite.
 *
 *   1. The selection is NOT cleared while the browser is copying it.
 *   2. The outcome is never silent — either the browser asks us for the data
 *      (which proves the copy) or the fallback runs and announces what it got.
 */
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { cleanup, render, waitFor } from '@testing-library/react'

let handler: ((e: KeyboardEvent) => boolean) | null = null
let term: any = null
let opened: string[] = []

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

const notice = () => document.querySelector('[data-fleet-terminal-copied]')

beforeEach(async () => {
  handler = null; term = null; opened = []
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

describe('the panel gets out of the way', () => {
  it('declines Ctrl+C on a selection and leaves the selection ALONE', () => {
    term._sel = 'the line the reader picked'
    expect(handler!(key({ ctrlKey: true, key: 'c' }))).toBe(false)
    // Clearing it here is what would break the browser's copy: it copies the
    // selection that exists when the event finishes, not the one we saw.
    expect(term.getSelection()).toBe('the line the reader picked')
  })

  it('still interrupts when nothing is selected', () => {
    term._sel = ''
    expect(handler!(key({ ctrlKey: true, key: 'c' }))).toBe(true)
  })
})

describe('the copy event is the proof, not our own call', () => {
  it('hands the terminal selection to the browser and says so', async () => {
    term._sel = 'exactly this'
    const { ev, written } = fireCopy()
    expect(written['text/plain']).toBe('exactly this')
    expect(ev.defaultPrevented).toBe(true)
    await waitFor(() => expect(notice()?.getAttribute('data-fleet-terminal-copied')).toBe('yes'))
    expect(notice()?.textContent).toContain('12')
  })

  it('clears the selection only AFTER the copy, so the interrupt comes back', async () => {
    term._sel = 'exactly this'
    fireCopy()
    // Not yet: the browser is still holding the event.
    expect(term.getSelection()).toBe('exactly this')
    await waitFor(() => expect(term.getSelection()).toBe(''))
    expect(handler!(key({ ctrlKey: true, key: 'c' }))).toBe(true)
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

describe('silence is impossible', () => {
  it('falls back and ANNOUNCES when the browser never asks for the data', async () => {
    vi.useFakeTimers()
    term._sel = 'never copied by the browser'
    handler!(key({ ctrlKey: true, key: 'c' }))
    // Past the 400 ms the browser had, and NO further: the notice hides itself
    // after 2.5 s, so advancing through that would make an announcement that DID
    // happen look like silence — which is the very thing under test here.
    await vi.advanceTimersByTimeAsync(500)
    vi.useRealTimers()
    await waitFor(() => expect(notice()).toBeTruthy())
    // Whatever it says, it SAYS something — that is the property under test.
    expect(notice()!.textContent!.length).toBeGreaterThan(0)
  })

  it('does not run the fallback when the browser did copy', async () => {
    vi.useFakeTimers()
    term._sel = 'copied natively'
    handler!(key({ ctrlKey: true, key: 'c' }))
    fireCopy()
    await vi.advanceTimersByTimeAsync(1000)
    vi.useRealTimers()
    // One announcement, and it is the success one — a fallback firing as well
    // would overwrite it with a failure and teach the reader to distrust both.
    await waitFor(() => expect(notice()?.getAttribute('data-fleet-terminal-copied')).toBe('yes'))
  })
})
