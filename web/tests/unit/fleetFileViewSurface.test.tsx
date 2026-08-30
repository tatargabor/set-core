/**
 * What the file view SAYS — the half no endpoint test can reach.
 *
 * The server tests prove that a refusal is a refusal and that a stale write is
 * rejected. None of that is worth anything if the panel renders an empty editor
 * for a file it could not read, or drops an edit without asking: those are the
 * failures that look like success, and they live here.
 *
 * Monaco is mocked, deliberately and narrowly. What is under test is the
 * panel's own behaviour — which sentence is on screen, what happens to an unsaved
 * edit, what reaches storage — and none of that is Monaco's. What IS Monaco's,
 * the jump to a line, is asserted through the editor handle the panel drives, so
 * the test measures the panel's call rather than the emulator's scrolling.
 */
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react'

/** Every call the panel makes into the editor, in order. */
const editorCalls: string[] = []

vi.mock('@monaco-editor/react', () => ({
  loader: { config: () => {} },
  default: ({ value, onChange, onMount, language, path, options }: {
    value: string
    onChange?: (v: string | undefined) => void
    onMount?: (editor: unknown) => void
    language?: string
    path?: string
    options?: { wordWrap?: string }
  }) => {
    // A stand-in for the editor handle, recording what the panel asks of it.
    const handle = {
      revealLineInCenter: (l: number) => editorCalls.push(`reveal:${l}`),
      setPosition: (p: { lineNumber: number }) => editorCalls.push(`position:${p.lineNumber}`),
      createDecorationsCollection: (d: Array<{ range: { startLineNumber: number } }>) => {
        editorCalls.push(`mark:${d[0].range.startLineNumber}`)
        return { set: (n: Array<{ range: { startLineNumber: number } }>) =>
          editorCalls.push(`mark:${n[0].range.startLineNumber}`), clear: () => editorCalls.push('unmark') }
      },
    }
    return (
      <textarea
        data-testid="monaco"
        data-language={language ?? 'none'}
        data-path={path}
        data-wrap={options?.wordWrap ?? 'unset'}
        value={value}
        ref={el => { if (el) onMount?.(handle) }}
        onChange={e => onChange?.(e.target.value)}
      />
    )
  },
}))
vi.mock('../../src/lib/monacoLocal', () => ({ useLocalMonaco: () => ({}) }))

import FleetFileView from '../../src/components/FleetFileView'

const ROOT = '/home/x/proj'

/** One file's content as the endpoint would answer it. */
interface Fake { content: string; identity: string }
/** A file the endpoint types by its BYTES rather than serving as text. */
interface FakeBinary { media_type: string; bytes: number; raw: Uint8Array }

let files: Record<string, Fake | FakeBinary | { status: number; detail: unknown }>
let writes: Array<Record<string, unknown>>
/** Every `root=` the panel asked an endpoint for, in order. */
let rootsAsked: string[]
/** The status map the fake listing answers with — `null` for "nothing to ask". */
let listStatus: Record<string, string> | null
/** Every `ignored=` the panel asked the listing for, in order. */
let ignoredAsked: boolean[]
/** Every Blob the panel built for a renderer, and every URL it released. */
let createdBlobs: Blob[]
let revokedUrls: string[]

function server() {
  return vi.fn((url: string | URL, init?: RequestInit) => {
    const u = String(url)
    const askedRoot = /[?&]root=([^&]+)/.exec(u)?.[1]
    if (askedRoot) rootsAsked.push(decodeURIComponent(askedRoot))
    if (u.includes('/api/fleet/files?')) ignoredAsked.push(u.includes('ignored=true'))
    if (init?.method === 'PUT') {
      const body = JSON.parse(String(init.body)) as Record<string, unknown>
      writes.push(body)
      const known = files[String(body.path)]
      if (known && 'identity' in known && known.identity !== body.identity) {
        return Promise.resolve({
          ok: false, status: 409,
          json: () => Promise.resolve({ detail: 'the file changed on disk since it was read' }),
        } as Response)
      }
      return Promise.resolve({
        ok: true, status: 200,
        json: () => Promise.resolve({ identity: 'after-write', bytes: 1 }),
      } as Response)
    }
    if (u.includes('/files/raw')) {
      const path = decodeURIComponent(u.split('path=')[1] ?? '')
      const entry = files[path]
      if (!entry || !('raw' in entry)) {
        return Promise.resolve({
          ok: false, status: 415,
          json: () => Promise.resolve({ detail: 'not served as bytes' }),
        } as unknown as Response)
      }
      return Promise.resolve({
        ok: true, status: 200,
        blob: () => Promise.resolve(new Blob([entry.raw])),
      } as unknown as Response)
    }
    if (u.includes('/files/content')) {
      const path = decodeURIComponent(u.split('path=')[1] ?? '')
      const entry = files[path]
      if (!entry) {
        return Promise.resolve({ ok: false, status: 404, json: () => Promise.resolve({ detail: 'no such file' }) } as Response)
      }
      if ('status' in entry) {
        return Promise.resolve({ ok: false, status: entry.status, json: () => Promise.resolve({ detail: entry.detail }) } as Response)
      }
      if ('raw' in entry) {
        return Promise.resolve({
          ok: true, status: 200,
          json: () => Promise.resolve({
            path, kind: 'binary', media_type: entry.media_type, bytes: entry.bytes,
          }),
        } as Response)
      }
      return Promise.resolve({
        ok: true, status: 200,
        json: () => Promise.resolve({
          path, kind: 'text', content: entry.content, identity: entry.identity,
          bytes: entry.content.length,
        }),
      } as Response)
    }
    return Promise.resolve({
      ok: true, status: 200,
      json: () => Promise.resolve({
        root: ROOT, source: 'git', files: Object.keys(files), total: Object.keys(files).length,
        cap: 20000, truncated: false,
        ignored: u.includes('ignored=true'),
        status: listStatus,
      }),
    } as Response)
  })
}

