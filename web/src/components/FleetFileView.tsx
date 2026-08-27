import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import {
  ChevronDown, ChevronRight, EyeOff, File as FileIcon, Maximize2, Minimize2,
  PanelLeftClose, PanelLeftOpen, RefreshCw, Save, WrapText, X,
} from 'lucide-react'

import { ancestorsOf, buildTree, languageOf, statusKind, type TreeNode } from '../lib/fleetFiles'
import { classifyLoadFailure, type LoadFailure } from '../lib/buildFreshness'
import { DOCK_CONTROLS, IconButton } from './TileControls'
import FleetSplitter from './FleetSplitter'
import type { DockEdge } from '../lib/fleetDocks'

/**
 * The file view — a project's structure on the left, one file on the right.
 *
 * ## What this panel is careful about
 *
 * It is the only surface in this dashboard that WRITES into a project tree, so
 * three of its rules are about not losing somebody's work rather than about
 * showing things:
 *
 *  - **an unsaved edit is never lost silently.** Opening another file while one
 *    is dirty asks first. An edit that disappears is indistinguishable from one
 *    that was never made.
 *  - **a refused save keeps the reader's text.** The endpoint refuses when the
 *    file changed underneath — on this screen the other writer is an agent
 *    running flat out — and the reader's version stays in the editor until they
 *    decide what to do with it.
 *  - **a refusal is stated where the content would be.** Too large, not text,
 *    unreadable: all three are sentences on the panel, never an empty editor,
 *    which reads as an empty file.
 *
 * ## And what it must not keep
 *
 * **Nothing OF THE PROJECT reaches browser storage** — not the content, not the
 * path, not the list. A project's source is the project's own domain
 * (`CLAUDE.md`, External Project Confidentiality), and this panel displays it
 * for as long as it is on screen and no longer.
 *
 * Three booleans DO persist: whether lines are wrapped, whether ignored files
 * are shown, and whether the file list is hidden. The line the rule draws is
 * not "localStorage is forbidden" but
 * "a consumer's domain does not leave the framework's memory", and a flag about
 * this panel is not a consumer's domain. They are stored because the panel is
 * torn down for reasons that have nothing to do with the reader — docking it to
 * an edge, enlarging it, closing it — and losing a setting to each of those is
 * the same complaint already answered for *which file was I reading*.
 */

/**
 * A remembered yes/no about this panel — read and written defensively.
 *
 * Every access is wrapped, because a browser configured to refuse site data
 * THROWS on the accessor rather than returning null. An unguarded read would
 * take the whole panel down over a preference, which is a much worse failure
 * than forgetting one.
 */
function remembered(key: string, fallback: boolean): boolean {
  try {
    const raw = localStorage.getItem(key)
    return raw === null ? fallback : raw === '1'
  } catch { return fallback }
}

function remember(key: string, value: boolean): void {
  try { localStorage.setItem(key, value ? '1' : '0') } catch { /* a preference, not the panel */ }
}

/**
 * The media types THIS PANEL will draw — its own list, not the server's.
 *
 * Deliberately a second list rather than a value read off the response, and the
 * duplication is the design: the type that reaches a renderer is the panel's
 * CHOICE, so a file whose bytes claim to be a document cannot become one by
 * saying so. The server's allow-list still stands; these are two independent
 * gates rather than one moved.
 *
 * The drift risk that usually condemns a second enumeration points the safe way
 * here: both lists must agree before any byte is drawn, so a disagreement makes
 * something fail to render — never something render that should not have.
 *
 * `image/svg+xml` is on neither list. An SVG is text, so it opens in the editor.
 */
const PANEL_RENDERS = new Set([
  'image/png', 'image/jpeg', 'image/gif', 'image/webp', 'image/bmp',
  'image/avif', 'image/tiff', 'image/x-icon', 'image/vnd.microsoft.icon',
])

/** A byte count as a person reads it. Nothing here is persisted anywhere. */
function humanBytes(n: number): string {
  if (n < 1024) return `${n} B`
  if (n < 1024 * 1024) return `${(n / 1024).toFixed(1)} kB`
  return `${(n / (1024 * 1024)).toFixed(1)} MB`
}

const WRAP_KEY = 'set-file-wrap'
const IGNORED_KEY = 'set-file-ignored'
const TREE_HIDDEN_KEY = 'set-file-tree-hidden'

/** What the listing endpoint answers. */
interface Listing {
  root: string
  source: 'git' | 'walk'
  files: string[]
  total: number
  cap: number
  truncated: boolean
  /** Whether the answer includes what the project's ignore rules exclude. */
  ignored?: boolean
  /**
   * Each non-clean path's git code — and `null` when there was NOTHING TO ASK.
   *
   * The two are different answers and the panel must keep them different: `{}`
   * means the status was read and everything is clean, `null` means there is no
   * repository or the read failed. Rendering both as a tree of unmarked rows
   * would report a cleanliness nobody measured, so the `null` case is stated in
   * words in the structure pane rather than left to be inferred from an absence
   * of marks — which is what an absence of marks always looks like.
   */
  status?: Record<string, string> | null
}

/** What the panel is showing, or why it is not. */
type Opened =
  | { kind: 'none' }
  | { kind: 'loading'; path: string }
  | { kind: 'open'; path: string; text: string; identity: string; line?: number; lineBeyondEnd?: boolean }
  /** A binary the panel can DRAW. `url` is an object URL this panel owns. */
  | { kind: 'shown'; path: string; mediaType: string; bytes: number; url: string }
  /**
   * Not shown, and WHY — the three reasons stay apart.
   *
   * *Too large*, *no view for this type* and *unreadable* send the reader to
   * three different places, and a panel that collapsed them into one sentence
   * sends two of the three to the wrong one. In particular a large image is
   * refused for its SIZE, not for its type, and saying otherwise reports a limit
   * the framework does not have.
   */
  | {
      kind: 'refused'
      path: string
      reason: string
      why: 'too-large' | 'no-view' | 'unreadable'
      mediaType?: string
      bytes?: number
      cap?: number
    }

/** Where a save got to. `conflict` keeps the reader's text — see the header. */
type SaveState =
  | { kind: 'idle' }
  | { kind: 'saving' }
  | { kind: 'saved'; at: number }
  | { kind: 'failed'; reason: string }
  | { kind: 'conflict' }

