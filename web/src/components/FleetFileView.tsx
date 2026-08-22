import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { ChevronDown, ChevronRight, File as FileIcon, RefreshCw, Save, X } from 'lucide-react'

import { buildTree, languageOf, type TreeNode } from '../lib/fleetFiles'
import { IconButton } from './TileControls'

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
 * Nothing reaches browser storage — not the content, not the path, not the list.
 * A project's source is the project's own domain (`CLAUDE.md`, External Project
 * Confidentiality), and this panel displays it for as long as it is on screen
 * and no longer.
 */

/** What the listing endpoint answers. */
interface Listing {
  root: string
  source: 'git' | 'walk'
  files: string[]
  total: number
  cap: number
  truncated: boolean
}

/** What the panel is showing, or why it is not. */
type Opened =
  | { kind: 'none' }
  | { kind: 'loading'; path: string }
  | { kind: 'open'; path: string; text: string; identity: string; line?: number; lineBeyondEnd?: boolean }
  | { kind: 'refused'; path: string; reason: string }

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
}

export default function FleetFileView({ root, projectName, request, onClose, onRequestHandled }: {
  /** The project's root — how every endpoint here identifies the project. */
  root: string
  projectName: string
  /** A file somebody asked for: the terminal, or a click in another panel. */
  request?: FileRequest | null
  onClose: () => void
  /** Called once a request has been taken up, so it is not re-opened forever. */
  onRequestHandled?: () => void
}) {
  const [listing, setListing] = useState<Listing | null>(null)
  const [listError, setListError] = useState<string | null>(null)
  const [expanded, setExpanded] = useState<Set<string>>(new Set())
  const [opened, setOpened] = useState<Opened>({ kind: 'none' })
  const [text, setText] = useState('')
  const [save, setSave] = useState<SaveState>({ kind: 'idle' })
  const [ask, setAsk] = useState<FileRequest | null>(null)
  const [ready, setReady] = useState(false)
  const editorRef = useRef<{ revealLineInCenter(l: number): void; setPosition(p: { lineNumber: number; column: number }): void } | null>(null)
  const MonacoRef = useRef<React.ComponentType<Record<string, unknown>> | null>(null)
  const [, forceRender] = useState(0)

  const dirty = opened.kind === 'open' && text !== opened.text

  /* Monaco arrives lazily — see `monacoLocal.ts` for why it is never the CDN. */
  useEffect(() => {
    let dead = false
    void (async () => {
      const [{ default: Editor }, { useLocalMonaco }] = await Promise.all([
        import('@monaco-editor/react'),
        import('../lib/monacoLocal'),
      ])
      useLocalMonaco()
      if (dead) return
      MonacoRef.current = Editor as unknown as React.ComponentType<Record<string, unknown>>
      setReady(true)
      forceRender(n => n + 1)
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
  useEffect(() => {
    let dead = false
    setListing(null)
    setListError(null)
    void fetch(`/api/fleet/files?root=${encodeURIComponent(root)}`)
      .then(async r => {
        const body = await r.json().catch(() => null)
        if (!r.ok) throw new Error(String(body?.detail ?? `HTTP ${r.status}`))
        return body as Listing
      })
      .then(l => { if (!dead) setListing(l) })
      .catch(e => { if (!dead) setListError(String((e as Error)?.message ?? e)) })
    return () => { dead = true }
  }, [root, reloads])

  const tree = useMemo(() => buildTree(listing?.files ?? []), [listing])

  const load = useCallback(async (path: string, line?: number) => {
    setOpened({ kind: 'loading', path })
    setSave({ kind: 'idle' })
    try {
      const r = await fetch(
        `/api/fleet/files/content?root=${encodeURIComponent(root)}&path=${encodeURIComponent(path)}`)
      const body = await r.json().catch(() => null)
      if (!r.ok) {
        setOpened({ kind: 'refused', path, reason: String(body?.detail ?? `HTTP ${r.status}`) })
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
    } catch (e) {
      setOpened({ kind: 'refused', path, reason: String((e as Error)?.message ?? e) })
    }
  }, [root])

  /* Somebody asked for a file — from the terminal, usually. An unsaved edit
     turns the request into a question rather than an action. */
  useEffect(() => {
    // An empty path means "just open the panel" — the control in the project
    // header. Treating it as a file would produce a refusal for a file nobody
    // asked for, which reads as the panel being broken on arrival.
    if (!request || !request.path) return
    onRequestHandled?.()
    if (dirty) { setAsk(request); return }
    void load(request.path, request.line)
    // `dirty` and `load` are deliberately not dependencies: this fires on a NEW
    // request, not every time the reader types a character.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [request])

  /* Jump to the line once the editor exists. */
  useEffect(() => {
    if (opened.kind !== 'open' || opened.line === undefined || !editorRef.current) return
    editorRef.current.revealLineInCenter(opened.line)
    editorRef.current.setPosition({ lineNumber: opened.line, column: 1 })
  }, [opened])

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
        body: JSON.stringify({ root, path: opened.path, content: text, identity: opened.identity }),
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
  }, [opened, root, text])

  const openPath = opened.kind === 'none' ? null : opened.path

  return (
    <div className="flex flex-col h-full min-h-0" data-fleet-file-view={projectName}>
      <div className="flex items-center gap-1.5 px-2 py-1 border-b border-surface-line min-w-0">
        <span className="text-xs text-fg-strong shrink-0">files</span>
        <span className="text-xs text-fg-ghost truncate" title={root}>{projectName}</span>
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
        <div className="w-64 shrink-0 overflow-auto border-r border-surface-line p-1"
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
          {tree.map(node => (
            <Node key={node.path} node={node} depth={0} openPath={openPath}
                  expanded={expanded} onToggle={p => setExpanded(prev => {
                    const next = new Set(prev)
                    if (next.has(p)) next.delete(p); else next.add(p)
                    return next
                  })} onOpen={openFile} />
          ))}
        </div>

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
            <div className="p-2 text-xs text-amber-400" data-fleet-file-refused={opened.path}>
              {opened.path} cannot be shown: {opened.reason}
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
                    editorRef.current = editor as typeof editorRef.current
                    if (opened.line !== undefined) {
                      editorRef.current?.revealLineInCenter(opened.line)
                      editorRef.current?.setPosition({ lineNumber: opened.line, column: 1 })
                    }
                  }}
                  options={{ minimap: { enabled: false }, fontSize: 12, scrollBeyondLastLine: false }}
                />
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

/** One row of the structure. Recursive, because the structure is. */
function Node({ node, depth, openPath, expanded, onToggle, onOpen }: {
  node: TreeNode
  depth: number
  openPath: string | null
  expanded: ReadonlySet<string>
  onToggle: (path: string) => void
  onOpen: (path: string) => void
}) {
  const isOpen = expanded.has(node.path)
  const active = openPath === node.path
  return (
    <>
      <button
        className={`flex items-center gap-1 w-full text-left text-xs px-1 py-0.5 rounded truncate ${
          active ? 'bg-surface-raised/60 text-sky-300' : 'text-fg-muted hover:text-fg-strong hover:bg-surface-raised/40'}`}
        style={{ paddingLeft: `${depth * 10 + 4}px` }}
        data-fleet-file-node={node.path}
        data-fleet-file-node-active={active ? 'yes' : undefined}
        onClick={() => (node.dir ? onToggle(node.path) : onOpen(node.path))}
        title={node.path}
      >
        {node.dir
          ? (isOpen ? <ChevronDown size={11} aria-hidden /> : <ChevronRight size={11} aria-hidden />)
          : <FileIcon size={11} aria-hidden className="shrink-0 opacity-60" />}
        <span className="truncate">{node.name}</span>
      </button>
      {node.dir && isOpen && node.children?.map(child => (
        <Node key={child.path} node={child} depth={depth + 1} openPath={openPath}
              expanded={expanded} onToggle={onToggle} onOpen={onOpen} />
      ))}
    </>
  )
}

/** Re-exported so the panel's caller can name what it is asking for. */
export type { TreeNode }