beforeEach(() => {
  editorCalls.length = 0
  writes = []
  rootsAsked = []
  ignoredAsked = []
  listStatus = {}
  files = {
    'a.ts': { content: 'one\ntwo\nthree\n', identity: 'id-a' },
    'b.ts': { content: 'other file\n', identity: 'id-b' },
    'empty.ts': { content: '', identity: 'id-empty' },
    'huge.bin': {
      status: 413,
      detail: {
        reason: 'too-large', bytes: 9000000, cap: 2097152,
        message: 'file is 9000000 bytes; this view serves at most 2097152',
      },
    },
    'report.pdf': {
      status: 415,
      detail: {
        reason: 'no-view', media_type: 'application/pdf', bytes: 1258291,
        message: 'application/pdf is not a type this view can show (1258291 bytes)',
      },
    },
    'logo.png': { media_type: 'image/png', bytes: 6, raw: new Uint8Array([1, 2, 3, 4, 5, 6]) },
    'clip.mp4': { media_type: 'video/mp4', bytes: 4, raw: new Uint8Array([9, 9, 9, 9]) },
    'sub/deep/x.ts': { content: 'nested\n', identity: 'id-x' },
  }
  vi.stubGlobal('fetch', server())
  /*
    jsdom has no object-URL factory. Stubbed rather than skipped, because WHICH
    type the panel puts on the Blob is the security decision under test: the
    renderer must be handed the panel's choice, never a type a file's own bytes
    could claim.
  */
  createdBlobs = []
  vi.stubGlobal('URL', Object.assign(Object.create(URL), {
    createObjectURL: (b: Blob) => { createdBlobs.push(b); return `blob:fake-${createdBlobs.length}` },
    revokeObjectURL: (u: string) => { revokedUrls.push(u) },
  }))
  revokedUrls = []
  localStorage.clear()
})
afterEach(() => { cleanup(); vi.unstubAllGlobals() })

const view = (props: Partial<React.ComponentProps<typeof FleetFileView>> = {}) =>
  render(<FleetFileView root={ROOT} projectName="proj" onClose={() => {}} {...props} />)

/** Click one file in the structure. */
async function open(container: HTMLElement, path: string) {
  await waitFor(() => expect(container.querySelector(`[data-fleet-file-node="${path}"]`)).toBeTruthy())
  fireEvent.click(container.querySelector(`[data-fleet-file-node="${path}"]`)!)
}

describe('opening a file at a line', () => {
  it('reveals the line and puts the cursor on it', async () => {
    const { container } = view({ request: { path: 'a.ts', line: 2 } })
    await waitFor(() => expect(screen.getByTestId('monaco')).toBeTruthy())
    await waitFor(() => expect(editorCalls).toContain('reveal:2'))
    expect(editorCalls).toContain('position:2')
    // MARKED as well as scrolled to. Arriving at the right screenful with
    // nothing saying which line was meant is the failure this half guards.
    expect(editorCalls).toContain('mark:2')
  })

  it('opens at the END and SAYS SO when the line is past the last one', async () => {
    // The failure this guards is the quiet one: landing at the top of the file
    // and reporting nothing, which reads as "the reference was right and the
    // line is boring" rather than "that line does not exist".
    const { container } = view({ request: { path: 'a.ts', line: 900 } })
    await waitFor(() => expect(container.querySelector('[data-fleet-file-line-beyond="yes"]')).toBeTruthy())
    expect(container.textContent).toMatch(/past the end/)
    // Still opened, and clamped to a line that exists rather than 900.
    await waitFor(() => expect(editorCalls.some(c => c.startsWith('reveal:'))).toBe(true))
    expect(editorCalls).not.toContain('reveal:900')
  })
})