export interface FileRequest {
  path: string
  line?: number
  /**
   * The CHECKOUT the path is relative to, when it is not the project root.
   *
   * A worktree agent's relative path names a file in ITS tree, on ITS branch.
   * Without this the panel would read the project root's copy — which either
   * does not exist (a refusal for a file plainly in front of the agent) or does,
   * and is a different file with the same name, opened silently. The panel's
   * IDENTITY stays the project root, so docking, remembering and closing are
   * unchanged; only what it reads moves.
   */
  from?: string
  /**
   * REVEAL this directory rather than open a file: expand its ancestors, scroll
   * the node into view, mark it, and leave what is open alone.
   *
   * A flag on the request rather than a second request channel, because getting
   * to the panel is the same act either way — open it if it is closed, un-tidy
   * it if it is collapsed. Only what the panel does on arrival differs.
   *
   * `path` then names a DIRECTORY. It is never remembered as the reader's last
   * file: a reveal did not open anything, and reporting it as an opened file
   * would restore a directory path into the editor next time the panel opens.
   */
  reveal?: boolean
}

export default function FleetFileView({ root, projectName, request, initial, onClose, onRequestHandled, onOpened, onDock, dockedEdge, maximised, onMaximise }: {
  /** The project's root — the panel's IDENTITY, and its default checkout. */
  root: string
  projectName: string
  /** A file somebody asked for: the terminal, or a click in another panel. */
  request?: FileRequest | null
  /**
   * Where this project's reader was last time — opened once, when the panel
   * appears, and never again.
   *
   * The panel is torn down and rebuilt for reasons that have nothing to do with
   * the reader: closing it, moving it to an edge, another panel being enlarged.
   * Every one of those looked like "the file view forgot what I was reading",
   * which is what was reported 2026-08-22. A live `request` cannot do this job —
   * it fires whenever it changes, so it would re-open the remembered file over
   * the reader's later navigation.
   */
  initial?: FileRequest | null
  onClose: () => void
  /** Called once a request has been taken up, so it is not re-opened forever. */
  onRequestHandled?: () => void
  /**
   * Which file is on screen now — reported up so that closing and re-opening the
   * panel comes back to it, asked for 2026-08-22: *"files ha bezarom akkor mentse
   * el hol volt hogy ha ujra kinyitom akkor ott legyen"*.
   *
   * Reported rather than remembered here, because the panel stops existing when
   * it is closed and that is exactly when the answer is needed. The caller holds
   * it IN MEMORY — a path is a consumer's own domain, so it may be displayed for
   * as long as this screen is open and persisted nowhere (External Project
   * Confidentiality).
   */
  onOpened?: (file: FileRequest) => void
  /**
   * Put this panel on an edge, or `null` to bring it back into the grid.
   *
   * The same four controls an agent tile carries, from the same list — asked for
   * 2026-08-22: *"nem csak jobb oldalt akarom tartani, hanem ugyanúgy rendezni
   * mint agentek nézetét"*. Before this the panel could only be on the right,
   * and its only other state was closed.
   */
  onDock?: (edge: DockEdge | null) => void
  /** Which edge it is on now, or `null` when it sits in the grid. */
  dockedEdge?: DockEdge | null
  /**
   * Whether this panel currently fills the agent panel — the same act an agent
   * tile calls enlarging, asked for 2026-08-22 (*"files maximize mar van?"*).
   *
   * Offered in BOTH placements, and it means a different act in each — which is
   * why the label says which. In the grid it fills the agent panel and the
   * agents move to the strip. On an edge it resizes the band to the largest the
   * arrangement allows, remembering the size it had so the control is a toggle
   * and not a one-way loss of the width the reader chose.
   *
   * The first build withheld it from a docked band on the reasoning that the
   * band already owns its edge. The reader disagreed, and they were right: an
   * edge is not a size, and 320 px of edge is not *"a teljes képernyő"*.
   */
  maximised?: boolean
  onMaximise?: () => void
}) {
  /*
    WHICH CHECKOUT THIS PANEL IS READING — reported 2026-08-26.

    The panel's identity is the project root; what it READS follows the request,
    because a worktree agent's paths belong to its own tree. It is held in state
    rather than derived from `request` on every render for one reason: the
    request is cleared once it has been handled, and a derived value would then
    snap the panel back to the project root while the reader is still in the
    worktree's file.

    It is also SHOWN in the header. A panel silently reading another branch is
    the same defect as the one this fixes, pointing the other way.
  */
  const [readRoot, setReadRoot] = useState(root)
  useEffect(() => { setReadRoot(root) }, [root])
  useEffect(() => {
    if (request?.from && request.from !== readRoot) setReadRoot(request.from)
  }, [request, readRoot])

  const [listing, setListing] = useState<Listing | null>(null)
  const [listError, setListError] = useState<string | null>(null)
  const [expanded, setExpanded] = useState<Set<string>>(new Set())
  const [opened, setOpened] = useState<Opened>({ kind: 'none' })
  const [text, setText] = useState('')
  const [save, setSave] = useState<SaveState>({ kind: 'idle' })
  const [ask, setAsk] = useState<FileRequest | null>(null)
  /**
   * A DIRECTORY the reader was sent to, or `null`.
   *
   * Kept apart from `opened` on purpose: a reveal is a move in the structure
   * pane and not a change of what is open, so it must not be able to disturb an
   * unsaved edit — the panel already refuses to lose one, and a reveal that
   * quietly closed a dirty file would be that same loss through a new door.
   */
  const [revealed, setRevealed] = useState<string | null>(null)
  const [ready, setReady] = useState(false)
  /** Why the editor never arrived, when it never arrived — B-77. */
  const [editorFailure, setEditorFailure] = useState<LoadFailure | null>(null)
  interface EditorHandle {
    revealLineInCenter(l: number): void
    setPosition(p: { lineNumber: number; column: number }): void
    createDecorationsCollection?(d: unknown[]): { set(d: unknown[]): void; clear(): void }
  }
  const editorRef = useRef<EditorHandle | null>(null)
  const markRef = useRef<{ set(d: unknown[]): void; clear(): void } | null>(null)
  const MonacoRef = useRef<React.ComponentType<Record<string, unknown>> | null>(null)
  const [, forceRender] = useState(0)

  const dirty = opened.kind === 'open' && text !== opened.text

  /*
    Monaco arrives lazily — see `monacoLocal.ts` for why it is never the CDN.

    AND THE ARRIVAL CAN FAIL — B-77. The chunk's filename carries a build hash,
    so a redeploy deletes the one this page knows about: the reader's next click
    asks for a file the server no longer has, the `import()` rejects, and without
    the catch below `ready` stays false and the panel says `loading the editor…`
    for ever. Reported 2026-08-24 with the console open beside it, because the
    console was the only place the failure existed.

    The state it fails into is NOT a guess about why. `classifyLoadFailure` asks
    the server whether this page's entry script is still the one it serves, and
    only that answer licenses telling the reader to reload — see the module's
    own header. Everything else surfaces the underlying error verbatim.
  */
  useEffect(() => {
    let dead = false
    void (async () => {
      try {
        const [{ default: Editor }, { useLocalMonaco }] = await Promise.all([
          import('@monaco-editor/react'),
          import('../lib/monacoLocal'),
        ])
        useLocalMonaco()
        if (dead) return
        MonacoRef.current = Editor as unknown as React.ComponentType<Record<string, unknown>>
        setReady(true)
        forceRender(n => n + 1)
      } catch (err) {
        const failure = await classifyLoadFailure(err)
        if (dead) return
        setEditorFailure(failure)
      }
    })()
    return () => { dead = true }
  }, [])

  /*
    The listing, and a way to ask for it again.

    Found by LOOKING, 2026-08-22: a file created while the panel was open did not
    appear, because the listing is fetched once. On this screen that is not an
    edge case — agents create files continuously, and the whole reason the
    endpoint includes untracked files is that a file written a minute ago is the
    one a reader wants to open. A list that cannot be refreshed makes that
    promise decay the moment the panel is opened.

    A control rather than a poll: the endpoint runs `git ls-files` on a real tree,
    and a panel that re-reads it every few seconds would cost that for a reader
    who is looking at one file.
  */
  const [reloads, setReloads] = useState(0)
  /*
    The two remembered preferences — see `remembered` above for why they persist
    and `WRAP_KEY` / `IGNORED_KEY` for where.

    Wrapping starts OFF, and that is a decision rather than a default inherited
    from Monaco. A wrapped line breaks the correspondence between a row on screen
    and a line NUMBER, and this panel's other job is *open at line N and mark it*
    — the terminal links depend on it. Somebody who asked to go to a line did not
    ask for the ruler to stop matching, so wrapping is something they turn on.
  */
  const [wrap, setWrap] = useState(() => remembered(WRAP_KEY, false))
  const [showIgnored, setShowIgnored] = useState(() => remembered(IGNORED_KEY, false))
  useEffect(() => { remember(WRAP_KEY, wrap) }, [wrap])
  useEffect(() => { remember(IGNORED_KEY, showIgnored) }, [showIgnored])
  /*
    The structure's width — asked for 2026-08-22: *"kellene a file nézet és a
    file lista közötti savot is tudnk húzogatni"*.

    The SAME `FleetSplitter` the project list and the docked bands use, so there
    is one answer to what a divider looks like and how it behaves (drag, arrow
    keys, Home/End). A second implementation would drift from those the first
    time either is touched.

    Held in the component rather than in the stored arrangement: a panel that can
    sit in the grid or on any of four edges has a different sensible width in
    each, and one remembered number would be wrong in three of them. Stated
    rather than silent — if it turns out to want remembering, that is a decision
    with a place to store it, not an oversight.
  */
  const [treeWidth, setTreeWidth] = useState(256)

  /*
    THE FILE LIST, OUT OF THE WAY — asked for on 2026-08-27.

    The tree is a navigation aid. Once a file is open it keeps costing the width
    the content is read in, and on a docked or narrow panel that is most of the
    width there is. Hiding it is a decision about LAYOUT, not about data, so it
    holds for whatever the right-hand side is showing — the editor today, any
    other viewer this panel grows later.

    Kept apart from `treeWidth` rather than folded into it: a list dragged down
    to its minimum is still a list somebody wants, and collapsing by width would
    spend the width they chose. Bringing it back restores exactly that number.

    Remembered, for the reason the other two are: docking, enlarging and closing
    all tear this panel down, and none of them is the reader asking for their
    list back.
  */
  const [treeHidden, setTreeHidden] = useState(() => remembered(TREE_HIDDEN_KEY, false))
  useEffect(() => { remember(TREE_HIDDEN_KEY, treeHidden) }, [treeHidden])
  useEffect(() => {
    let dead = false
    setListing(null)
    setListError(null)
    void fetch(`/api/fleet/files?root=${encodeURIComponent(readRoot)}`
               + (showIgnored ? '&ignored=true' : ''))
      .then(async r => {
        const body = await r.json().catch(() => null)
        if (!r.ok) throw new Error(String(body?.detail ?? `HTTP ${r.status}`))
        return body as Listing
      })
      .then(l => { if (!dead) setListing(l) })
      .catch(e => { if (!dead) setListError(String((e as Error)?.message ?? e)) })
    return () => { dead = true }
  }, [readRoot, reloads, showIgnored])

  /*
    `listing.status` is passed straight through, INCLUDING its absence.

    `undefined`/`null` means the listing had nothing to report — a directory that
    is not a repository, or a status read that failed — and the tree then carries
    no marks. That is indistinguishable from a clean tree by looking at it, which
    is exactly why the pane SAYS so below rather than leaving the reader to infer
    calm from an absence of marks.
  */
  const tree = useMemo(
    () => buildTree(listing?.files ?? [], listing?.status ?? undefined),
    [listing],
  )

  /**
   * The object URL the image view is currently holding, so it can be released.
   *
   * A ref rather than state, because releasing it is cleanup and must happen
   * whatever re-renders: an object URL that is never revoked keeps the whole
   * file alive in the page for as long as the tab is open, and this panel is
   * used to flick through files.
   */
  /**
   * Handing a file the panel cannot draw to the reader's own desktop.
   *
   * The same endpoint the terminal uses, with the same guard: it refuses to
   * hand over anything the desktop would RUN or interpret, and this change
   * widens that list rather than relaxing it. What is offered here is only the
   * case where the hand-over is the answer — a type this panel has no view for.
   */
  const [handOver_outcome, setHandOverOutcome] =
    useState<{ ok: boolean; reason?: string } | null>(null)
  const handOver = useCallback(async (rel: string) => {
    setHandOverOutcome(null)
    try {
      const res = await fetch('/api/desktop/open', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ path: `${readRoot.replace(/\/+$/, '')}/${rel}` }),
      })
      if (!res.ok) {
        const body = await res.json().catch(() => null)
        setHandOverOutcome({ ok: false, reason: String(body?.detail ?? `HTTP ${res.status}`) })
        return
      }
      setHandOverOutcome({ ok: true })
    } catch (e) {
      setHandOverOutcome({ ok: false, reason: String((e as Error)?.message ?? e) })
    }
  }, [readRoot])

  const objectUrl = useRef<string | null>(null)
  const releaseObjectUrl = useCallback(() => {
    if (objectUrl.current) { URL.revokeObjectURL(objectUrl.current); objectUrl.current = null }
  }, [])
  useEffect(() => releaseObjectUrl, [releaseObjectUrl])

  /**
   * Fetch a renderable file's BYTES and draw them — never by pointing an `<img>`
   * at the endpoint.
   *
   * The whole security decision is in this order of operations, and each step
   * matters:
   *
   *  - the response is served as an ATTACHMENT with `nosniff`, so a browser left
   *    to itself renders nothing;
   *  - the media type is checked against this panel's OWN list before anything
   *    is drawn;
   *  - and the `Blob` is constructed WITH THAT TYPE, so the type reaching the
   *    renderer is the panel's choice rather than something the file's bytes
   *    could claim.
   *
   * A local dashboard cannot buy a second origin — the isolation GitHub gets
   * from `raw.githubusercontent.com` is not available — so this is what stands
   * in its place.
   */
  const showBinary = useCallback(async (path: string, mediaType: string, bytes: number) => {
    if (!PANEL_RENDERS.has(mediaType)) {
      setOpened({
        kind: 'refused', path, why: 'no-view', mediaType, bytes,
        reason: `${mediaType} is not a type this panel can show`,
      })
      return
    }
    const r = await fetch(
      `/api/fleet/files/raw?root=${encodeURIComponent(readRoot)}&path=${encodeURIComponent(path)}`)
    if (!r.ok) {
      const body = await r.json().catch(() => null)
      setOpened({
        kind: 'refused', path, why: r.status === 413 ? 'too-large' : 'no-view',
        mediaType, bytes, reason: String(body?.detail ?? `HTTP ${r.status}`),
      })
      return
    }
    const raw = await r.blob()
    const url = URL.createObjectURL(new Blob([raw], { type: mediaType }))
    objectUrl.current = url
    setOpened({ kind: 'shown', path, mediaType, bytes, url })
    // An image counts in the remembered-file behaviour with no special case:
    // the remembered value is a path, so nothing about that mechanism changes.
    onOpened?.({ path })
  }, [readRoot, onOpened])

  const load = useCallback(async (path: string, line?: number) => {
    setOpened({ kind: 'loading', path })
    setSave({ kind: 'idle' })
    // The mark follows the LAST act. Leaving a revealed directory marked while
    // a file opens would put two current positions on one list.
    setRevealed(null)
    // Nothing of the previous file survives into the next one — the editor's
    // text and the image's bytes both. Switching from an image back to a text
    // file must give the editor and its save control back, with no state left.
    releaseObjectUrl()
    setText('')
    setHandOverOutcome(null)
    try {
      const r = await fetch(
        `/api/fleet/files/content?root=${encodeURIComponent(readRoot)}&path=${encodeURIComponent(path)}`)
      const body = await r.json().catch(() => null)
      if (!r.ok) {
        /*
          The endpoint's typed refusal, kept typed.

          `detail` is an object for the two refusals this panel has to tell
          apart, and a plain string everywhere else (an older server, a 404, a
          confinement refusal). Both are handled, because reading only one of
          them would render `[object Object]` at exactly the moment the reader
          needs a reason.
        */
        const detail: unknown = body?.detail
        const typed = detail !== null && typeof detail === 'object'
          ? detail as { reason?: string; message?: string; media_type?: string; bytes?: number; cap?: number }
          : null
        setOpened({
          kind: 'refused',
          path,
          why: typed?.reason === 'too-large' ? 'too-large'
            : typed?.reason === 'no-view' ? 'no-view'
              : r.status === 415 ? 'no-view' : r.status === 413 ? 'too-large' : 'unreadable',
          reason: String(typed?.message ?? detail ?? `HTTP ${r.status}`),
          ...(typed?.media_type ? { mediaType: typed.media_type } : {}),
          ...(typeof typed?.bytes === 'number' ? { bytes: typed.bytes } : {}),
          ...(typeof typed?.cap === 'number' ? { cap: typed.cap } : {}),
        })
        return
      }
      if (body?.kind === 'binary') {
        await showBinary(path, String(body.media_type ?? ''), Number(body.bytes ?? 0))
        return
      }
      const content = String(body.content ?? '')
      // A line past the end is not a failure to open: the file opens, at its
      // end, and the panel SAYS the line was not there. Silently landing at the
      // top would be the same fact reported as calm.
      const lines = content === '' ? 1 : content.split('\n').length
      const beyond = line !== undefined && line > lines
      setOpened({
        kind: 'open', path, text: content, identity: String(body.identity),
        line: line === undefined ? undefined : Math.min(line, lines),
        lineBeyondEnd: beyond,
      })
      setText(content)
      onOpened?.(line === undefined ? { path } : { path, line })
    } catch (e) {
      setOpened({
        kind: 'refused', path, why: 'unreadable',
        reason: String((e as Error)?.message ?? e),
      })
    }
  }, [readRoot, onOpened, releaseObjectUrl, showBinary])

  /* Somebody asked for a file — from the terminal, usually. An unsaved edit
     turns the request into a question rather than an action. */
  useEffect(() => {
    // An empty path means "just open the panel" — the control in the project
    // header. Treating it as a file would produce a refusal for a file nobody
    // asked for, which reads as the panel being broken on arrival.
    if (!request || !request.path) return
    onRequestHandled?.()
    if (request.reveal) {
      // Never a question, whatever is unsaved: a reveal opens nothing, so there
      // is nothing for the reader to lose and nothing to ask them about.
      setRevealed(request.path.replace(/\/+$/, ''))
      return
    }
    if (dirty) { setAsk(request); return }
    void load(request.path, request.line)
    // `dirty` and `load` are deliberately not dependencies: this fires on a NEW
    // request, not every time the reader types a character.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [request])

  /**
   * Go to a line, and MARK it.
   *
   * Both halves, because the scroll alone is not the requirement: a reader who
   * asked for `fleetFiles.ts:120` arrives at a screenful of code with nothing
   * saying which line was meant, and picks the wrong one — the reference was
   * precise and the arrival is not.
   *
   * Revealed twice on purpose. The first call runs while the editor is being
   * mounted, when its height is not yet what it will be, so *centred* comes out
   * as *near the top* — measured 2026-08-22 in the browser: the target line
   * landed under Monaco's sticky-scroll header, which is the one place on the
   * screen it cannot be read. The second call, one frame later, centres it
   * against the real height.
   */
  const goToLine = useCallback((line: number) => {
    const ed = editorRef.current
    if (!ed) return
    ed.revealLineInCenter(line)
    ed.setPosition({ lineNumber: line, column: 1 })
    const decoration = [{
      range: { startLineNumber: line, startColumn: 1, endLineNumber: line, endColumn: 1 },
      options: { isWholeLine: true, className: 'fleet-file-line' },
    }]
    if (markRef.current) markRef.current.set(decoration)
    else markRef.current = ed.createDecorationsCollection?.(decoration) ?? null
    /*
      And again once the editor has its real size.

      Measured in the browser 2026-08-22, twice: at mount and one frame later the
      editor is still the height it was given before the panel's flex layout
      settled, so *centred* lands the target line just above the viewport — with
      Monaco's sticky-scroll header sitting exactly where it would have been. The
      mark was in the DOM and off screen, which is the worst of both: a highlight
      nobody can see.

      A second, later pass is the cheap fix and it is idempotent — revealing a
      line already centred does nothing.
    */
    requestAnimationFrame(() => editorRef.current?.revealLineInCenter(line))
    setTimeout(() => editorRef.current?.revealLineInCenter(line), 250)
  }, [])

  /*
    ON APPEARING, go back to where this project's reader was.

    Guarded by a ref rather than by an empty dependency list, because the effect
    must not fire a second time when the panel re-renders — and must not fire at
    all when the panel is appearing *because* somebody asked for a specific file.
  */
  const restored = useRef(false)
  useEffect(() => {
    if (restored.current) return
    restored.current = true
    if (request?.path || !initial?.path) return
    void load(initial.path, initial.line)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  /* Jump to the line once the editor exists. */
  useEffect(() => {
    if (opened.kind !== 'open' || !editorRef.current) return
    // No line asked for: clear the mark, so a previous file's highlight does not
    // sit on an unrelated line of this one.
    if (opened.line === undefined) { markRef.current?.clear(); return }
    goToLine(opened.line)
  }, [opened, goToLine])

  const openFile = useCallback((path: string) => {
    if (dirty) { setAsk({ path }); return }
    void load(path)
  }, [dirty, load])

  const doSave = useCallback(async () => {
    if (opened.kind !== 'open') return
    setSave({ kind: 'saving' })
    try {
      const r = await fetch('/api/fleet/files/content', {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ root: readRoot, path: opened.path, content: text, identity: opened.identity }),
      })
      const body = await r.json().catch(() => null)
      if (r.status === 409) { setSave({ kind: 'conflict' }); return }
      if (!r.ok) { setSave({ kind: 'failed', reason: String(body?.detail ?? `HTTP ${r.status}`) }); return }
      // The identity of what was WRITTEN, not of what was read: the next save
      // has to be checked against the file as it now is.
      setOpened({ ...opened, text, identity: String(body.identity) })
      setSave({ kind: 'saved', at: Date.now() })
    } catch (e) {
      setSave({ kind: 'failed', reason: String((e as Error)?.message ?? e) })
    }
  }, [opened, readRoot, text])

  const openPath = opened.kind === 'none' ? null : opened.path

  /**
   * WHERE THE READER IS in the structure — the open file, or a revealed
   * directory. One position and one mark, whichever act put them there.
   */
  const markedPath = revealed ?? openPath

  /**
   * A reveal that finds nothing SAYS so — never a silent no-op.
   *
   * The structure pane is built from a listing of FILES, so a directory holding
   * nothing the listing carries has no node to expand or scroll to. A control
   * that appears to do nothing is indistinguishable from a broken one, which is
   * the whole reason this is a stated case rather than an early return.
   *
   * `listing === null` makes NO claim: the listing has not arrived, and saying
   * "nothing here" on the strength of an answer nobody has yet is the shape
   * this panel refuses everywhere else.
   */
  const revealFoundNothing = revealed !== null && listing !== null
    && !listing.files.some(f => f === revealed || f.startsWith(revealed + '/'))

  /*
    HIDING MAY NOT HIDE A FAILURE — `ui-quality.md`'s rule, applied to the
    control that does the hiding.

    Two of the tree's notices are the kind of thing that can sit behind a tidy
    screen: a listing that FAILED, and a listing that carries no change marks at
    all. Both render inside the list, so putting the list away would take them
    with it and leave a panel that looks calm about something it never measured.
    They travel to the toggle instead — colour is the alarm, the label is the
    reason, the same split the terminal control already uses.
  */
  const treeAlarm: string | null = !treeHidden ? null
    : listError != null ? `the files could not be listed: ${listError}`
      : listing != null && listing.status == null
        ? (listing.source === 'walk'
            ? 'not a git repository — nothing in the file list says what is committed'
            : 'the change marks could not be read — the list does not know what changed')
        : null

  /*
    THE STRUCTURE FOLLOWS THE OPEN FILE — reported 2026-08-26:
    *"ha egy filet megnyitok akkor a navigacio a file listaban oda kelllene
    alljon (koveti)"*.

    Marking the active row was never enough on its own. A file opened from a
    terminal link is usually many levels down a tree whose branches are all
    collapsed, so the mark sat on a row that was not rendered at all — the panel
    knew where the reader was and the list did not show it.

    Two rules, and the second is the one that is easy to get wrong:

     - **expand, never collapse.** Ancestors are ADDED to `expanded`; nothing is
       removed. A reveal that tidied the tree would undo branches somebody opened
       on purpose, which is the panel overriding a choice rather than serving one.
     - **`block: 'nearest'` scrolls only if it has to.** Revealing the file the
       reader just clicked in the tree must not yank the list under their cursor.
  */
  const revealRef = useRef<HTMLButtonElement | null>(null)
  useEffect(() => {
    if (!markedPath) return
    // A FILE needs its ancestors open; a DIRECTORY needs its own node open too,
    // which is what makes a reveal show what is inside rather than merely
    // scroll to a closed folder.
    const ancestors = revealed === null
      ? ancestorsOf(markedPath)
      : [...ancestorsOf(markedPath), markedPath]
    if (ancestors.length > 0) {
      setExpanded(prev => {
        const missing = ancestors.filter(a => !prev.has(a))
        if (missing.length === 0) return prev
        const next = new Set(prev)
        missing.forEach(a => next.add(a))
        return next
      })
    }
    // One frame later: the rows the expansion just created do not exist yet.
    const id = requestAnimationFrame(() => {
      revealRef.current?.scrollIntoView({ block: 'nearest' })
    })
    return () => cancelAnimationFrame(id)
  }, [markedPath, revealed])

  return (
    <div className="flex flex-col h-full min-h-0" data-fleet-file-view={projectName}>
      <div className="flex items-center gap-1.5 px-2 py-1 border-b border-surface-line min-w-0">
        <span className="text-xs text-fg-strong shrink-0">files</span>
        <span className="text-xs text-fg-ghost truncate" title={root}>{projectName}</span>
        {/* WHICH CHECKOUT — shown whenever it is not the project's own. A panel
            reading another branch without saying so is the same defect this
            feature exists to fix, pointing the other way: the file is right, the
            reader's belief about which branch it came from is not. */}
        {readRoot !== root && (
          <span
            className="text-xs text-sky-400 shrink-0"
            data-fleet-file-checkout={readRoot}
            title={`Reading ${readRoot} — a worktree, not ${root}`}
          >
            · {readRoot.split('/').filter(Boolean).pop()}
          </span>
        )}
        {openPath && (
          <span className="text-xs text-fg-muted truncate" data-fleet-file-open={openPath}>
            · {openPath}{dirty && <span className="text-amber-400" data-fleet-file-dirty="yes"> ●</span>}
          </span>
        )}
        {/* The cap, where the reader is standing. A list cut to its cap and
            shown as a plain tree reads as the whole project. */}
        {listing?.truncated && (
          <span className="text-xs text-amber-400 shrink-0" data-fleet-file-truncated="yes"
                title={`This project has ${listing.total} files; this view lists the first ${listing.cap}.`}>
            {listing.cap} of {listing.total}
          </span>
        )}
        <span className="ml-auto flex items-center gap-0.5 shrink-0">
          {onDock && (
            /* Four edges, one control each, and the one it is already on is the
               way back into the grid — the same shape the agent tiles use, so a
               control never becomes a dead end. */
            <span className="flex items-center" data-fleet-file-dock={dockedEdge ?? 'grid'}>
              {DOCK_CONTROLS.map(({ edge, icon, where }) => (
                <IconButton
                  key={edge}
                  icon={icon}
                  testId={`file-dock-${edge}`}
                  active={dockedEdge === edge}
                  label={dockedEdge === edge
                    ? `bring the files back into the grid from the ${where}`
                    : `put the files ${where} — the panel takes its space out of the grid`}
                  onClick={() => onDock(dockedEdge === edge ? null : edge)}
                />
              ))}
            </span>
          )}
          {onMaximise && (
            <IconButton
              icon={maximised ? Minimize2 : Maximize2}
              testId="file-max"
              active={maximised}
              mark={{ 'data-fleet-file-maximised': maximised ? 'on' : 'off' }}
              label={maximised
                ? 'back to the size it had — the agents get their room back'
                : 'as large as this placement allows — in the grid the agents move to the strip above; on an edge the band takes the room the layout can spare, never all of it'}
              onClick={onMaximise}
            />
          )}
          {/* Layout, not data: it changes what the panel spends its width on
              and nothing about what it holds. Hence its place beside `wrap`. */}
          <IconButton
            icon={treeHidden ? PanelLeftOpen : PanelLeftClose}
            testId="file-tree-toggle"
            active={treeHidden}
            tone={treeAlarm ? 'amber' : undefined}
            mark={{ 'data-fleet-file-tree-hidden': treeHidden ? 'on' : 'off' }}
            label={treeAlarm
              ? `bring the file list back — ${treeAlarm}`
              : treeHidden
                ? 'bring the file list back'
                : 'hide the file list — whatever is open takes its width'}
            onClick={() => setTreeHidden(v => !v)}
          />
          <IconButton
            icon={WrapText}
            testId="file-wrap"
            active={wrap}
            mark={{ 'data-fleet-file-wrap': wrap ? 'on' : 'off' }}
            label={wrap
              ? 'stop wrapping — a wrapped line no longer matches its line number'
              : 'wrap long lines to the width of the editor'}
            onClick={() => setWrap(w => !w)}
          />
          {/* Ignored files. The label states what is being WITHHELD when it is
              off, because that is the reported defect: a directory of files was
              missing and nothing on the screen distinguished that from a project
              that does not have one. */}
          <IconButton
            icon={EyeOff}
            testId="file-ignored"
            active={showIgnored}
            mark={{ 'data-fleet-file-ignored': showIgnored ? 'on' : 'off' }}
            label={showIgnored
              ? 'hide the files this project ignores'
              : 'show the files this project ignores — they are being withheld now'}
            onClick={() => setShowIgnored(v => !v)}
          />
          <IconButton
            icon={RefreshCw}
            testId="file-refresh"
            mark={{ 'data-fleet-file-refresh': 'yes' }}
            label="list the files again — agents create files while this is open"
            onClick={() => setReloads(n => n + 1)}
          />
          {dirty && (
            <IconButton
              icon={Save}
              tone="amber"
              testId="file-save"
              mark={{ 'data-fleet-file-save': 'yes' }}
              label={save.kind === 'saving' ? 'saving…' : 'save this file'}
              onClick={() => { if (save.kind !== 'saving') void doSave() }}
            />
          )}
          <IconButton
            icon={X}
            testId="file-close"
            mark={{ 'data-fleet-file-close': 'yes' }}
            label="close the file view"
            onClick={onClose}
          />
        </span>
      </div>

      {save.kind === 'conflict' && (
        <div className="px-2 py-1 text-xs text-amber-400 border-b border-surface-line"
             data-fleet-file-conflict="yes">
          the file changed on disk since you opened it — nothing was written, and your text is
          still here.
          <button
            className="ml-2 underline underline-offset-2 hover:text-amber-300"
            data-fleet-file-reload
            onClick={() => { if (opened.kind === 'open') void load(opened.path) }}
          >
            load what is on disk (this replaces your text)
          </button>
        </div>
      )}
      {save.kind === 'failed' && (
        <div className="px-2 py-1 text-xs text-red-400 border-b border-surface-line">
          the save failed: {save.reason}
        </div>
      )}

      {ask && (
        <div className="px-2 py-1 text-xs text-amber-400 border-b border-surface-line"
             data-fleet-file-ask={ask.path}>
          {openPath} has unsaved changes.
          <button className="ml-2 underline underline-offset-2" data-fleet-file-ask-discard
                  onClick={() => { const r = ask; setAsk(null); void load(r.path, r.line) }}>
            open {ask.path} anyway (your changes are lost)
          </button>
          <button className="ml-2 underline underline-offset-2" data-fleet-file-ask-keep
                  onClick={() => setAsk(null)}>
            stay here
          </button>
        </div>
      )}

      <div className="flex-1 min-h-0 flex">
        {/*
          The list and the divider leave TOGETHER. A splitter with nothing on
          one side of it is a handle for resizing a panel that is not there —
          it would still drag, still set `treeWidth`, and report nothing back.
        */}
        {!treeHidden && (<>
          <div className="shrink-0 overflow-auto p-1"
               style={{ width: `${treeWidth}px` }}
               data-fleet-file-tree>
            {listError && <div className="text-xs text-red-400 p-1">the files could not be listed: {listError}</div>}
            {!listError && !listing && <div className="text-xs text-fg-ghost p-1">listing…</div>}
            {listing && listing.files.length === 0 && (
              <div className="text-xs text-fg-ghost p-1">
                {listing.source === 'git'
                  ? 'this repository lists no files'
                  : 'this directory is not a git repository, and the walk found no files'}
              </div>
            )}
            {/*
              A REVEAL THAT FOUND NOTHING, said where the reader is standing.

              The structure is built from a listing of files, so a directory
              with nothing the listing carries has no node — because it is
              empty, or because the listing excludes what is in it. Both are
              worth saying, and neither may be reported as the other: an
              activation that appears to do nothing is indistinguishable from a
              broken control.
            */}
            {revealFoundNothing && (
              <div className="text-xs text-amber-300 p-1 mb-1 border-b border-surface-line"
                   data-fleet-file-reveal-empty={revealed ?? undefined}>
                nothing under {revealed} is in this listing — it may be empty, or the
                listing may be excluding what it holds
              </div>
            )}
            {tree.map(node => (
              <Node key={node.path} node={node} depth={0} openPath={markedPath}
                    activeRef={revealRef}
                    expanded={expanded} onToggle={p => setExpanded(prev => {
                      const next = new Set(prev)
                      if (next.has(p)) next.delete(p); else next.add(p)
                      return next
                    })} onOpen={openFile} />
            ))}
            {/*
              A STATED ABSENCE, not an inferred calm.

              When the listing carries no status map there is nothing to ask — the
              directory is not a repository, or the read failed — and every row
              renders unmarked. Unmarked rows are exactly what a clean project
              looks like, so without this line the panel would report a
              cleanliness it never measured. Same rule as `a gap is not a zero`,
              reaching a tree instead of a number.
            */}
            {listing && listing.status == null && (
              <div className="text-xs text-fg-ghost p-1 mt-1 border-t border-surface-line"
                   data-fleet-file-nostatus={listing.source}>
                {listing.source === 'walk'
                  ? 'not a git repository — nothing here says what is committed'
                  : 'the change marks could not be read — an unmarked row does not mean clean'}
              </div>
            )}
            {/* And the other withheld thing, said where the reader is standing. */}
            {listing && listing.status != null && !showIgnored && (
              <div className="text-xs text-fg-ghost p-1 mt-1"
                   data-fleet-file-ignored-hint="yes">
                files this project ignores are not listed
              </div>
            )}
          </div>

          <FleetSplitter
            axis="x"
            size={treeWidth}
            grows="before"
            min={120}
            max={640}
            label="file list width"
            onDrag={setTreeWidth}
            onCommit={setTreeWidth}
          />
        </>)}

        <div className="flex-1 min-w-0 min-h-0" data-fleet-file-content>
          {opened.kind === 'none' && (
            <div className="p-2 text-xs text-fg-ghost">
              pick a file from the structure.
              {/*
                Ctrl-clicking a path in a terminal is offered, and this says what
                is KNOWN about it rather than promising it: while an agent's own
                program holds the mouse — the terminal marks that with an amber
                pointer icon — a click belongs to that program, and whether it
                still reaches the link was NOT measured. So the structure is
                named first, because it is the route that always works.
              */}
              <span className="block mt-1 text-fg-ghost">
                ctrl-click a path in a terminal to open it here — though while the agent holds the
                mouse (the terminal says so) the click may go to the agent instead.
              </span>
            </div>
          )}
          {opened.kind === 'loading' && <div className="p-2 text-xs text-fg-ghost">opening {opened.path}…</div>}
          {opened.kind === 'refused' && (
            /*
              THE THREE REASONS, KEPT APART.

              A reader told *not a text file* about a file that was merely too
              large goes looking for the wrong problem, and a reader told *too
              large* about a PDF goes looking for a setting that would not help.
              So the sentence names which one fired, and `data-fleet-file-why`
              carries it for anything reading the screen rather than looking.

              The hand-over is offered only where it is the answer: a type this
              panel cannot draw is a type the reader's own desktop probably can.
              For a file that is too large, or unreadable, it is not.
            */
            <div className="p-2 text-xs text-amber-400"
                 data-fleet-file-refused={opened.path}
                 data-fleet-file-why={opened.why}>
              {opened.why === 'too-large' && (
                <>
                  {opened.path} is too large to show
                  {opened.bytes !== undefined && ` — ${humanBytes(opened.bytes)}`}
                  {opened.cap !== undefined && `, and this view serves at most ${humanBytes(opened.cap)}`}
                </>
              )}
              {opened.why === 'no-view' && (
                <>
                  {opened.path} is {opened.mediaType ?? 'a type this panel has no view for'}
                  {opened.bytes !== undefined && `, ${humanBytes(opened.bytes)}`}
                  {' — there is no view for it here.'}
                </>
              )}
              {opened.why === 'unreadable' && (
                <>{opened.path} cannot be read: {opened.reason}</>
              )}
              {opened.why === 'no-view' && (
                <button
                  type="button"
                  className="block mt-1 underline underline-offset-2 hover:text-fg-strong"
                  data-fleet-file-handover={opened.path}
                  onClick={() => { void handOver(opened.path) }}
                >
                  open it with this machine{String.fromCharCode(39)}s own application
                </button>
              )}
              {handOver_outcome && (
                <div className="mt-1 text-fg-muted" data-fleet-file-handover-outcome={handOver_outcome.ok ? 'ok' : 'failed'}>
                  {handOver_outcome.ok
                    ? 'handed to the desktop'
                    : `could not hand it over: ${handOver_outcome.reason}`}
                </div>
              )}
            </div>
          )}
          {opened.kind === 'shown' && (
            /*
              The image, scaled to FIT rather than to fill.

              `object-contain` inside a box that owns the panel's remaining
              space: a screenshot is routinely wider than this panel and taller
              than the viewport, and an image that overflows takes the reader to
              a scrollbar in both directions to see what they clicked on.

              No save control, and that is not an omission — see the header note.
              There is no editor behind this, so a save would either do nothing
              or write back something the reader never edited.
            */
            <div className="h-full w-full flex flex-col min-h-0"
                 data-fleet-file-shown={opened.path}
                 data-fleet-file-media={opened.mediaType}>
              <div className="px-2 py-1 text-xs text-fg-ghost shrink-0">
                {opened.mediaType} · {humanBytes(opened.bytes)}
              </div>
              <div className="flex-1 min-h-0 flex items-center justify-center overflow-hidden p-2">
                <img
                  src={opened.url}
                  alt={opened.path}
                  className="max-w-full max-h-full object-contain"
                />
              </div>
            </div>
          )}
          {opened.kind === 'open' && (
            <>
              {opened.lineBeyondEnd && (
                <div className="px-2 py-1 text-xs text-amber-400" data-fleet-file-line-beyond="yes">
                  the reference named a line past the end of this file — it opens at its end
                </div>
              )}
              {opened.text === '' && !dirty && (
                <div className="px-2 py-1 text-xs text-fg-ghost" data-fleet-file-empty="yes">
                  this file is empty
                </div>
              )}
              {ready && MonacoRef.current ? (
                <MonacoRef.current
                  height="100%"
                  theme="vs-dark"
                  path={opened.path}
                  language={languageOf(opened.path)}
                  value={text}
                  onChange={(v: string | undefined) => setText(v ?? '')}
                  onMount={(editor: unknown) => {
                    editorRef.current = editor as EditorHandle
                    markRef.current = null
                    if (opened.line !== undefined) goToLine(opened.line)
                  }}
                  options={{
                    minimap: { enabled: false },
                    fontSize: 12,
                    scrollBeyondLastLine: false,
                    /* Reported 2026-08-26: a long line ran off the editor with
                       no way to bring it back. Off by default — see `wrap`. */
                    wordWrap: wrap ? 'on' : 'off',
                    /*
                      WITHOUT THIS, Monaco keeps the size it had at mount.

                      Measured in the browser 2026-08-22: the DOM node was 688 px
                      tall while the editor still believed it was the height it
                      was created at, so `revealLineInCenter` centred the target
                      inside a viewport nobody could see — the line landed at the
                      very top of the visible box, under the sticky-scroll header.
                      It reads as "the jump goes to the wrong place", and it is
                      really "the editor does not know how big it is".

                      Every panel here is resizable — docked to four edges,
                      enlarged, and dragged by two splitters — so a layout that is
                      measured once is a layout that is wrong most of the time.
                    */
                    automaticLayout: true,
                  }}
                />
              ) : editorFailure ? (
                /*
                  B-77 — a named failure where the endless `loading…` used to be.

                  The reload control is offered ONLY on the measured case. On an
                  unmeasured one the underlying error is shown instead: a reload
                  button beside an error a reload cannot fix spends the reader's
                  attention and returns them to the same screen.
                */
                <div className="p-2 text-xs text-amber-400" data-fleet-editor-failed={editorFailure.kind}>
                  the editor could not be loaded — {editorFailure.reason}
                  {editorFailure.kind === 'stale' && (
                    <button
                      className="ml-2 underline underline-offset-2 hover:text-amber-300"
                      data-fleet-editor-reload="yes"
                      onClick={() => window.location.reload()}
                    >
                      reload
                    </button>
                  )}
                </div>
              ) : (
                <div className="p-2 text-xs text-fg-ghost">loading the editor…</div>
              )}
            </>
          )}
        </div>
      </div>
    </div>
  )
}

/**
 * What a status code looks like on a row, and what it MEANS in words.
 *
 * One colour per meaning, and the colours are the ones this dashboard already
 * uses for these facts elsewhere: amber is work in progress, emerald is new,
 * ghost is present-but-subordinate. Nothing decorative uses them.
 *
 * The `title` carries git's own code, so summarising into three kinds loses
 * nothing a reader might want — it is a summary on the surface with the exact
 * answer one hover away.
 */
const MARKS: Record<string, { glyph: string; className: string; what: string }> = {
  changed: { glyph: '●', className: 'text-amber-400', what: 'changed since the last commit' },
  untracked: { glyph: '✚', className: 'text-emerald-400', what: 'never committed' },
  ignored: { glyph: '·', className: 'text-fg-ghost', what: 'ignored by this project' },
}

/** One row of the structure. Recursive, because the structure is. */
function Node({ node, depth, openPath, expanded, onToggle, onOpen, activeRef }: {
  node: TreeNode
  depth: number
  openPath: string | null
  expanded: ReadonlySet<string>
  onToggle: (path: string) => void
  onOpen: (path: string) => void
  /** Attached to the OPEN row, so the panel can scroll it into view. */
  activeRef?: React.MutableRefObject<HTMLButtonElement | null>
}) {
  const isOpen = expanded.has(node.path)
  const active = openPath === node.path
  /*
    A file wears its own code; a directory wears a SUMMARY of its subtree.

    The directory case is the one that matters. Every layout that hides
    something creates a place a changed thing can sit while the screen looks
    settled (`ui-quality`), and a collapsed folder is exactly such a place — so
    what is hidden and not committed is marked here, where the reader is
    standing, and not only on the row they cannot see.

    Untracked wins the single glyph when a folder holds both, because "there is
    something new in here" is the fact a reader is least likely to already know.
  */
  const kind = node.dir
    ? (node.below?.untracked ? 'untracked' : node.below?.changed ? 'changed' : undefined)
    : statusKind(node.status)
  const mark = kind ? MARKS[kind] : undefined
  const meaning = mark && (node.dir
    ? `something under here is ${kind === 'untracked' ? 'never committed' : 'changed since the last commit'}`
    : `${node.status} — ${mark.what}`)
  return (
    <>
      <button
        ref={active ? activeRef : undefined}
        className={`flex items-center gap-1 w-full text-left text-xs px-1 py-0.5 rounded truncate ${
          active ? 'bg-surface-raised/60 text-sky-300' : 'text-fg-muted hover:text-fg-strong hover:bg-surface-raised/40'} ${
          node.ignored && !active ? 'opacity-50' : ''}`}
        style={{ paddingLeft: `${depth * 10 + 4}px` }}
        data-fleet-file-node={node.path}
        data-fleet-file-node-active={active ? 'yes' : undefined}
        data-fleet-file-mark={kind}
        data-fleet-file-node-ignored={node.ignored ? 'yes' : undefined}
        onClick={() => (node.dir ? onToggle(node.path) : onOpen(node.path))}
        title={meaning ? `${node.path} — ${meaning}` : node.path}
      >
        {node.dir
          ? (isOpen ? <ChevronDown size={11} aria-hidden /> : <ChevronRight size={11} aria-hidden />)
          : <FileIcon size={11} aria-hidden className="shrink-0 opacity-60" />}
        <span className="truncate">{node.name}</span>
        {mark && (
          <span className={`ml-auto shrink-0 pl-1 ${mark.className}`} aria-hidden>
            {mark.glyph}
          </span>
        )}
      </button>
      {node.dir && isOpen && node.children?.map(child => (
        <Node key={child.path} node={child} depth={depth + 1} openPath={openPath}
              activeRef={activeRef}
              expanded={expanded} onToggle={onToggle} onOpen={onOpen} />
      ))}
    </>
  )
}

/** Re-exported so the panel's caller can name what it is asking for. */
export type { TreeNode }
