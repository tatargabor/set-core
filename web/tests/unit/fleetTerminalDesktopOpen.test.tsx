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
    /*
      The stub HONOURS the trim flag, because that flag is where a real defect
      lived: a row read trimmed produces indices relative to the trimmed string,
      while xterm's link range is a column in the real row. A stub that ignores
      the argument measures a row with no indent — which is not the row the
      product ever sees, since the runtime frames its output with one.
    */
    buffer = { active: { getLine: () => ({
      translateToString: (trim?: boolean) => (trim ? line.trim() : line),
    }) } }
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

  it('REVEALS a relative directory in the panel instead of launching a file manager', async () => {
    // The second report, 2026-08-26, and its answer has moved: an agent names
    // the change directory it just finished, and opening a desktop file manager
    // over the dashboard the reader is looking at is not what they asked for.
    // Measured over 30 transcripts: 431 directory tokens went that way, 209 of
    // them under a registered project root.
    line = 'A change kész: openspec/changes/mobil-nezet-reszponziv/ — 4/4 artefaktum'
    const reveal = vi.fn()
    await mount({
      projectRoot: root, knownFiles: new Set(['src/app.ts']),
      onOpenFile: vi.fn(), onReveal: reveal,
    })

    const found = links()
    expect(found.map(l => l.text)).toEqual(['openspec/changes/mobil-nezet-reszponziv/'])

    click(found[0], { ctrl: true })
    expect(reveal).toHaveBeenCalledWith('openspec/changes/mobil-nezet-reszponziv', root)
    expect(fetchMock).not.toHaveBeenCalled()
  })

  it('reveals a worktree agent\'s directory in ITS OWN checkout', async () => {
    // The live report, 2026-08-26: the dashboard resolved against the project
    // root and answered "no such file or directory" for a directory the agent
    // was plainly looking at, one checkout over. The base is still the worktree
    // — only the destination changed.
    line = '4 file(s): openspec/changes/mobil-nezet-reszponziv/'
    const reveal = vi.fn()
    await mount({
      projectRoot: root,
      agentCwd: '/home/x/proj-wt-mobil',
      knownFiles: new Set(['src/app.ts']),
      onOpenFile: vi.fn(),
      onReveal: reveal,
    })

    click(links()[0], { ctrl: true })
    expect(reveal).toHaveBeenCalledWith(
      'openspec/changes/mobil-nezet-reszponziv', '/home/x/proj-wt-mobil')
  })

  it('still hands a directory under NO known checkout to the desktop', async () => {
    // AC-27. What the desktop keeps is exactly what the framework may not read,
    // and this change widens what it may read without touching that boundary.
    line = 'kimenet: /tmp/run-4/artifacts/'
    const reveal = vi.fn()
    await mount({
      projectRoot: root, knownFiles: new Set(['src/app.ts']),
      onOpenFile: vi.fn(), onReveal: reveal,
    })

    click(links()[0], { ctrl: true })
    await waitFor(() => expect(fetchMock).toHaveBeenCalled())
    expect(JSON.parse((fetchMock.mock.calls[0][1] as RequestInit).body as string))
      .toEqual({ path: '/tmp/run-4/artifacts' })
    expect(reveal).not.toHaveBeenCalled()
  })

  it('opens a file of ANOTHER checkout in the panel, naming that checkout', async () => {
    // AC-15. A worktree agent prints an absolute path into the main checkout.
    // The framework may read it, so the framework opens it — measured: 125
    // distinct text files under a registered root were handed to the desktop
    // instead, where the reading guard on the server would have served them all.
    line = 'lásd /home/x/proj/src/app.ts:12'
    const openFile = vi.fn()
    await mount({
      projectRoot: root,
      agentCwd: '/home/x/proj-wt-mobil',
      knownFiles: new Set(['src/app.ts']),
      checkouts: [root, '/home/x/proj-wt-mobil'],
      onOpenFile: openFile,
    })

    click(links()[0], { ctrl: true })
    expect(openFile).toHaveBeenCalledWith({ path: 'src/app.ts', line: 12 }, root)
    expect(fetchMock).not.toHaveBeenCalled()
  })

  it('draws NOTHING on a low-confidence token, and still activates it', async () => {
    // AC-4 and AC-47 together: the underline is what the tier suppresses, and
    // the modifier is what keeps the capability. 1 464 measured occurrences of
    // an underline that answers "no such file or directory" is what this is for.
    line = 'futtasd: /opsx:ff és nézd meg a /tmp könyvtárat'
    await mount({ projectRoot: root, knownFiles: new Set(['src/app.ts']), onOpenFile: vi.fn() })

    const found = links()
    expect(found.map(l => l.text)).toEqual(['/tmp'])
    expect(found[0].decorations).toEqual({ underline: false, pointerCursor: false })

    click(found[0], { ctrl: true })
    await waitFor(() => expect(fetchMock).toHaveBeenCalled())
    expect(JSON.parse((fetchMock.mock.calls[0][1] as RequestInit).body as string))
      .toEqual({ path: '/tmp' })
  })

  it('puts the link on the REAL columns of an indented row', async () => {
    /*
      The runtime frames an agent's output, so the row an agent's path arrives on
      is indented. A scan of the trimmed row produces indices relative to the
      trimmed string, and xterm's range is a column in the real row — so the
      underline lands beside the path and a click on the path misses the link.

      Found by looking at the live screen. Every test before this one used a stub
      that ignored the trim flag, so all of them measured a row with no indent.
    */
    const indent = '     '
    line = `${indent}wrote src/app.ts today`
    await mount({ projectRoot: root, knownFiles: new Set(['src/app.ts']), onOpenFile: vi.fn() })

    const found = links()
    expect(found.map(l => l.text)).toEqual(['src/app.ts'])
    // 1-based, and it must point at where the token really is.
    expect(found[0].range.start.x).toBe(line.indexOf('src/app.ts') + 1)
    expect(found[0].range.end.x).toBe(line.indexOf('src/app.ts') + 'src/app.ts'.length)
  })

  it('does nothing on a plain click, whatever KIND of reference it is', async () => {
    /*
      The gesture is one act for four destinations, and the refusal has to hold
      for all four. A reader clicks in a terminal to focus it, to place a cursor,
      to select — and a provider that opened on every click would satisfy every
      assertion about which paths are recognised while taking the screen
      somewhere nobody asked to go.

      Checked per KIND rather than once, because each kind is a separate branch
      of the same handler and three of them are new here.
    */
    const cases: Array<[string, string]> = [
      ['a file', 'wrote src/app.ts'],
      ['a directory', 'kész: openspec/changes/a/'],
      ['a desktop path', 'kimenet /tmp/run-4/shot.png'],
      ['a low-confidence path', 'nézd a /tmp könyvtárat'],
      ['a choice', 'lásd lib/util.ts'],
    ]
    for (const [what, row] of cases) {
      cleanup()
      providers = []
      socket = null
      line = row
      const openFile = vi.fn()
      const reveal = vi.fn()
      await mount({
        projectRoot: root,
        knownFiles: new Set(['src/app.ts', 'openspec/changes/a/spec.md',
                             'src/lib/util.ts', 'test/lib/util.ts']),
        onOpenFile: openFile, onReveal: reveal,
      })
      const found = links()
      expect(found.length, `${what}: nothing was recognised, so the click proves nothing`)
        .toBeGreaterThan(0)
      click(found[0], { ctrl: false })
      expect(openFile, what).not.toHaveBeenCalled()
      expect(reveal, what).not.toHaveBeenCalled()
      expect(fetchMock, what).not.toHaveBeenCalled()
      expect(document.querySelector('[data-fleet-terminal-choice]'), what).toBeNull()
    }
  })

  it('offers the matches when a token suffixes several files, and opens none', async () => {
    // AC-9. Never a guess and never a discard — the reader chooses.
    line = 'lásd lib/util.ts'
    const openFile = vi.fn()
    await mount({
      projectRoot: root,
      knownFiles: new Set(['src/lib/util.ts', 'test/lib/util.ts']),
      onOpenFile: openFile,
    })

    click(links()[0], { ctrl: true })
    expect(openFile).not.toHaveBeenCalled()
    const offered = await screen.findAllByRole('button', { name: /lib\/util\.ts/ })
    expect(offered.map(b => b.textContent)).toEqual(['src/lib/util.ts', 'test/lib/util.ts'])

    offered[1].click()
    expect(openFile).toHaveBeenCalledWith({ path: 'test/lib/util.ts' }, root)
  })

  it('opens a worktree agent\'s FILE in the file view, naming the worktree', async () => {
    // Asked for 2026-08-26: what is inside the project and the internal editor
    // can open, opens there. The listing handed in is the WORKTREE's, so the
    // panel is told which checkout to read — not left to assume the main one.
    line = 'wrote src/app.ts'
    const openFile = vi.fn()
    await mount({
      projectRoot: root,
      agentCwd: '/home/x/proj-wt-mobil',
      knownFiles: new Set(['src/app.ts']),
      onOpenFile: openFile,
    })

    click(links()[0], { ctrl: true })
    expect(openFile).toHaveBeenCalledWith({ path: 'src/app.ts' }, '/home/x/proj-wt-mobil')
    expect(fetchMock).not.toHaveBeenCalled()
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
    expect(openFile).toHaveBeenCalledWith({ path: 'src/app.ts', line: 12 }, root)
    expect(fetchMock).not.toHaveBeenCalled()

    click(found[1], { ctrl: true })
    await waitFor(() => expect(fetchMock).toHaveBeenCalledTimes(1))
    expect(JSON.parse((fetchMock.mock.calls[0][1] as RequestInit).body as string))
      .toEqual({ path: '/tmp/shot.png' })
  })
})