describe('a file that cannot be shown', () => {
  it('states the reason where the content would be, naming the file and the cap', async () => {
    const { container } = view()
    await open(container, 'huge.bin')
    await waitFor(() => expect(container.querySelector('[data-fleet-file-refused="huge.bin"]')).toBeTruthy())
    expect(container.querySelector('[data-fleet-file-why="too-large"]')).toBeTruthy()
    expect(container.textContent).toMatch(/huge\.bin is too large/)
    expect(container.textContent).toMatch(/8\.6 MB/)
    expect(container.textContent).toMatch(/at most 2\.0 MB/)
    // And NO editor: an empty editor for an unreadable file reads as an empty file.
    expect(screen.queryByTestId('monaco')).toBeNull()
  })

  it('keeps the three reasons APART', async () => {
    /*
      *Too large*, *no view for this type* and *unreadable* send the reader to
      three different places. A panel that collapsed them into one sentence
      would send two of the three to the wrong one — and a large IMAGE refused
      for its size must not be reported as a type with no view, because that
      states a limit the framework does not have.
    */
    const { container } = view()
    await open(container, 'report.pdf')
    await waitFor(() => expect(container.querySelector('[data-fleet-file-why="no-view"]')).toBeTruthy())
    expect(container.textContent).toMatch(/application\/pdf/)
    expect(container.textContent).toMatch(/1\.2 MB/)
    expect(container.textContent).not.toMatch(/too large/)
  })

  it('offers the desktop hand-over for a type it cannot draw, and only then', async () => {
    // AC-42 and AC-52. A PDF is NAMED and handed over; no viewer is embedded.
    const { container } = view()
    await open(container, 'report.pdf')
    await waitFor(() => expect(container.querySelector('[data-fleet-file-handover="report.pdf"]')).toBeTruthy())
    expect(container.querySelector('embed, object, iframe')).toBeNull()

    fireEvent.click(container.querySelector('[data-fleet-file-handover="report.pdf"]')!)
    await waitFor(() => expect(
      container.querySelector('[data-fleet-file-handover-outcome="ok"]')).toBeTruthy())
    const call = (fetch as unknown as ReturnType<typeof vi.fn>).mock.calls
      .find(c => String(c[0]).includes('/api/desktop/open'))
    expect(JSON.parse(String((call![1] as RequestInit).body)))
      .toEqual({ path: `${ROOT}/report.pdf` })

    // And NOT offered where the hand-over is not the answer.
    await open(container, 'huge.bin')
    await waitFor(() => expect(container.querySelector('[data-fleet-file-why="too-large"]')).toBeTruthy())
    expect(container.querySelector('[data-fleet-file-handover]')).toBeNull()
  })

  it('shows an EMPTY file as empty, which is not a failure', async () => {
    const { container } = view()
    await open(container, 'empty.ts')
    await waitFor(() => expect(container.querySelector('[data-fleet-file-empty="yes"]')).toBeTruthy())
    // The editor IS there — the file opened, it simply has nothing in it.
    expect(screen.getByTestId('monaco')).toBeTruthy()
    expect(container.querySelector('[data-fleet-file-refused]')).toBeNull()
  })
})

describe('an unsaved edit', () => {
  it('marks the file, and asks before opening another one', async () => {
    const { container } = view()
    await open(container, 'a.ts')
    await waitFor(() => expect(screen.getByTestId('monaco')).toBeTruthy())
    fireEvent.change(screen.getByTestId('monaco'), { target: { value: 'edited\n' } })
    await waitFor(() => expect(container.querySelector('[data-fleet-file-dirty="yes"]')).toBeTruthy())

    fireEvent.click(container.querySelector('[data-fleet-file-node="b.ts"]')!)
    // ASKS — the other file is not open yet, and the edit is still here.
    await waitFor(() => expect(container.querySelector('[data-fleet-file-ask="b.ts"]')).toBeTruthy())
    expect((screen.getByTestId('monaco') as HTMLTextAreaElement).value).toBe('edited\n')

    fireEvent.click(container.querySelector('[data-fleet-file-ask-keep]')!)
    await waitFor(() => expect(container.querySelector('[data-fleet-file-ask]')).toBeNull())
    expect((screen.getByTestId('monaco') as HTMLTextAreaElement).value).toBe('edited\n')
  })

  it('opens the other file only when the reader says so', async () => {
    const { container } = view()
    await open(container, 'a.ts')
    await waitFor(() => expect(screen.getByTestId('monaco')).toBeTruthy())
    fireEvent.change(screen.getByTestId('monaco'), { target: { value: 'edited\n' } })
    fireEvent.click(container.querySelector('[data-fleet-file-node="b.ts"]')!)
    await waitFor(() => expect(container.querySelector('[data-fleet-file-ask-discard]')).toBeTruthy())
    fireEvent.click(container.querySelector('[data-fleet-file-ask-discard]')!)
    await waitFor(() => expect((screen.getByTestId('monaco') as HTMLTextAreaElement).value).toBe('other file\n'))
  })
})

