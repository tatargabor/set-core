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

let files: Record<string, Fake | { status: number; detail: string }>
let writes: Array<Record<string, unknown>>
/** Every `root=` the panel asked an endpoint for, in order. */
let rootsAsked: string[]
/** The status map the fake listing answers with — `null` for "nothing to ask". */
let listStatus: Record<string, string> | null
/** Every `ignored=` the panel asked the listing for, in order. */
let ignoredAsked: boolean[]

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
    if (u.includes('/files/content')) {
      const path = decodeURIComponent(u.split('path=')[1] ?? '')
      const entry = files[path]
      if (!entry) {
        return Promise.resolve({ ok: false, status: 404, json: () => Promise.resolve({ detail: 'no such file' }) } as Response)
      }
      if ('status' in entry) {
        return Promise.resolve({ ok: false, status: entry.status, json: () => Promise.resolve({ detail: entry.detail }) } as Response)
      }
      return Promise.resolve({
        ok: true, status: 200,
        json: () => Promise.resolve({ path, content: entry.content, identity: entry.identity, bytes: entry.content.length }),
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
    'huge.bin': { status: 413, detail: 'file is 9000000 bytes; this view serves at most 2097152' },
    'logo.png': { status: 415, detail: 'not a text file' },
  }
  vi.stubGlobal('fetch', server())
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
  it('states the reason where the content would be, naming the file', async () => {
    const { container } = view()
    await open(container, 'huge.bin')
    await waitFor(() => expect(container.querySelector('[data-fleet-file-refused="huge.bin"]')).toBeTruthy())
    expect(container.textContent).toMatch(/huge\.bin cannot be shown/)
    expect(container.textContent).toMatch(/9000000 bytes/)
    // And NO editor: an empty editor for an unreadable file reads as an empty file.
    expect(screen.queryByTestId('monaco')).toBeNull()
  })

  it('says "not a text file" rather than rendering nothing', async () => {
    const { container } = view()
    await open(container, 'logo.png')
    await waitFor(() => expect(container.textContent).toMatch(/not a text file/))
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
