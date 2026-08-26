/**
 * Ctrl-clicking a path that is NOT this project's — the wiring, not the rule.
 *
 * `fleetFiles.test.ts` decides what counts as an external path. This file
 * asserts what the terminal DOES with one, and it exists because three of those
 * behaviours are invisible to any test of the rule:
 *
 *  - a plain click must stay the terminal's (focus, cursor, selection). A
 *    provider that opened on every click would satisfy every assertion about
 *    which paths are recognised, and take the reader's screen somewhere nobody
 *    asked to go on an ordinary click.
 *  - a refusal has to REACH the screen. The endpoint's guard is worth nothing to
 *    a reader who sees a link that silently does nothing.
 *  - nothing may be asked of the server while the output is merely rendered.
 *    That is the probe this change deliberately does not have, and the only way
 *    to keep it absent is to assert its absence.
 */
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { cleanup, render, waitFor, screen } from '@testing-library/react'

interface Link {
  range: { start: { x: number; y: number }; end: { x: number; y: number } }
  text: string
  activate: (event: MouseEvent) => void
}
interface Provider {
  provideLinks(line: number, cb: (links: Link[] | undefined) => void): void
}

let providers: Provider[] = []
let line = ''
let socket: FakeSocket | null = null

vi.mock('@xterm/xterm/css/xterm.css', () => ({}))
vi.mock('@xterm/addon-fit', () => ({ FitAddon: class { fit() { /* geometry is elsewhere */ } } }))
vi.mock('@xterm/addon-web-links', () => ({ WebLinksAddon: class { /* URLs are elsewhere */ } }))
vi.mock('@xterm/xterm', () => ({
  Terminal: class {
    cols = 120
    rows = 40
    // The one row this terminal has, handed to whatever provider asks.
    buffer = { active: { getLine: () => ({ translateToString: () => line }) } }
    open() { /* no DOM measurement in jsdom */ }
    loadAddon() { /* stubbed */ }
    focus() { /* no keyboard here */ }
    dispose() { /* nothing to release */ }
    resize() { /* geometry is elsewhere */ }
    write() { /* no bytes here */ }
    onData() { return { dispose() { /* no listener */ } } }
    attachCustomKeyEventHandler() { /* keys are elsewhere */ }
    getSelection() { return '' }
    clearSelection() { /* no selection here */ }
    registerLinkProvider(p: Provider) {
      providers.push(p)
      return { dispose() { providers = providers.filter(x => x !== p) } }
    }
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
  send() { /* nothing this file reads */ }
  close() { /* detach only */ }
  attach() {
    this.onmessage?.({ data: JSON.stringify({
      event: 'attached', attached: 't-1', replayed_bytes: 0,
      replay_truncated: false, viewers: 1, rows: 40, cols: 120,
    }) })
  }
}

let fetchMock: ReturnType<typeof vi.fn>

/** The links the registered provider offers for the single row on screen. */
function links(): Link[] {
  const found: Link[] = []
  for (const p of providers) p.provideLinks(1, ls => { if (ls) found.push(...ls) })
  return found
}

function click(link: Link, opts: { ctrl: boolean }) {
  link.activate({ ctrlKey: opts.ctrl, metaKey: false } as MouseEvent)
}

/*
  ATTACH FIRST, and this order is not incidental. The link provider is
  registered by an effect that finds nothing on the first pass — the emulator is
  created asynchronously — and runs again when the phase changes. So a test that
  waited for a provider before attaching would wait forever, which is precisely
  what the running screen does too if that second run is ever removed.
*/
async function mount(props: Record<string, unknown> = {}) {
  render(<FleetTerminal label="t-1" onClose={() => {}} {...props} />)
  await waitFor(() => expect(socket).toBeTruthy())
  socket!.attach()
  await waitFor(() => expect(providers.length).toBeGreaterThan(0))
}

beforeEach(() => {
  providers = []
  socket = null
  line = 'Kész (/tmp/claude-chrome-screenshots-DJPCLm/shot-2.jpg) megnyitva'
  fetchMock = vi.fn().mockResolvedValue({ ok: true, json: async () => ({ opened: true }) })
  vi.stubGlobal('fetch', fetchMock)
  vi.stubGlobal('WebSocket', FakeSocket)
  vi.stubGlobal('ResizeObserver', class {
    observe() { /* not this file's subject */ }
    disconnect() { /* nothing observed */ }
  })
})
afterEach(() => { cleanup(); vi.unstubAllGlobals(); vi.restoreAllMocks() })

describe('an out-of-project path in the output', () => {
  it('is offered as a link even with no project context at all', async () => {
    await mount()
    const found = links()
    expect(found.map(l => l.text)).toContain('(/tmp/claude-chrome-screenshots-DJPCLm/shot-2.jpg)')
  })

  it('hands the path to the desktop on ctrl-click — punctuation stripped', async () => {
    await mount()
    click(links()[0], { ctrl: true })
    await waitFor(() => expect(fetchMock).toHaveBeenCalled())
    const [url, init] = fetchMock.mock.calls[0]
    expect(url).toBe('/api/desktop/open')
    expect(JSON.parse((init as RequestInit).body as string))
      .toEqual({ path: '/tmp/claude-chrome-screenshots-DJPCLm/shot-2.jpg' })
  })

  it('does nothing at all on a plain click', async () => {
    await mount()
    click(links()[0], { ctrl: false })
    await Promise.resolve()
    // The click belongs to the terminal: focus, cursor, selection. Opening here
    // would move the reader's screen on an ordinary click.
    expect(fetchMock).not.toHaveBeenCalled()
  })

  it('asks the server nothing while the output is merely rendered', async () => {
    await mount()
    links()
    await Promise.resolve()
    // No existence probe, deliberately — such a route would answer "is there a
    // file at X" for any path on the machine.
    expect(fetchMock).not.toHaveBeenCalled()
  })

  it('says what happened when the hand-over succeeds', async () => {
    await mount()
    click(links()[0], { ctrl: true })
    await waitFor(() =>
      expect(document.querySelector('[data-fleet-terminal-open-outcome="ok"]')).toBeTruthy(),
    )
    // Said out loud because the window may open on another workspace: an
    // invisible success is indistinguishable from a dead link.
    expect(screen.getByText(/handed to the desktop/)).toBeTruthy()
  })

  it('shows the framework’s own reason when it is refused', async () => {
    fetchMock.mockResolvedValue({
      ok: false,
      status: 400,
      json: async () => ({ detail: 'executable files are not opened' }),
    })
    await mount()
    click(links()[0], { ctrl: true })
    await waitFor(() =>
      expect(document.querySelector('[data-fleet-terminal-open-outcome="failed"]')).toBeTruthy(),
    )
    expect(screen.getByText(/executable files are not opened/)).toBeTruthy()
  })

  it('reports a request that never reached the framework', async () => {
    fetchMock.mockRejectedValue(new Error('network down'))
    await mount()
    click(links()[0], { ctrl: true })
    await waitFor(() =>
      expect(document.querySelector('[data-fleet-terminal-open-outcome="failed"]')).toBeTruthy(),
    )
    expect(screen.getByText(/network down/)).toBeTruthy()
  })
})

describe('when the project IS known', () => {
  const root = '/home/x/proj'

  it('hands over a relative DIRECTORY, resolved against the root', async () => {
    // The second report, 2026-08-26: an agent names the change directory it just
    // finished. No listing ever contains it, so it was plain text.
    line = 'A change kész: openspec/changes/mobil-nezet-reszponziv/ — 4/4 artefaktum'
    await mount({ projectRoot: root, knownFiles: new Set(['src/app.ts']), onOpenFile: vi.fn() })

    const found = links()
    expect(found.map(l => l.text)).toEqual(['openspec/changes/mobil-nezet-reszponziv/'])

    click(found[0], { ctrl: true })
    await waitFor(() => expect(fetchMock).toHaveBeenCalled())
    expect(JSON.parse((fetchMock.mock.calls[0][1] as RequestInit).body as string))
      .toEqual({ path: '/home/x/proj/openspec/changes/mobil-nezet-reszponziv' })
  })

  it('leaves the prose around it alone', async () => {
    // The same line, and the point is what is NOT underlined: one link, not four.
    line = 'A change kész: openspec/changes/x/ és/vagy 24/7 a docs/ alatt'
    await mount({ projectRoot: root, knownFiles: new Set(['src/app.ts']), onOpenFile: vi.fn() })
    expect(links().map(l => l.text)).toEqual(['openspec/changes/x/', 'docs/'])
  })

  it('leaves this project’s own file to the file view, and hands over the other one', async () => {
    line = '/home/x/proj/src/app.ts:12 and /tmp/shot.png'
    const openFile = vi.fn()
    await mount({ projectRoot: root, knownFiles: new Set(['src/app.ts']), onOpenFile: openFile })

    const found = links()
    expect(found.map(l => l.text)).toEqual(['/home/x/proj/src/app.ts:12', '/tmp/shot.png'])

    click(found[0], { ctrl: true })
    expect(openFile).toHaveBeenCalledWith({ path: 'src/app.ts', line: 12 })
    expect(fetchMock).not.toHaveBeenCalled()

    click(found[1], { ctrl: true })
    await waitFor(() => expect(fetchMock).toHaveBeenCalledTimes(1))
    expect(JSON.parse((fetchMock.mock.calls[0][1] as RequestInit).body as string))
      .toEqual({ path: '/tmp/shot.png' })
  })
})
