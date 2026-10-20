/**
 * The terminal gives Ctrl+←/→ up to the page in latest mode — and ONLY then
 * (asked for 2026-10-20; see `tabSwitchDirection`). Driven through xterm's
 * custom key handler, the one place the terminal decides whether a keystroke
 * goes to the program: returning `false` is what lets it bubble to the page.
 */
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { cleanup, render, waitFor } from '@testing-library/react'

let handler: ((e: KeyboardEvent) => boolean) | null = null
let opened = false

vi.mock('@xterm/xterm/css/xterm.css', () => ({}))
vi.mock('@xterm/addon-fit', () => ({ FitAddon: class { fit() { /* geometry is elsewhere */ } } }))
vi.mock('@xterm/xterm', () => ({
  Terminal: class {
    cols = 120
    rows = 40
    open(el: HTMLElement) { opened = true; el?.insertAdjacentHTML('beforeend', '<div class="terminal xterm"></div>') }
    loadAddon() { /* stubbed */ }
    focus() { /* no keyboard in jsdom */ }
    dispose() { /* nothing to release */ }
    resize() { /* geometry is elsewhere */ }
    write() { /* output is not this file's subject */ }
    onData() { return { dispose() { /* no listener */ } } }
    attachCustomKeyEventHandler(fn: (e: KeyboardEvent) => boolean) { handler = fn }
    getSelection() { return '' }
    clearSelection() { /* nothing selected */ }
    onSelectionChange() { return { dispose() { /* nothing */ } } }
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

async function mount(release: boolean) {
  const view = render(<FleetTerminal label="t-1" onClose={() => {}} releaseTabKeys={release} />)
  await waitFor(() => expect(opened && handler).toBeTruthy())
  return view
}

beforeEach(() => {
  handler = null
  opened = false
  vi.stubGlobal('WebSocket', FakeSocket)
  vi.stubGlobal('ResizeObserver', class { observe() { /* n/a */ } disconnect() { /* n/a */ } })
})
afterEach(() => { cleanup(); vi.unstubAllGlobals() })

describe('Ctrl+←/→ in a terminal', () => {
  it('is given up to the page in latest mode', async () => {
    await mount(true)
    expect(handler!(key({ ctrlKey: true, key: 'ArrowLeft' }))).toBe(false)
    expect(handler!(key({ ctrlKey: true, key: 'ArrowRight' }))).toBe(false)
  })

  it('stays the program\'s word-jump outside latest mode', async () => {
    await mount(false)
    expect(handler!(key({ ctrlKey: true, key: 'ArrowLeft' }))).toBe(true)
  })

  it('keeps every other arrow combination for the program, even in latest mode', async () => {
    await mount(true)
    expect(handler!(key({ key: 'ArrowLeft' }))).toBe(true)
    expect(handler!(key({ ctrlKey: true, shiftKey: true, key: 'ArrowLeft' }))).toBe(true)
    expect(handler!(key({ altKey: true, key: 'ArrowRight' }))).toBe(true)
  })

  it('follows the prop after mount, although the handler is attached once', async () => {
    const view = await mount(false)
    view.rerender(<FleetTerminal label="t-1" onClose={() => {}} releaseTabKeys />)
    expect(handler!(key({ ctrlKey: true, key: 'ArrowRight' }))).toBe(false)
  })
})
