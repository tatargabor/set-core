/**
 * A clipboard image reaching an agent — and, more importantly, a text paste NOT
 * reaching the store.
 *
 * The defect this whole feature came from was a paste path verified with a
 * synthetic event the reader could never produce. So the shape of the risk here
 * is known in advance: a regression that uploads on EVERY paste would satisfy
 * every image-only assertion and quietly send a consumer's screen to a store on
 * each ordinary copy-paste. `4.1` and `4.2` exist for exactly that, and they are
 * the tests to keep if anything here is ever rewritten.
 *
 * `fleetTerminal.test.ts` asserts the decisions in isolation; this file asserts
 * the WIRING — what the panel does to the socket, and what it says on screen.
 */
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { cleanup, render, waitFor, screen } from '@testing-library/react'

let opened: string[] = []
let sent: unknown[] = []
let socket: FakeSocket | null = null

vi.mock('@xterm/xterm/css/xterm.css', () => ({}))
vi.mock('@xterm/addon-fit', () => ({ FitAddon: class { fit() { /* geometry is elsewhere */ } } }))
vi.mock('@xterm/xterm', () => ({
  Terminal: class {
    cols = 120
    rows = 40
    open(el: HTMLElement) { opened.push('open'); this._el = el }
    _el: HTMLElement | null = null
    loadAddon() { /* stubbed */ }
    focus() { /* no keyboard in jsdom */ }
    dispose() { /* nothing to release */ }
    resize() { /* geometry is elsewhere */ }
    write() { /* no bytes here */ }
    onData() { return { dispose() { /* no listener */ } } }
    attachCustomKeyEventHandler() { /* keys are fleetTerminalPasteKey's subject */ }
    getSelection() { return '' }
    clearSelection() { /* no selection here */ }
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
  constructor() { socket = this }
  send(payload: unknown) { sent.push(payload) }
  close() { /* nothing to tear down */ }
}

/** A clipboard payload, in the shape a real `ClipboardEvent` carries. */
function clipboard(opts: { text?: string; image?: Blob }): DataTransfer {
  const types: string[] = []
  const items: unknown[] = []
  if (opts.text !== undefined) {
    types.push('text/plain')
    items.push({ kind: 'string', type: 'text/plain', getAsFile: () => null })
  }
  if (opts.image) {
    types.push(opts.image.type)
    items.push({ kind: 'file', type: opts.image.type, getAsFile: () => opts.image })
  }
  return {
    types,
    items,
    getData: (t: string) => (t === 'text/plain' ? (opts.text ?? '') : ''),
  } as unknown as DataTransfer
}

function firePaste(data: DataTransfer) {
  const host = document.querySelector('[data-fleet-terminal-host]') ?? document.body.firstElementChild!
  const ev = new Event('paste', { bubbles: true, cancelable: true }) as ClipboardEvent
  Object.defineProperty(ev, 'clipboardData', { value: data })
  host.dispatchEvent(ev)
  return ev
}

/*
  `ArrayBuffer.isView`, not `instanceof Uint8Array`. Under jsdom the component's
  typed array comes from a different realm than the test's, so `instanceof` is
  false for a value that IS a Uint8Array — measured here: the byte frame was sent
  and the filter dropped it, which reads exactly like the code never sending.
*/
const bytesSent = () =>
  sent
    .filter(s => ArrayBuffer.isView(s as ArrayBufferView))
    .map(s => new TextDecoder().decode(s as Uint8Array))

let fetchMock: ReturnType<typeof vi.fn>

beforeEach(async () => {
  opened = []; sent = []; socket = null
  fetchMock = vi.fn()
  vi.stubGlobal('fetch', fetchMock)
  vi.stubGlobal('WebSocket', FakeSocket)
  vi.stubGlobal('ResizeObserver', class {
    observe() { /* not this file's subject */ }
    disconnect() { /* nothing observed */ }
  })
  render(<FleetTerminal label="t-1" onClose={() => {}} />)
  await waitFor(() => expect(opened).toContain('open'))
})
afterEach(() => { cleanup(); vi.unstubAllGlobals(); vi.restoreAllMocks() })

const png = () => new Blob([new Uint8Array([0x89, 0x50, 0x4e, 0x47])], { type: 'image/png' })

describe('a text paste is not an image paste', () => {
  it('uploads NOTHING for a text-only paste, and does not swallow the event', async () => {
    const ev = firePaste(clipboard({ text: 'hello' }))
    await Promise.resolve()
    expect(fetchMock).not.toHaveBeenCalled()
    // Not cancelled: the browser's own paste must still run, which is what puts
    // the text into the pty (B-62). Cancelling here would break the half that works.
    expect(ev.defaultPrevented).toBe(false)
  })

  it('treats a paste carrying BOTH text and an image as text', async () => {
    const ev = firePaste(clipboard({ text: 'a copied paragraph', image: png() }))
    await Promise.resolve()
    expect(fetchMock).not.toHaveBeenCalled()
    expect(ev.defaultPrevented).toBe(false)
  })
})

describe('an image paste', () => {
  it('uploads once and types the path with a trailing space and no newline', async () => {
    fetchMock.mockResolvedValue({
      ok: true,
      json: async () => ({ path: '/home/user/.local/share/set-core/paste/abc.png', bytes: 4, type: 'image/png' }),
    })
    const ev = firePaste(clipboard({ image: png() }))
    expect(ev.defaultPrevented).toBe(true)
    await waitFor(() => expect(bytesSent().length).toBe(1))
    expect(fetchMock).toHaveBeenCalledTimes(1)
    expect(fetchMock.mock.calls[0][0]).toBe('/api/fleet/paste')
    const written = bytesSent()[0]
    expect(written).toBe('/home/user/.local/share/set-core/paste/abc.png ')
    // The reader decides when it is sent — so nothing that submits a line.
    expect(written).not.toContain('\n')
    expect(written).not.toContain('\r')
  })

  it('says a refusal, with the framework’s own reason, and writes nothing', async () => {
    fetchMock.mockResolvedValue({
      ok: false,
      status: 413,
      json: async () => ({ detail: 'the image is 99 bytes and the limit is 8 bytes' }),
    })
    firePaste(clipboard({ image: png() }))
    await waitFor(() =>
      expect(document.querySelector('[data-fleet-terminal-pasted="failed"]')).toBeTruthy(),
    )
    expect(screen.getByText(/the limit is 8 bytes/)).toBeTruthy()
    expect(bytesSent()).toEqual([])
  })

  it('says an upload that never answers is not sent, and writes nothing', async () => {
    vi.useFakeTimers()
    fetchMock.mockImplementation(
      (_url: string, init: { signal: AbortSignal }) =>
        new Promise((_res, rej) => {
          init.signal.addEventListener('abort', () => rej(Object.assign(new Error('x'), { name: 'AbortError' })))
        }),
    )
    firePaste(clipboard({ image: png() }))
    await vi.advanceTimersByTimeAsync(20000)
    vi.useRealTimers()
    await waitFor(() =>
      expect(document.querySelector('[data-fleet-terminal-pasted="failed"]')).toBeTruthy(),
    )
    expect(bytesSent()).toEqual([])
  })

  it('shows that a paste is on its way while it is', async () => {
    let release: (v: unknown) => void = () => {}
    fetchMock.mockImplementation(() => new Promise(res => { release = res }))
    firePaste(clipboard({ image: png() }))
    await waitFor(() =>
      expect(document.querySelector('[data-fleet-terminal-pasted="sending"]')).toBeTruthy(),
    )
    release({ ok: true, json: async () => ({ path: '/store/x.png' }) })
    await waitFor(() => expect(bytesSent().length).toBe(1))
    // ...and the notice goes away on success: the typed path is the receipt.
    expect(document.querySelector('[data-fleet-terminal-pasted]')).toBeNull()
  })

  it('keeps nothing about the image in any browser storage', async () => {
    fetchMock.mockResolvedValue({ ok: true, json: async () => ({ path: '/store/secret-shot.png' }) })
    firePaste(clipboard({ image: png() }))
    await waitFor(() => expect(bytesSent().length).toBe(1))
    const stored = [
      ...Object.keys(window.localStorage), ...Object.values(window.localStorage),
      ...Object.keys(window.sessionStorage), ...Object.values(window.sessionStorage),
    ].join('|')
    expect(stored).not.toContain('secret-shot')
    expect(stored).not.toContain('image/png')
    expect(stored).not.toContain('/store/')
  })
})