describe('a save the endpoint refused', () => {
  it('keeps the text, says the file changed, and writes nothing more', async () => {
    const { container } = view()
    await open(container, 'a.ts')
    await waitFor(() => expect(screen.getByTestId('monaco')).toBeTruthy())
    fireEvent.change(screen.getByTestId('monaco'), { target: { value: 'mine\n' } })
    // Somebody else wrote the file while it was open.
    files['a.ts'] = { content: 'theirs\n', identity: 'id-a-changed' }
    fireEvent.click(container.querySelector('[data-fleet-file-save]')!)

    await waitFor(() => expect(container.querySelector('[data-fleet-file-conflict="yes"]')).toBeTruthy())
    expect(container.textContent).toMatch(/nothing was written/)
    expect((screen.getByTestId('monaco') as HTMLTextAreaElement).value).toBe('mine\n')
    expect(writes.length).toBe(1)
  })

  it('replaces the text with what is on disk only on an explicit choice', async () => {
    const { container } = view()
    await open(container, 'a.ts')
    await waitFor(() => expect(screen.getByTestId('monaco')).toBeTruthy())
    fireEvent.change(screen.getByTestId('monaco'), { target: { value: 'mine\n' } })
    files['a.ts'] = { content: 'theirs\n', identity: 'id-a-changed' }
    fireEvent.click(container.querySelector('[data-fleet-file-save]')!)
    await waitFor(() => expect(container.querySelector('[data-fleet-file-reload]')).toBeTruthy())

    // The offer SAYS what it costs before it is taken.
    expect(container.querySelector('[data-fleet-file-reload]')!.textContent)
      .toMatch(/replaces your text/)
    fireEvent.click(container.querySelector('[data-fleet-file-reload]')!)
    await waitFor(() => expect((screen.getByTestId('monaco') as HTMLTextAreaElement).value).toBe('theirs\n'))
  })
})

describe('the confidentiality boundary is persistence, not display', () => {
  it('puts no file content and no path into browser storage', async () => {
    // Same shape as `fleetInstructSurface.test.tsx` uses for a declared focus,
    // and for the same reason: the tempting change is small and looks helpful —
    // remembering the last open file so the panel does not start empty would put
    // a consumer's path, and then their source, into `localStorage`.
    const secret = 'ACME-Ltd-invoice-2026-07.ts'
    files[secret] = { content: 'PARTNER NAME AND AMOUNT', identity: 'id-secret' }
    const { container } = view()
    await open(container, secret)
    await waitFor(() => expect(screen.getByTestId('monaco')).toBeTruthy())
    fireEvent.change(screen.getByTestId('monaco'), { target: { value: 'edited PARTNER NAME' } })

    const dump = JSON.stringify({ ...localStorage })
    expect(dump).not.toContain('PARTNER NAME')
    expect(dump).not.toContain('ACME-Ltd')
    expect(dump).not.toContain(ROOT)
    // …and the check is not vacuous only because the content WAS on screen.
    expect(container.textContent).toContain(secret)
  })
})

describe('the route that does not need the mouse is stated', () => {
  it('names the structure first, and does not promise the ctrl-click', async () => {
    // The panel must not claim what was not measured: while an agent's program
    // holds the mouse, a click belongs to that program. So the sentence offers
    // the structure and says the click MAY go to the agent.
    const { container } = view()
    await waitFor(() => expect(container.textContent).toMatch(/pick a file from the structure/))
    expect(container.textContent).toMatch(/may go to the agent/)
  })
})


/**
 * WHICH CHECKOUT THE PANEL READS — reported 2026-08-26.
 *
 * A worktree agent's relative path names a file in ITS tree. The panel's
 * identity stays the project root — docking, remembering, closing are keyed by
 * it — so the checkout travels on the REQUEST. Two things have to hold, and the
 * second is the one nobody would miss until it was wrong on screen: it must read
 * the worktree, and it must SAY that it is.
 */
describe('a request that names another checkout', () => {
  const WT = '/home/x/proj-wt-mobil'

  it('reads the worktree, not the project root', async () => {
    view({ request: { path: 'a.ts', from: WT } })
    await waitFor(() => expect(screen.getByTestId('monaco')).toBeTruthy())
    // Both the listing and the content come from the worktree.
    expect(rootsAsked.filter(r => r === WT).length).toBeGreaterThan(0)
    expect(rootsAsked.some(r => r === ROOT && rootsAsked.indexOf(WT) < rootsAsked.lastIndexOf(r)))
      .toBe(false)
  })

  it('says which checkout it is reading', async () => {
    const { container } = view({ request: { path: 'a.ts', from: WT } })
    await waitFor(() => expect(container.querySelector(`[data-fleet-file-checkout="${WT}"]`)).toBeTruthy())
    // A panel quietly showing another branch is the same defect as the one this
    // fixes, pointing the other way.
    expect(screen.getByText(/proj-wt-mobil/)).toBeTruthy()
  })

  it('says nothing when it is reading the project itself', async () => {
    const { container } = view({ request: { path: 'a.ts' } })
    await waitFor(() => expect(screen.getByTestId('monaco')).toBeTruthy())
    expect(container.querySelector('[data-fleet-file-checkout]')).toBeNull()
  })

  it('writes back to the checkout it read from', async () => {
    const { container } = view({ request: { path: 'a.ts', from: WT } })
    await waitFor(() => expect(screen.getByTestId('monaco')).toBeTruthy())
    fireEvent.change(screen.getByTestId('monaco'), { target: { value: 'edited\n' } })
    await waitFor(() => expect(container.querySelector('[data-fleet-file-save]')).toBeTruthy())
    fireEvent.click(container.querySelector('[data-fleet-file-save]')!)
    await waitFor(() => expect(writes.length).toBe(1))
    // Saving into the main checkout what was read from the worktree would be a
    // cross-branch write — the worst thing this panel could do.
    expect(writes[0].root).toBe(WT)
  })
})

describe('the five things the reader could not see', () => {
  it('wraps long lines only when asked, and remembers the answer', async () => {
    // Off first, because a wrapped line stops matching its line number and this
    // panel's other job is *open at line N and mark it*.
    const first = view({ request: { path: 'a.ts' } })
    await waitFor(() => expect(screen.getByTestId('monaco').dataset.wrap).toBe('off'))
    fireEvent.click(first.container.querySelector('[data-fleet-file-wrap]')!)
    await waitFor(() => expect(screen.getByTestId('monaco').dataset.wrap).toBe('on'))
    cleanup()

    // A REMOUNT, which is what docking, enlarging and closing all do to this
    // panel. Before the preference was remembered, each of those silently
    // undid the reader's choice.
    view({ request: { path: 'a.ts' } })
    await waitFor(() => expect(screen.getByTestId('monaco').dataset.wrap).toBe('on'))
  })

  it('asks the endpoint for ignored files only when the control is on', async () => {
    const { container } = view()
    await waitFor(() => expect(ignoredAsked).toEqual([false]))
    fireEvent.click(container.querySelector('[data-fleet-file-ignored]')!)
    // The listing is re-fetched — a toggle that changed only the rendering
    // would filter a list that never contained the files in the first place.
    await waitFor(() => expect(ignoredAsked).toEqual([false, true]))
    expect(container.querySelector('[data-fleet-file-ignored]')!
      .getAttribute('data-fleet-file-ignored')).toBe('on')
  })

  it('says that ignored files are being withheld while they are', async () => {
    // The reported defect was not that the files were absent — it was that
    // nothing distinguished their absence from a project without them.
    const { container } = view()
    await waitFor(() => expect(container.querySelector('[data-fleet-file-ignored-hint]')).toBeTruthy())
    fireEvent.click(container.querySelector('[data-fleet-file-ignored]')!)
    await waitFor(() => expect(container.querySelector('[data-fleet-file-ignored-hint]')).toBeNull())
  })

  it('marks a changed file and an untracked one differently', async () => {
    listStatus = { 'a.ts': ' M', 'b.ts': '??' }
    const { container } = view()
    await waitFor(() => expect(container.querySelector('[data-fleet-file-node="a.ts"]')).toBeTruthy())
    expect(container.querySelector('[data-fleet-file-node="a.ts"]')!
      .getAttribute('data-fleet-file-mark')).toBe('changed')
    expect(container.querySelector('[data-fleet-file-node="b.ts"]')!
      .getAttribute('data-fleet-file-mark')).toBe('untracked')
    // A clean file carries no mark at all.
    expect(container.querySelector('[data-fleet-file-node="empty.ts"]')!
      .getAttribute('data-fleet-file-mark')).toBeNull()
  })

  it('marks a COLLAPSED directory that holds a changed file', async () => {
    // The rule that outranks compactness: a layout that hides something creates
    // a place a changed thing can sit while the screen looks settled.
    files = { 'deep/nest/x.ts': { content: 'x\n', identity: 'id-x' } }
    listStatus = { 'deep/nest/x.ts': ' M' }
    const { container } = view()
    await waitFor(() => expect(container.querySelector('[data-fleet-file-node="deep"]')).toBeTruthy())
    // The file's own row is not rendered — its directory is collapsed — and the
    // mark is on the row that IS.
    expect(container.querySelector('[data-fleet-file-node="deep/nest/x.ts"]')).toBeNull()
    expect(container.querySelector('[data-fleet-file-node="deep"]')!
      .getAttribute('data-fleet-file-mark')).toBe('changed')
  })

  it('states that there is no status rather than leaving rows to imply calm', async () => {
    listStatus = null
    const { container } = view()
    await waitFor(() => expect(container.querySelector('[data-fleet-file-nostatus]')).toBeTruthy())
    // And no row claims anything.
    expect(container.querySelector('[data-fleet-file-mark]')).toBeNull()
  })

  it('expands every directory down to the file it opens', async () => {
    // The reported defect: a file opened from a terminal link sits many levels
    // down a collapsed tree, so the active mark was on a row nobody could see.
    files = { 'deep/nest/x.ts': { content: 'x\n', identity: 'id-x' }, 'top.md': { content: 't\n', identity: 'id-t' } }
    const { container } = view({ request: { path: 'deep/nest/x.ts' } })
    await waitFor(() => expect(
      container.querySelector('[data-fleet-file-node="deep/nest/x.ts"]')).toBeTruthy())
    expect(container.querySelector('[data-fleet-file-node-active="yes"]')!
      .getAttribute('data-fleet-file-node')).toBe('deep/nest/x.ts')
  })

  it('does not collapse what the reader opened themselves', async () => {
    files = {
      'deep/nest/x.ts': { content: 'x\n', identity: 'id-x' },
      'other/y.ts': { content: 'y\n', identity: 'id-y' },
    }
    const { container, rerender } = render(
      <FleetFileView root={ROOT} projectName="proj" onClose={() => {}} />)
    await waitFor(() => expect(container.querySelector('[data-fleet-file-node="other"]')).toBeTruthy())
    fireEvent.click(container.querySelector('[data-fleet-file-node="other"]')!)
    await waitFor(() => expect(container.querySelector('[data-fleet-file-node="other/y.ts"]')).toBeTruthy())

    /*
      The file is opened WITHOUT its own branches being expanded first — which
      is the whole point, and what the earlier version of this test got wrong.
      Expanding `deep` and `deep/nest` by hand first left the reveal with
      nothing to add, so its merge never ran and a mutation replacing that
      merge with `new Set(ancestors)` stayed green. Measured, not assumed.
    */
    rerender(<FleetFileView root={ROOT} projectName="proj" onClose={() => {}}
                            request={{ path: 'deep/nest/x.ts' }} />)
    await waitFor(() => expect(container.querySelector('[data-fleet-file-node-active="yes"]')
      ?.getAttribute('data-fleet-file-node')).toBe('deep/nest/x.ts'))

    // Revealing ADDS branches; it never takes away one somebody chose to open.
    expect(container.querySelector('[data-fleet-file-node="other/y.ts"]')).toBeTruthy()
  })
})

/**
 * THE FILE LIST, PUT AWAY — asked for on 2026-08-27.
 *
 * The list is a navigation aid that keeps charging the reader 256 px of the
 * width the content is read in. Hiding it is a layout decision, so it holds for
 * whatever the right-hand side shows, and the divider has to leave with it — a
 * splitter with nothing on one side still drags and still sets a width nobody
 * can see.
 */
describe('hiding the file list', () => {
  const toggle = (c: HTMLElement) => c.querySelector('[data-fleet-file-tree-hidden]')!

  it('takes the list AND its divider away, and gives the width back', async () => {
    const { container } = view({ request: { path: 'a.ts' } })
    await waitFor(() => expect(container.querySelector('[data-fleet-file-tree]')).toBeTruthy())
    expect(container.querySelector('[data-fleet-splitter]')).toBeTruthy()

    fireEvent.click(toggle(container))

    expect(container.querySelector('[data-fleet-file-tree]')).toBeNull()
    expect(container.querySelector('[data-fleet-splitter]')).toBeNull()
    // The content is still there — this hides the list, not the file.
    expect(screen.getByTestId('monaco')).toBeTruthy()
    expect(toggle(container).getAttribute('data-fleet-file-tree-hidden')).toBe('on')
  })

  it('brings it back at the width it had, not at the default', async () => {
    const { container } = view()
    await waitFor(() => expect(container.querySelector('[data-fleet-file-tree]')).toBeTruthy())
    const before = (container.querySelector('[data-fleet-file-tree]') as HTMLElement).style.width

    fireEvent.click(toggle(container))
    fireEvent.click(toggle(container))

    const after = (container.querySelector('[data-fleet-file-tree]') as HTMLElement).style.width
    expect(after).toBe(before)
  })

  it('says the list is hidden where the reader is standing, instead of bare empty', async () => {
    // B-127: hidden + nothing open + no alarm used to render one help line over
    // empty space — read as "too many files broke the panel".
    const { container } = view()
    await waitFor(() => expect(container.querySelector('[data-fleet-file-tree]')).toBeTruthy())
    fireEvent.click(toggle(container))
    expect(container.querySelector('[data-fleet-file-list-hidden]')).toBeTruthy()
  })

  it('un-hides when a request arrives — a reveal against a hidden pane is a silent no-op', async () => {
    // B-128: the reveal expanded ancestors and scrolled a ref that was never
    // mounted, and the panel looked untouched.
    files = { 'deep/nest/x.ts': { content: 'x\n', identity: 'id-x' } }
    const { container, rerender } = render(
      <FleetFileView root={ROOT} projectName="proj" onClose={() => {}} />)
    await waitFor(() => expect(container.querySelector('[data-fleet-file-tree]')).toBeTruthy())
    fireEvent.click(toggle(container))
    expect(container.querySelector('[data-fleet-file-tree]')).toBeNull()

    rerender(<FleetFileView root={ROOT} projectName="proj" onClose={() => {}}
                            request={{ path: 'deep/nest/x.ts' }} />)
    await waitFor(() => expect(container.querySelector('[data-fleet-file-node="deep/nest/x.ts"]'))
      .toBeTruthy())
    expect(toggle(container).getAttribute('data-fleet-file-tree-hidden')).toBe('off')
  })

  it('remembers the answer across the remount that docking and enlarging cause', async () => {
    const first = view()
    await waitFor(() => expect(first.container.querySelector('[data-fleet-file-tree]')).toBeTruthy())
    fireEvent.click(toggle(first.container))
    cleanup()

    const { container } = view()
    await waitFor(() => expect(toggle(container)).toBeTruthy())
    expect(container.querySelector('[data-fleet-file-tree]')).toBeNull()
  })

  /*
    ui-quality's rule, and the only reason this feature needed a test beyond
    "it disappears": every layout that hides something creates a place a broken
    thing can sit while the screen looks fine. Both of the tree's own notices
    live INSIDE the tree.
  */
  it('carries the "no change marks" notice out to the control that hid it', async () => {
    listStatus = null
    const { container } = view()
    await waitFor(() => expect(container.querySelector('[data-fleet-file-nostatus]')).toBeTruthy())

    fireEvent.click(toggle(container))

    expect(container.querySelector('[data-fleet-file-nostatus]')).toBeNull()
    // Colour is the alarm — a reader must not have to hover to learn of it.
    expect(toggle(container).className).toContain('amber')
    // and the reason travels with it.
    expect(toggle(container).getAttribute('title')).toMatch(/change marks|not a git repository/)
  })

  it('says nothing alarming when there was nothing to say', async () => {
    const { container } = view()
    await waitFor(() => expect(container.querySelector('[data-fleet-file-tree]')).toBeTruthy())
    fireEvent.click(toggle(container))
    expect(toggle(container).className).not.toContain('amber')
  })
})

/**
 * A FILE THAT IS NOT TEXT — the arm the panel grew for it.
 *
 * The failure this replaces was a refusal and nothing else: agents produce
 * screenshots constantly and print the path, and the panel could only say *not
 * a text file* about every one of them.
 */
describe('a binary the panel can draw', () => {
  it('renders an image the panel FETCHED, with the type it chose itself', async () => {
    const { container } = view()
    await open(container, 'logo.png')
    await waitFor(() => expect(container.querySelector('[data-fleet-file-shown="logo.png"]')).toBeTruthy())

    const img = container.querySelector('img') as HTMLImageElement
    expect(img).toBeTruthy()
    // Never pointed at the endpoint: the bytes are fetched and wrapped here, so
    // the type that reaches the renderer is the PANEL's choice and not
    // something the file's own bytes could claim.
    expect(img.getAttribute('src')).toMatch(/^blob:/)
    expect(createdBlobs).toHaveLength(1)
    expect(createdBlobs[0].type).toBe('image/png')
    // Scaled to fit rather than to fill — a screenshot is routinely wider than
    // this panel, and an overflowing image costs the reader two scrollbars.
    expect(img.className).toMatch(/object-contain/)

    // No save control: there is no editor behind an image, so a save would
    // either do nothing or write back something nobody edited.
    expect(container.querySelector('[data-fleet-file-save]')).toBeNull()
    expect(screen.queryByTestId('monaco')).toBeNull()
  })

  it('refuses a type the PANEL does not draw, even when the endpoint offered it', async () => {
    /*
      The second gate, and the reason it is a second one rather than the same
      one moved: the server's allow-list and the panel's must BOTH say yes
      before a byte is drawn. Here the endpoint answers `video/mp4` — and
      nothing is fetched, because this panel has no view for it.
    */
    const { container } = view()
    await open(container, 'clip.mp4')
    await waitFor(() => expect(container.querySelector('[data-fleet-file-why="no-view"]')).toBeTruthy())
    expect(container.textContent).toMatch(/video\/mp4/)
    expect(createdBlobs).toHaveLength(0)
    expect((fetch as unknown as ReturnType<typeof vi.fn>).mock.calls
      .some(c => String(c[0]).includes('/files/raw'))).toBe(false)
  })

  it('gives the editor back when the reader opens a text file next', async () => {
    // AC-43 — and the object URL is RELEASED, which is the half nothing on
    // screen would show: an un-revoked object URL keeps the whole file alive in
    // the page for as long as the tab is open.
    const { container } = view()
    await open(container, 'logo.png')
    await waitFor(() => expect(container.querySelector('[data-fleet-file-shown="logo.png"]')).toBeTruthy())

    await open(container, 'a.ts')
    await waitFor(() => expect(screen.getByTestId('monaco')).toBeTruthy())
    expect(container.querySelector('[data-fleet-file-shown]')).toBeNull()
    expect(container.querySelector('img')).toBeNull()
    expect(revokedUrls).toContain('blob:fake-1')

    fireEvent.change(screen.getByTestId('monaco'), { target: { value: 'edited\n' } })
    await waitFor(() => expect(container.querySelector('[data-fleet-file-save]')).toBeTruthy())
  })

  it('puts nothing of the project into browser storage on these paths', async () => {
    // The confidentiality boundary is PERSISTENCE, not display. A path, a media
    // type and a byte count are all consumer domain, and none of them may
    // outlive the page.
    const { container } = view()
    await open(container, 'logo.png')
    await waitFor(() => expect(container.querySelector('[data-fleet-file-shown="logo.png"]')).toBeTruthy())
    await open(container, 'report.pdf')
    await waitFor(() => expect(container.querySelector('[data-fleet-file-why="no-view"]')).toBeTruthy())

    const stored = Object.keys(localStorage).map(k => `${k}=${localStorage.getItem(k)}`).join('|')
    for (const secret of ['logo.png', 'report.pdf', 'image/png', 'application/pdf', ROOT]) {
      expect(stored).not.toContain(secret)
    }
  })
})

/**
 * REVEALING A DIRECTORY — a move in the structure, never a change of what is
 * open. The panel already refuses to lose an unsaved edit, and a reveal that
 * quietly closed a dirty file would be that same loss through a new door.
 */
describe('revealing a directory', () => {
  it('expands it, marks it, and opens nothing', async () => {
    const { container, rerender } = view()
    await waitFor(() => expect(container.querySelector('[data-fleet-file-node="a.ts"]')).toBeTruthy())
    rerender(<FleetFileView root={ROOT} projectName="proj" onClose={() => {}}
                            request={{ path: 'sub', reveal: true }} />)
    await waitFor(() => expect(
      container.querySelector('[data-fleet-file-node-active="yes"]')).toBeTruthy())
    expect(container.querySelector('[data-fleet-file-node-active="yes"]')
      ?.getAttribute('data-fleet-file-node')).toBe('sub')
    expect(screen.queryByTestId('monaco')).toBeNull()
    expect(container.querySelector('[data-fleet-file-refused]')).toBeNull()
  })

  it('SAYS SO when the listing has nothing beneath it', async () => {
    // Never a silent no-op: an activation that appears to do nothing is
    // indistinguishable from a broken control.
    const { container, rerender } = view()
    await waitFor(() => expect(container.querySelector('[data-fleet-file-node="a.ts"]')).toBeTruthy())
    rerender(<FleetFileView root={ROOT} projectName="proj" onClose={() => {}}
                            request={{ path: 'nowhere', reveal: true }} />)
    await waitFor(() => expect(
      container.querySelector('[data-fleet-file-reveal-empty="nowhere"]')).toBeTruthy())
    expect(container.textContent).toMatch(/may be excluding what it holds/)
  })

  it('leaves an unsaved edit and the open file exactly where they were', async () => {
    const { container, rerender } = view()
    await open(container, 'a.ts')
    await waitFor(() => expect(screen.getByTestId('monaco')).toBeTruthy())
    fireEvent.change(screen.getByTestId('monaco'), { target: { value: 'edited\n' } })
    await waitFor(() => expect(container.querySelector('[data-fleet-file-dirty="yes"]')).toBeTruthy())

    rerender(<FleetFileView root={ROOT} projectName="proj" onClose={() => {}}
                            request={{ path: 'sub', reveal: true }} />)
    await waitFor(() => expect(container.querySelector('[data-fleet-file-node="sub"]')).toBeTruthy())

    // No question asked, nothing closed, nothing lost.
    expect(container.querySelector('[data-fleet-file-ask]')).toBeNull()
    expect((screen.getByTestId('monaco') as HTMLTextAreaElement).value).toBe('edited\n')
    expect(container.querySelector('[data-fleet-file-open="a.ts"]')).toBeTruthy()
  })
})

/**
 * THE BOARD'S ⛶, ON THE FILE VIEW (asked for 2026-08-30): full screen is the
 * whole window, past every dock and grid cell — and the panel is the SAME
 * instance, its root escaping to `fixed`, because a page-level overlay would
 * remount the panel and drop an unsaved draft.
 */
describe('full screen', () => {
  it('offers no ⛶ when the page provides no way to go full screen', () => {
    const { container } = view()
    expect(container.querySelector('[data-tile-control="file-fullscreen"]')).toBeNull()
  })

  it('the ⛶ toggles through to the page, and the root escapes to fixed while on', () => {
    const onFullscreen = vi.fn()
    const { container } = view({ fullscreen: false, onFullscreen })
    const btn = container.querySelector('[data-tile-control="file-fullscreen"]')!
    expect(btn).toBeTruthy()
    fireEvent.click(btn)
    expect(onFullscreen).toHaveBeenCalledTimes(1)

    const { container: onScreen } = view({ fullscreen: true, onFullscreen, onMaximise: () => {} })
    expect(onScreen.querySelector('[data-fleet-file-fullscreen="on"]')).toBeTruthy()
    const rootEl = onScreen.querySelector('[data-fleet-file-fullscreen-root="proj"]')!
    expect(rootEl.className).toContain('fixed')
    expect(rootEl.className).toContain('inset-0')
    // maximise and full screen are different controls: maximise grows within
    // the placement, full screen takes the window
    expect(onScreen.querySelector('[data-tile-control="file-max"]')).toBeTruthy()
  })

  it('without fullscreen the root stays a placed panel, not fixed', () => {
    const { container } = view({ fullscreen: false, onFullscreen: () => {} })
    const rootEl = container.querySelector('[data-fleet-file-view="proj"]')!
    expect(rootEl.className).not.toContain('fixed')
    expect(rootEl.className).toContain('h-full')
  })
})
