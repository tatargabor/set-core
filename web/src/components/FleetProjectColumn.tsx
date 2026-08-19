import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import type { KeyboardEvent as ReactKeyboardEvent, PointerEvent as ReactPointerEvent, RefObject } from 'react'
import type { FleetProject, FleetResponse } from '../lib/fleetTypes'
import {
  type FleetArrangement,
  type FleetGroup,
  type Target,
  arrangedNames,
  assign,
  createGroup,
  emptyArrangement,
  forgetMissing,
  fromResponse,
  moveGroup,
  moveParked,
  moveProject,
  moveUngrouped,
  orphans as findOrphans,
  removeGroup,
  seedCandidates,
  setCollapsed,
  toPutBody,
} from '../lib/fleetLayout'
import {
  type AttentionProject,
  type Tally,
  EMPTY_TALLY,
  UNKNOWN,
  WAITING,
  firstAwaiting,
  firstMatching,
  firstWith,
  hasConflict,
  tallyOf,
  waitingReported,
} from '../lib/fleetAttention'

/**
 * The project column — hand-ordered groups, parked section, attention header.
 *
 * Task 7.1 (the left panel), 7.2 (the tile and the sticky count), and the half
 * of 7.5 that D-2 added: the order and the parked set are remembered state, and
 * they are the kind that must survive a reload rather than a tab, which is why
 * they live on the server rather than in `localStorage`.
 *
 * ## What the arrangement is, and what it is not
 *
 * It is *where the user wants things*, never *what exists*. Discovery answers
 * the second question, and the two answers are joined by the API. That join is
 * what keeps three silences from happening:
 *
 *  - a project the user arranged that discovery no longer finds is rendered as
 *    `nincs meg`, not dropped. A name disappearing from a hand-made list is
 *    information, and a list that rewrites itself is the thing the user would
 *    otherwise have to notice on their own;
 *  - a project that exists but was never arranged lands in the ungrouped block
 *    at the end — one more group, not a second layout mode;
 *  - a project discovery found that the arrangement places NOWHERE gets its own
 *    block with the reason. That should be impossible (both lists come from the
 *    same discovery pass) which is exactly why it is rendered: "should" is not a
 *    measurement, the two answers are fetched separately, and the failure
 *    direction is a project with a running agent rendering nowhere.
 *
 * ## Why the attention header is not decoration
 *
 * `ui-quality.md` puts one rule above the rest: compacting must never hide a
 * failure. Manual ordering is compaction the user performs themselves, and it
 * is the only one of the three options considered that has no construction
 * keeping a waiting project visible. So the count sits in a header that does not
 * scroll (a flex sibling of the scroll area, not `position: sticky`, which can
 * still be scrolled past inside a nested overflow), it counts across parked and
 * collapsed groups, and it jumps to the first one. Every collapsed group carries
 * its own copy of the same counters, because a collapsed group is one more place
 * a waiting agent can sit while the screen looks calm.
 *
 * ## Drag, and why it is pointer events rather than HTML5 drag-and-drop
 *
 * The gesture has to be one a person can actually perform, so it is built on
 * pointer events with capture — which real mouse and touch input produce, and
 * which a synthetic `dispatchEvent` in a test would only imitate. The handle is
 * also a focusable button that moves its row with the arrow keys: that path is
 * genuinely user-performable too, and unlike the pointer path it can be asserted
 * without a layout engine.
 */

// --------------------------------------------------------------------------- //
// Reordering by pointer, with a keyboard path that is not a fallback
// --------------------------------------------------------------------------- //

/**
 * `CSS.escape`, or a fallback.
 *
 * Not defensive habit: measured 2026-08-19, the unit environment's `localStorage`
 * is a plain object with none of its methods, so "the DOM globals are all there"
 * is not true here. A missing `CSS` would throw inside an effect and take the
 * landing screen down for a lookup that has a two-line substitute.
 */
function escapeAttr(value: string): string {
  const css = (globalThis as { CSS?: { escape?: (s: string) => string } }).CSS
  if (typeof css?.escape === 'function') return css.escape(value)
  return value.replace(/["\\]/g, m => '\\' + m)
}

interface ReorderHandlers {
  onPointerDown: (e: ReactPointerEvent<HTMLElement>) => void
  onPointerMove: (e: ReactPointerEvent<HTMLElement>) => void
  onPointerUp: (e: ReactPointerEvent<HTMLElement>) => void
  onPointerCancel: () => void
  onKeyDown: (e: ReactKeyboardEvent<HTMLElement>) => void
}

interface ReorderApi {
  handlers: ReorderHandlers
  dragFrom: number | null
  dragTo: number | null
}

/**
 * Handles that carry their own index, rather than a factory called per row.
 *
 * The index and the identity live on the element as `data-drag-index` and
 * `data-drag-handle`, and every handler is a stable callback that reads them
 * off `currentTarget`. That is not a style choice: props built by calling into
 * the hook on every render close over refs, and a closure captured during
 * render is how a drag ends up moving the row that *used* to be at that index.
 * Reading the index from the element at the moment of the gesture means the
 * index cannot be stale, because it is not remembered at all.
 */
function useReorder(
  onMove: (from: number, to: number) => void,
  container: RefObject<HTMLDivElement | null>,
  /**
   * How many entries the STORED list has. Not `items().length`: a list may
   * render fewer rows than it holds (the ungrouped filter), and bounding the
   * keyboard move by what is on screen would stop an arrow key one row short of
   * the real end, or worse, at a boundary that moves when a filter is toggled.
   */
  count: number,
): ReorderApi {
  /**
   * `engaged` is what separates a CLICK from a DRAG, and it is not defensive
   * polish — it is a defect found on the live screen on 2026-08-19.
   *
   * Clicking a handle and releasing without moving reordered the list. The cause
   * is that `indexAt` answers "which row is under this point", and a press in the
   * lower half of a row is already past that row's midpoint, so it answers with
   * the NEXT row — a move of one position, committed by a gesture that looks like
   * nothing happening. Measured against the running server: one click on
   * `deckforge`'s grip moved it six positions and saved the result, because the
   * rows in between were hidden by the ungrouped filter and the answer is a
   * STORED index.
   *
   * Its direction is what makes it worth this comment. Nothing fails, nothing is
   * lost, and the arrangement is hand-made work that the user is not watching a
   * diff of — so the screen quietly rewrites the thing they built, one accidental
   * click at a time.
   */
  const live = useRef<{ from: number; to: number; pointerId: number; startY: number; engaged: boolean } | null>(null)
  /** Pixels the pointer must travel before this counts as a drag at all. */
  const DRAG_THRESHOLD = 4
  const refocus = useRef<string | null>(null)
  const [drag, setDrag] = useState<{ from: number; to: number } | null>(null)


  // After a keyboard move the row is re-rendered at its new index, so the
  // handle loses focus and the next arrow press goes nowhere. Restoring it is
  // what makes the keyboard path a real way to reorder rather than a way to
  // move something once.
  useEffect(() => {
    const key = refocus.current
    if (!key) return
    refocus.current = null
    container.current?.querySelector<HTMLElement>(`[data-drag-handle="${escapeAttr(key)}"]`)?.focus()
  })

  const items = (): HTMLElement[] =>
    Array.from(container.current?.querySelectorAll<HTMLElement>(':scope > [data-drag-item]') ?? [])

  const indexOf = (el: HTMLElement): number => Number(el.dataset.dragIndex ?? -1)

  /**
   * The STORED index of the row under the pointer — read off the element, not
   * counted from its position among the rendered rows.
   *
   * The two are the same only while every member of the list is on screen, and
   * they stopped being the same when the ungrouped block gained a filter that
   * hides its agent-less projects. Counting rendered rows would then move a
   * project to the position of the *visible* row it was dropped on, which is a
   * different project — and the arrangement is hand-made work, so the mistake is
   * silent and expensive. Reading the index the row carries makes a partially
   * rendered list behave exactly like a complete one.
   */
  const indexAt = (clientY: number): number => {
    const list = items()
    if (list.length === 0) return 0
    for (const el of list) {
      const rect = el.getBoundingClientRect()
      if (clientY < rect.top + rect.height / 2) return indexOf(el)
    }
    return indexOf(list[list.length - 1])
  }

  const handlers: ReorderHandlers = {
    onPointerDown: (e) => {
      if (e.button !== 0) return
      const from = indexOf(e.currentTarget)
      if (from < 0) return
      e.preventDefault()
      e.stopPropagation()
      // `preventDefault` above stops the browser's own focus-on-mousedown, so
      // without this the handle can only be reached with Tab — and the arrow-key
      // path, which is the only reordering a keyboard user has, would be
      // unreachable from the gesture that obviously starts a drag.
      e.currentTarget.focus()
      e.currentTarget.setPointerCapture?.(e.pointerId)
      live.current = { from, to: from, pointerId: e.pointerId, startY: e.clientY, engaged: false }
      // Deliberately NOT `setDrag` yet: a press is not a drag, and highlighting
      // a drop target before the pointer has moved tells the reader a move is
      // under way when one click would commit nothing.
    },
    onPointerMove: (e) => {
      const s = live.current
      if (!s || e.pointerId !== s.pointerId) return
      if (!s.engaged) {
        if (Math.abs(e.clientY - s.startY) < DRAG_THRESHOLD) return
        s.engaged = true
      }
      const to = indexAt(e.clientY)
      if (to !== s.to) {
        s.to = to
        setDrag({ from: s.from, to })
      }
    },
    onPointerUp: (e) => {
      const s = live.current
      if (!s || e.pointerId !== s.pointerId) return
      e.currentTarget.releasePointerCapture?.(e.pointerId)
      live.current = null
      setDrag(null)
      // `engaged` first: without it, a release inside the row it started in
      // still commits, because the press point alone already resolves to a
      // different index.
      if (s.engaged && s.to !== s.from && s.to >= 0) {
        refocus.current = e.currentTarget.dataset.dragHandle ?? null
        onMove(s.from, s.to)
      }
    },
    onPointerCancel: () => { live.current = null; setDrag(null) },
    onKeyDown: (e) => {
      if (e.key !== 'ArrowUp' && e.key !== 'ArrowDown') return
      const from = indexOf(e.currentTarget)
      const to = e.key === 'ArrowUp' ? from - 1 : from + 1
      if (from < 0 || to < 0 || to >= count) return
      e.preventDefault()
      refocus.current = e.currentTarget.dataset.dragHandle ?? null
      onMove(from, to)
    },
  }

  return { handlers, dragFrom: drag?.from ?? null, dragTo: drag?.to ?? null }
}

/** The attributes that turn a button into a drag handle for row `index`. */
function handleAttrs(h: ReorderHandlers, index: number, key: string, label: string) {
  return {
    ...h,
    type: 'button' as const,
    'data-drag-handle': key,
    'data-drag-index': index,
    'aria-label': label,
    title: `${label} — drag, or ↑/↓ when focused`,
  }
}

function Grip() {
  return (
    <span aria-hidden className="text-xs text-fg-ghost leading-none select-none">⠿</span>
  )
}

// --------------------------------------------------------------------------- //
// Counters — one component, so a count cannot read one way open and another closed
// --------------------------------------------------------------------------- //

/**
 * The state counters, used identically on a project row, on a group header and
 * on the parked summary.
 *
 * One component on purpose. A collapsed group's counter is the only thing
 * standing between a waiting agent and a screen that looks calm, so it must not
 * be a differently-worded reimplementation of the row's counter that can drift
 * away from it.
 */
function Counts({ t, showAgents = true, waitingKnown }: { t: Tally; showAgents?: boolean; waitingKnown: boolean }) {
  return (
    <span className="inline-flex items-center gap-2 text-xs tabular-nums shrink-0">
      {waitingKnown && t.waiting > 0 && (
        <span className="inline-flex items-center gap-1 text-sky-300 font-semibold" title="waiting for an answer">
          <span className="w-1.5 h-1.5 rounded-full bg-sky-300" />{t.waiting}
        </span>
      )}
      {t.working > 0 && (
        <span className="inline-flex items-center gap-1 text-emerald-400" title="working">
          <span className="w-1.5 h-1.5 rounded-full bg-emerald-400" />{t.working}
        </span>
      )}
      {t.unknown > 0 && (
        <span className="inline-flex items-center gap-1 text-amber-400" title="unknown state">
          <span className="w-1.5 h-1.5 rounded-full bg-amber-400" />{t.unknown}
        </span>
      )}
      {/* Task 7.14 — work waiting for a HUMAN, with or without an agent. A
          different shape from the state dots on purpose: those describe an
          agent that exists, this one usually describes a project where none
          does, and one visual weight per meaning is the rule. */}
      {t.awaiting > 0 && (
        <span
          data-fleet-awaiting={t.awaiting}
          className="inline-flex items-center gap-1 text-violet-300"
          title="waiting for a human — even where no agent is running here"
        >
          {/* A SQUARE, where every agent-state marker is a circle. The shape
              carries the meaning — an agent that exists versus work with nobody
              on it — so the two can never be confused at a glance.

              It is CSS and not a glyph on purpose: the first version used ⏸,
              which rendered as a tofu box in this monospace stack. A marker
              that depends on a font's coverage is a marker that disappears on
              somebody else's machine. */}
          <span className="w-1.5 h-1.5 bg-violet-300" />{t.awaiting}
        </span>
      )}
      {showAgents && <span className="text-fg-muted">{t.agents}</span>}
    </span>
  )
}

// --------------------------------------------------------------------------- //
// One project
// --------------------------------------------------------------------------- //

interface RowProps {
  name: string
  project: FleetProject | undefined
  active: boolean
  waitingKnown: boolean
  onSelect: () => void
  handle?: Record<string, unknown>
  /** Position in the STORED list — what a drop on this row means. */
  index?: number
  /** Last row of its list — no separator below it, so a block ends cleanly. */
  last?: boolean
  dragging?: boolean
  dropTarget?: boolean
  menuOpen: boolean
  onMenu: () => void
  groups: FleetGroup[]
  currentGroupId: string | null
  parked: boolean
  onAssign: (target: Target) => void
}

function ProjectRow(p: RowProps) {
  const t = p.project
    ? tallyOf([p.name], new Map([[p.name, p.project as AttentionProject]]))
    : EMPTY_TALLY
  return (
    <div
      data-drag-item
      data-drag-index={p.index}
      data-fleet-project={p.name}
      className={p.dropTarget ? 'rounded outline outline-1 outline-sky-400' : undefined}
    >
      {/* Task 7.17. A hairline under every row except the last of its list.

          The token is `surface-edge`, NOT `surface-line`. Measured while
          building this: `--color-surface-line` and `--color-surface-raised` are
          the SAME value (neutral-800), so a border painted with it is invisible
          against exactly the surface it is supposed to bound — the first
          attempt rendered and could not be seen. A name that promises an edge
          while aliasing a fill is the second-place defect in a palette.
          These rows are COMPARABLE — same fields, same order — which is the
          case `ui-quality.md` says wants a table's separation rather than a
          list of floating cards. Without it the column reads as one surface
          and the eye has nothing to land on; measured by the user as
          "nagyon összefolynak a dolgok, mert nincsenek határok közöttük".

          The separator is on the row and not between rows, because a gap
          rendered between siblings disappears exactly when a row is dragged
          out — and a boundary that vanishes during a reorder is worse than
          none, since reordering is when you most need to see the rows. */}
      <div
        className={`flex items-center gap-1 rounded border transition-colors ${
          p.active
            ? 'border-surface-line bg-surface-raised'
            : `border-transparent hover:bg-surface-raised/50 ${p.last ? '' : 'border-b-surface-edge/70'}`
        } ${p.dragging ? 'opacity-50' : ''}`}
      >
        {p.handle ? (
          <button
            {...p.handle}
            className="px-1 py-1.5 cursor-grab active:cursor-grabbing touch-none focus:outline-none focus-visible:ring-1 focus-visible:ring-sky-400 rounded"
          >
            <Grip />
          </button>
        ) : (
          <span className="px-1 py-1.5 opacity-0" aria-hidden><Grip /></span>
        )}
        <button
          onClick={p.onSelect}
          className={`flex-1 min-w-0 text-left py-1 pr-1 ${p.active ? 'text-fg-loud' : 'text-fg-strong'}`}
        >
          <span className="text-sm truncate block">{p.name}</span>
          {p.project && p.project.archived && (
            <span className="text-xs text-fg-ghost">archived</span>
          )}
        </button>
        <Counts t={t} waitingKnown={p.waitingKnown} showAgents={t.agents > 0} />
        <button
          onClick={p.onMenu}
          aria-expanded={p.menuOpen}
          aria-label={`${p.name} — group and park`}
          title="assign to a group / park — a separate control, not a drag"
          className="px-1.5 py-1 text-fg-ghost hover:text-fg-strong shrink-0"
        >
          ⋯
        </button>
      </div>
      {p.menuOpen && (
        <div data-fleet-assign={p.name} className="ml-6 mr-1 mb-1 mt-0.5 rounded border border-surface-line bg-surface-raised p-1.5 text-xs space-y-0.5">
          <div className="text-fg-ghost">
            move — from here on, membership is a stored fact rather than a name pattern
          </div>
          {p.groups.filter(g => g.id !== p.currentGroupId).map(g => (
            <button
              key={g.id}
              onClick={() => p.onAssign({ kind: 'group', id: g.id })}
              className="block w-full text-left px-1.5 py-0.5 rounded text-fg-strong hover:bg-surface-raised"
            >
              → {g.name}
            </button>
          ))}
          {(p.currentGroupId !== null || p.parked) && (
            <button
              onClick={() => p.onAssign({ kind: 'ungrouped' })}
              className="block w-full text-left px-1.5 py-0.5 rounded text-fg-strong hover:bg-surface-raised"
            >
              → ungrouped
            </button>
          )}
          {p.parked ? (
            <button
              onClick={() => p.onAssign({ kind: 'ungrouped' })}
              className="block w-full text-left px-1.5 py-0.5 rounded text-fg-strong hover:bg-surface-raised"
            >
              ↩ put back in the list
            </button>
          ) : (
            <button
              onClick={() => p.onAssign({ kind: 'parked' })}
              className="block w-full text-left px-1.5 py-0.5 rounded text-fg-strong hover:bg-surface-raised"
            >
              ⇣ park it
            </button>
          )}
        </div>
      )}
    </div>
  )
}

/**
 * A project the user arranged that discovery no longer finds.
 *
 * Rendered, never dropped — and removing it is the user's decision rather than
 * a tidy-up the screen performs on their behalf, because the framework cannot
 * tell "this project is gone" from "discovery could not see it this time".
 */
function MissingRow({ name, onForget, index }: { name: string; onForget: () => void; index?: number }) {
  return (
    // A drag item like any other: it occupies a position in the stored list, so
    // dropping a project above or below it has to mean what it looks like. It
    // carries no handle of its own — a name discovery cannot find is not
    // something to reorder, it is something to keep or to forget.
    <div
      data-drag-item
      data-drag-index={index}
      data-fleet-missing={name}
      className="flex items-center gap-2 pl-6 pr-1 py-0.5"
    >
      <span className="text-xs text-fg-ghost line-through truncate flex-1 min-w-0">{name}</span>
      <span className="text-xs text-amber-400 shrink-0" title="It is in the arrangement, but discovery cannot find it. Not removed — a name vanishing from a hand-made list is information.">
        missing
      </span>
      <button onClick={onForget} className="text-xs text-fg-ghost hover:text-fg-strong shrink-0 underline underline-offset-2" title="Drop it from the arrangement">
        forget
      </button>
    </div>
  )
}

// --------------------------------------------------------------------------- //
// One group
// --------------------------------------------------------------------------- //

interface GroupProps {
  group: FleetGroup
  groups: FleetGroup[]
  byName: Map<string, FleetProject>
  waitingKnown: boolean
  selected: string | null
  onSelect: (name: string) => void
  onMoveProject: (groupId: string, from: number, to: number) => void
  onAssign: (project: string, target: Target) => void
  onToggle: (collapsed: boolean) => void
  onRemove: () => void
  confirmRemove: boolean
  onAskRemove: () => void
  onForget: (project: string) => void
  forcedOpen: boolean
  groupHandle?: Record<string, unknown>
  groupIndex: number
  groupDragging?: boolean
  groupDropTarget?: boolean
  menuFor: string | null
  setMenuFor: (name: string | null) => void
}

function GroupBlock(p: GroupProps) {
  const t = tallyOf(p.group.projects, p.byName as ReadonlyMap<string, AttentionProject>)
  const open = !p.group.collapsed || p.forcedOpen
  const list = useRef<HTMLDivElement | null>(null)
  const reorder = useReorder((from, to) => p.onMoveProject(p.group.id, from, to), list, p.group.order.length)
  const found = useMemo(() => new Set(p.group.projects), [p.group.projects])

  return (
    <div
      data-drag-item
      data-drag-index={p.groupIndex}
      data-fleet-group={p.group.id}
      data-fleet-group-collapsed={p.group.collapsed ? 'true' : 'false'}
      className={`rounded border border-surface-edge/60 bg-surface-panel/50 ${p.groupDropTarget ? 'outline outline-1 outline-sky-400' : ''} ${p.groupDragging ? 'opacity-50' : ''}`}
    >
      <div className="flex items-center gap-1 px-0.5 py-0.5">
        {p.groupHandle ? (
          <button
            {...p.groupHandle}
            className="px-1 py-1 cursor-grab active:cursor-grabbing touch-none focus:outline-none focus-visible:ring-1 focus-visible:ring-sky-400 rounded"
          >
            <Grip />
          </button>
        ) : (
          <span className="px-1 py-1 opacity-0" aria-hidden><Grip /></span>
        )}
        <button
          onClick={() => p.onToggle(!p.group.collapsed)}
          aria-expanded={open}
          className="flex-1 min-w-0 text-left text-xs font-semibold uppercase tracking-wide text-fg-muted hover:text-fg-strong truncate"
        >
          <span aria-hidden className="inline-block w-3">{open ? '▾' : '▸'}</span>
          {p.group.name}
          <span className="ml-1.5 font-normal normal-case tracking-normal text-fg-ghost tabular-nums">
            {p.group.projects.length}
          </span>
        </button>
        {/* The counters ride on the group header whether it is open or closed.
            A collapsed group is one more place a waiting agent can sit while
            the screen looks calm — the one thing ui-quality.md puts above the
            rest — so what is hidden is marked where the reader is standing. */}
        <Counts t={t} waitingKnown={p.waitingKnown} showAgents={false} />
        {/* Two clicks, because one click on a control this small next to a
            counter is how a group disappears by accident. Nothing is lost when
            it does — the members move to the ungrouped tail — but the ORDER
            inside the group is, and that is hand-made work. */}
        {p.confirmRemove ? (
          <button
            onClick={p.onRemove}
            title="Its projects move to the ungrouped tail; the order inside the group is lost"
            className="px-1 text-xs text-amber-400 hover:text-fg-loud shrink-0"
          >
            sure? ✕
          </button>
        ) : (
          <button
            onClick={p.onAskRemove}
            title="Remove the group — its projects move to the ungrouped tail, none disappears"
            className="px-1 text-xs text-fg-ghost hover:text-fg-strong shrink-0"
          >
            ✕
          </button>
        )}
      </div>
      {open && (
        /* The STORED order, in one list — found and missing interleaved exactly
           where the user put them. Before the API returned `order` the two had
           to be rendered as two blocks with the missing ones flattened to the
           end, which meant the screen showed a position the arrangement did not
           hold, and every save made that position real. */
        <div ref={list} className="pl-2 space-y-0.5">
          {p.group.order.map((name, i) => (
            found.has(name) ? (
              <ProjectRow
                key={name}
                name={name}
                index={i}
                last={i === p.group.order.length - 1}
                project={p.byName.get(name)}
                active={p.selected === name}
                waitingKnown={p.waitingKnown}
                onSelect={() => p.onSelect(name)}
                handle={handleAttrs(reorder.handlers, i, `${p.group.id}:${name}`, `order of ${name} within the group ${p.group.name}`)}
                dragging={reorder.dragFrom === i}
                dropTarget={reorder.dragFrom !== null && reorder.dragTo === i && reorder.dragFrom !== i}
                menuOpen={p.menuFor === name}
                onMenu={() => p.setMenuFor(p.menuFor === name ? null : name)}
                groups={p.groups}
                currentGroupId={p.group.id}
                parked={false}
                onAssign={target => { p.setMenuFor(null); p.onAssign(name, target) }}
              />
            ) : (
              <MissingRow key={name} name={name} index={i} onForget={() => p.onForget(name)} />
            )
          ))}
          {p.group.order.length === 0 && (
            <div className="pl-6 py-0.5 text-xs text-fg-ghost">empty group</div>
          )}
        </div>
      )}
      {!open && p.group.missing.length > 0 && (
        <div className="pl-6 text-xs text-amber-400">{p.group.missing.length} missing</div>
      )}
    </div>
  )
}

// --------------------------------------------------------------------------- //
// The column
// --------------------------------------------------------------------------- //

export default function FleetProjectColumn({
  data,
  selected,
  onSelect,
}: {
  data: FleetResponse
  selected: string | null
  onSelect: (name: string) => void
}) {
  const [arr, setArr] = useState<FleetArrangement | null>(null)
  const [loadError, setLoadError] = useState<string | null>(null)
  const [conflict, setConflict] = useState<string | null>(null)
  const [saveError, setSaveError] = useState<string | null>(null)
  const [forcedOpen, setForcedOpen] = useState<Set<string>>(() => new Set())
  const [parkedOpen, setParkedOpen] = useState(false)
  // 40-odd registered projects run nothing most of the time. Hidden by default
  // so the block the reader arranges is the block they can see — see the note
  // where the toggle is rendered for why this cannot hide a failure.
  const [showQuietUngrouped, setShowQuietUngrouped] = useState(false)
  const [menuFor, setMenuFor] = useState<string | null>(null)
  const [confirmRemove, setConfirmRemove] = useState<string | null>(null)
  const [newGroup, setNewGroup] = useState<{ name: string; prefix: string } | null>(null)
  const [jumpTo, setJumpTo] = useState<string | null>(null)
  const scrollRef = useRef<HTMLDivElement | null>(null)
  const inFlight = useRef(false)

  const byName = useMemo(() => {
    const m = new Map<string, FleetProject>()
    for (const p of data.projects) m.set(p.name, p)
    return m
  }, [data.projects])

  const waitingKnown = useMemo(
    () => waitingReported(data, data.projects as AttentionProject[]),
    [data],
  )

  const loadLayout = useCallback(() => {
    return fetch('/api/fleet/layout')
      .then(r => (r.ok ? r.json() : Promise.reject(new Error(`HTTP ${r.status}`))))
      .then(body => { setArr(fromResponse(body)); setLoadError(null); setConflict(null) })
      .catch(e => setLoadError(String(e?.message ?? e)))
  }, [])

  useEffect(() => { void loadLayout() }, [loadLayout])

  /**
   * Save the whole arrangement, optimistically, and REFUSE to swallow a 409.
   *
   * Two open dashboard tabs are ordinary, and the loser of a silent race would
   * find an arrangement they never made. So the local change stays on screen —
   * it is what the user just did — and the banner says the write was refused
   * and offers the reload that resolves it. Discarding their edit silently and
   * discarding the other tab's silently are both worse than saying so.
   */
  const save = useCallback(async (next: FleetArrangement) => {
    setArr(next)
    setSaveError(null)
    if (inFlight.current) return
    inFlight.current = true
    try {
      const res = await fetch('/api/fleet/layout', {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(toPutBody(next)),
      })
      if (res.status === 409) {
        const body = await res.json().catch(() => null)
        setConflict(String(body?.detail ?? 'the arrangement changed while you were editing it'))
        return
      }
      if (!res.ok) { setSaveError(`HTTP ${res.status}`); return }
      const body = await res.json()
      setArr(fromResponse(body))
      setConflict(null)
    } catch (e) {
      setSaveError(String((e as Error)?.message ?? e))
    } finally {
      inFlight.current = false
    }
  }, [])

  const discovered = useMemo(() => data.projects.map(p => p.name), [data.projects])
  /**
   * The fallback when the arrangement is UNREADABLE: every discovered project
   * falls into the ungrouped tail rather than off the screen. A lost
   * arrangement is never a lost list of projects, and the banner above says
   * which of the two happened.
   *
   * Deliberately NOT used while the arrangement is merely still loading. That
   * would paint 45 grouped projects as ungrouped for a moment — a statement
   * about the arrangement that has not been measured yet, and one the reader
   * would see reshuffle itself a beat later. Same rule as the screen's own
   * looking-vs-answered split: a gap is not an answer.
   */
  const view = useMemo(
    () => arr ?? (loadError ? { ...emptyArrangement(), ungrouped: discovered } : emptyArrangement()),
    [arr, loadError, discovered],
  )
  /**
   * Has the arrangement answered at all? Until it has, `view` is empty — and an
   * empty arrangement would make EVERY discovered project an orphan and every
   * count a zero. Both are answers, and neither was given yet, so both wait.
   */
  const arrangementKnown = arr !== null || loadError !== null
  const orphans = useMemo(
    () => (arrangementKnown ? findOrphans(view, discovered) : []),
    [arrangementKnown, view, discovered],
  )

  // The reading order, including everything out of sight. The attention header's
  // jump has to reach a collapsed group and the parked section, so the order it
  // searches is the whole document rather than what happens to be rendered.
  // The counts come from DISCOVERY either way. The arrangement decides order and
  // grouping; it never decides how many agents are running, so a slow or broken
  // arrangement must not be able to make the header read calm.
  const order = useMemo(
    () => (arrangementKnown ? [...arrangedNames(view), ...orphans] : discovered),
    [arrangementKnown, view, orphans, discovered],
  )
  // Counted from the data, not from the arrangement: a name the arrangement
  // holds that discovery cannot find is not a project on this machine, and
  // adding it to a project count would be the declaration-is-not-data defect
  // in the one number the reader trusts at a glance.
  const present = useMemo(() => order.filter(n => byName.has(n)), [order, byName])
  const missingCount = order.length - present.length
  const totals = useMemo(() => tallyOf(order, byName as ReadonlyMap<string, AttentionProject>), [order, byName])
  const firstWaiting = useMemo(
    () => firstWith(order, byName as ReadonlyMap<string, AttentionProject>, [WAITING]),
    [order, byName],
  )
  const firstUnknown = useMemo(
    () => firstWith(order, byName as ReadonlyMap<string, AttentionProject>, [UNKNOWN]),
    [order, byName],
  )
  const firstConflict = useMemo(
    () => firstMatching(order, byName as ReadonlyMap<string, AttentionProject>, hasConflict),
    [order, byName],
  )
  const firstAwaitingProject = useMemo(
    () => firstAwaiting(order, byName as ReadonlyMap<string, AttentionProject>),
    [order, byName],
  )

  /**
   * The first selection follows the arrangement, not discovery's order.
   *
   * Without this the screen opened on whichever project discovery happened to
   * list first — which was a PARKED one, so the right-hand panel showed a
   * project that could not be seen selected anywhere in the column. A selection
   * the reader cannot locate is worse than none.
   */
  useEffect(() => {
    // Not until the arrangement has answered. Measured on the live screen: the
    // effect fired against discovery's raw order first, landed on a PARKED
    // project, and the arrangement arriving a beat later could not undo it —
    // the selection was no longer null. The right-hand panel then showed a
    // project that was collapsed out of sight in the column.
    if (!arrangementKnown || selected !== null) return
    const first = present.find(n => (byName.get(n)?.agents.length ?? 0) > 0) ?? present[0]
    if (first) onSelect(first)
  }, [arrangementKnown, selected, present, byName, onSelect])

  const groupOf = useCallback((name: string): string | null => {
    for (const g of view.groups) if (g.projects.includes(name)) return g.id
    return null
  }, [view.groups])

  /** Reveal a project wherever it is hiding, then bring it into view. */
  const jump = useCallback((name: string | null) => {
    if (!name) return
    const gid = groupOf(name)
    if (gid) setForcedOpen(prev => new Set(prev).add(gid))
    if (view.parked.includes(name)) setParkedOpen(true)
    onSelect(name)
    setJumpTo(name)
  }, [groupOf, onSelect, view.parked])

  useEffect(() => {
    if (!jumpTo) return
    const el = scrollRef.current?.querySelector<HTMLElement>(`[data-fleet-project="${escapeAttr(jumpTo)}"]`)
    el?.scrollIntoView({ block: 'center' })
    setJumpTo(null)
  }, [jumpTo, view])

  const groupList = useRef<HTMLDivElement | null>(null)
  const groupReorder = useReorder((from, to) => void save(moveGroup(view, from, to)), groupList, view.groups.length)

  const ungroupedList = useRef<HTMLDivElement | null>(null)
  const ungroupedReorder = useReorder(
    (from, to) => void save(moveUngrouped(view, from, to)),
    ungroupedList,
    view.ungrouped.length,
  )
  const parkedList = useRef<HTMLDivElement | null>(null)
  const parkedReorder = useReorder(
    (from, to) => void save(moveParked(view, from, to)),
    parkedList,
    view.parkedOrder.length,
  )

  const parkedTally = tallyOf(view.parked, byName as ReadonlyMap<string, AttentionProject>)
  const ungroupedQuiet = view.ungrouped.filter(n => (byName.get(n)?.agents.length ?? 0) === 0)
  const ungroupedTally = tallyOf(view.ungrouped, byName as ReadonlyMap<string, AttentionProject>)
  const parkedFound = useMemo(() => new Set(view.parked), [view.parked])

  return (
    <div className="w-72 shrink-0 border-r border-surface-line flex flex-col min-h-0">
      {/* ---------------------------------------------------------------- */}
      {/* The attention header. A flex sibling of the scroll area rather than
          `position: sticky`, so it cannot be scrolled past — sticky inside a
          nested overflow container has been known to. */}
      {/* ---------------------------------------------------------------- */}
      <div data-fleet-attention className="shrink-0 border-b border-surface-line px-2 py-1.5 space-y-1">
        <div className="flex items-center gap-2 flex-wrap">
          {waitingKnown ? (
            totals.waiting > 0 ? (
              <button
                data-fleet-jump="waiting"
                onClick={() => jump(firstWaiting)}
                className="inline-flex items-center gap-1.5 text-xs text-sky-300 font-semibold hover:underline underline-offset-2 tabular-nums"
              >
                <span className="w-2 h-2 rounded-full bg-sky-300" />
                {totals.waiting} waiting for an answer
                <span className="text-fg-muted font-normal">→ first one</span>
              </button>
            ) : (
              <span className="text-xs text-fg-muted tabular-nums">0 waiting for an answer</span>
            )
          ) : (
            /* NOT a zero. Where the producer does not report this state at all,
               a rendered `0 waiting for an answer` would be an answer nobody gave — the
               false-absence class this screen exists for.

               Measured 2026-08-19 (afternoon): the producer DOES report it now
               (`waiting: 1` in the envelope, `state: "waiting"` on an agent), so
               this branch no longer fires against the live server. It is kept
               because the reason it exists has not changed: an older server, a
               partial answer, or a future field that stops being emitted all
               land here, and each of them is a gap rather than a zero. */
            <span
              data-fleet-waiting="unreported"
              className="text-xs text-amber-400"
              title="This answer carries no 'waiting for an answer' measurement. Not a zero — a missing measurement."
            >
              “waiting for an answer” — this answer does not measure it
            </span>
          )}
          {/* Task 7.14. In the header rather than only on the row, for the same
              reason the waiting count is: a hand-made order has no construction
              that keeps this visible, and a project awaiting a human is the one
              a reader could unblock in a minute. The jump has its own finder —
              `firstMatching` looks for an AGENT, and these projects usually
              have none. */}
          {totals.awaiting > 0 && (
            <button
              data-fleet-jump="awaiting"
              onClick={() => jump(firstAwaitingProject)}
              className="inline-flex items-center gap-1.5 text-xs text-violet-300 hover:underline underline-offset-2 tabular-nums"
              title="Work waiting for a human — even where no agent is running. A manual step, a stalled change, or work marked running whose process is gone."
            >
              <span className="w-2 h-2 bg-violet-300" />
              {totals.awaiting} waiting for a human
              <span className="text-fg-muted">→</span>
            </button>
          )}
          {/* A zero here is only readable next to this. 37 of 41 projects had no
              orchestration state at all on the day this was built, so a bare
              `0 waiting for a human` would have described "we looked nowhere" as "there
              is nothing". */}
          {totals.unmeasured > 0 && (
            <span
              data-fleet-awaiting-unmeasured={totals.unmeasured}
              className="text-xs text-fg-ghost tabular-nums"
              title="This many projects have no orchestration state at all, so nothing was looked at there. Not a zero — not measured."
            >
              {totals.unmeasured} projects not measured
            </span>
          )}
          {/* A contradiction the surface never shows is one nobody ever fixes.
              The measurement already won — `state` holds the log's answer — so
              this changes nothing the reader must act on, and that is exactly
              why it would otherwise never surface anywhere. */}
          {totals.conflicts > 0 && (
            <button
              data-fleet-jump="conflict"
              onClick={() => jump(firstConflict)}
              className="inline-flex items-center gap-1.5 text-xs text-amber-400 hover:underline underline-offset-2 tabular-nums"
              title="This many agents' records declared a state their log contradicts. The measurement wins; the contradiction is on the producer's side."
            >
              <span aria-hidden>⚠</span>
              {totals.conflicts} contradicting declarations
              <span className="text-fg-muted">→</span>
            </button>
          )}
          {totals.unknown > 0 && (
            <button
              data-fleet-jump="unknown"
              onClick={() => jump(firstUnknown)}
              className="inline-flex items-center gap-1.5 text-xs text-amber-400 hover:underline underline-offset-2 tabular-nums"
            >
              <span className="w-2 h-2 rounded-full bg-amber-400" />
              {totals.unknown} unknown
              <span className="text-fg-muted">→</span>
            </button>
          )}
          {totals.working > 0 && (
            <span className="inline-flex items-center gap-1.5 text-xs text-emerald-400 tabular-nums">
              <span className="w-2 h-2 rounded-full bg-emerald-400" />{totals.working} dolgozik
            </span>
          )}
        </div>
        {/* The agent and project totals used to live here AND in the screen's
            header, with different filters and no way to tell which was which
            (raised 2026-08-19). They are now stated once, in the header, as one
            sentence that carries the relation between the two numbers. What
            stays here is the thing only this column knows: arranged names that
            discovery no longer finds. */}
        {missingCount > 0 && (
          <div
            className="text-xs text-amber-400 tabular-nums truncate"
            title="Projects placed in this arrangement that the latest discovery did not return."
          >
            {missingCount} arranged name(s) missing
          </div>
        )}
      </div>

      {conflict && (
        <div data-fleet-conflict className="shrink-0 border-b border-amber-500/40 bg-amber-500/10 px-2 py-1.5 text-xs text-amber-300 space-y-1">
          <div>Saving the arrangement was refused: {conflict}</div>
          <div className="text-amber-200/80">
            The screen holds your change, but it is <span className="font-semibold">not saved</span>.
          </div>
          <button
            onClick={() => { void loadLayout() }}
            className="underline underline-offset-2 hover:text-amber-100"
          >
            reload from the server (your unsaved change is lost)
          </button>
        </div>
      )}
      {saveError && (
        <div className="shrink-0 border-b border-surface-line px-2 py-1 text-xs text-red-400">
          saving the arrangement failed: {saveError} — the order you see is not saved
        </div>
      )}
      {loadError && (
        <div className="shrink-0 border-b border-surface-line px-2 py-1 text-xs text-amber-400">
          the arrangement cannot be read ({loadError}) — the projects render as ungrouped,
          which is not a statement that there is no arrangement
        </div>
      )}

      <div ref={scrollRef} className="flex-1 overflow-y-auto p-1 space-y-1 min-h-0">
        {arr === null && !loadError && (
          <div data-fleet-arrangement="loading" className="px-2 py-1.5 text-xs text-fg-muted">
            loading the arrangement…
          </div>
        )}
        {/* Ordered groups. */}
        <div ref={groupList} className="space-y-1">
          {view.groups.map((g, i) => (
            <GroupBlock
              key={g.id}
              group={g}
              groups={view.groups}
              byName={byName}
              waitingKnown={waitingKnown}
              selected={selected}
              onSelect={onSelect}
              onMoveProject={(gid, from, to) => void save(moveProject(view, gid, from, to))}
              onAssign={(project, target) => void save(assign(view, project, target))}
              onToggle={collapsed => {
                setForcedOpen(prev => { const n = new Set(prev); n.delete(g.id); return n })
                void save(setCollapsed(view, g.id, collapsed))
              }}
              onRemove={() => { setConfirmRemove(null); void save(removeGroup(view, g.id)) }}
              confirmRemove={confirmRemove === g.id}
              onAskRemove={() => setConfirmRemove(g.id)}
              onForget={project => void save(forgetMissing(view, project))}
              forcedOpen={forcedOpen.has(g.id)}
              groupIndex={i}
              groupHandle={handleAttrs(groupReorder.handlers, i, `group:${g.id}`, `order of the ${g.name} group`)}
              groupDragging={groupReorder.dragFrom === i}
              groupDropTarget={groupReorder.dragFrom !== null && groupReorder.dragTo === i && groupReorder.dragFrom !== i}
              menuFor={menuFor}
              setMenuFor={setMenuFor}
            />
          ))}
        </div>

        {/* ------------------------------------------------------------ */}
        {/* Ungrouped — one more group at the end, never a second layout mode. */}
        {/* ------------------------------------------------------------ */}
        {view.ungrouped.length > 0 && (
          <div data-fleet-group="__ungrouped__" className="rounded">
            <div className="flex items-center gap-1 px-0.5 py-0.5">
              <span className="px-1 py-1 opacity-0" aria-hidden><Grip /></span>
              <span className="flex-1 min-w-0 text-xs font-semibold uppercase tracking-wide text-fg-muted truncate">
                ungrouped
                <span className="ml-1.5 font-normal normal-case tracking-normal text-fg-ghost tabular-nums">
                  {view.ungrouped.length}
                </span>
              </span>
              <Counts t={ungroupedTally} waitingKnown={waitingKnown} showAgents={false} />
            </div>
            {/* The ungrouped block is drag-orderable since the API started
                storing `ungrouped_order` (2026-08-19). Until then it carried a
                printed limit here — "sorrendjük a felderítésé" — because a drag
                had nothing to persist into. The limit is gone, so the sentence
                is gone: a stale caveat is worse than none, it teaches the reader
                that the caveats on this screen are decoration. */}
            <div ref={ungroupedList} className="pl-2 space-y-0.5">
              {view.ungrouped.map((name, i) => (
                (showQuietUngrouped || (byName.get(name)?.agents.length ?? 0) > 0) ? (
                  <ProjectRow
                    key={name}
                    name={name}
                    index={i}
                    last={i === view.ungrouped.length - 1}
                    project={byName.get(name)}
                    active={selected === name}
                    waitingKnown={waitingKnown}
                    onSelect={() => onSelect(name)}
                    handle={handleAttrs(ungroupedReorder.handlers, i, `ungrouped:${name}`, `order of ${name} among the ungrouped`)}
                    dragging={ungroupedReorder.dragFrom === i}
                    dropTarget={ungroupedReorder.dragFrom !== null && ungroupedReorder.dragTo === i && ungroupedReorder.dragFrom !== i}
                    menuOpen={menuFor === name}
                    onMenu={() => setMenuFor(menuFor === name ? null : name)}
                    groups={view.groups}
                    currentGroupId={null}
                    parked={false}
                    onAssign={target => { setMenuFor(null); void save(assign(view, name, target)) }}
                  />
                ) : null
              ))}
            </div>
            {/* Hiding the agent-less ones is compaction, and compaction must
                never hide a failure — so what is hidden is counted here, and
                the group's own `Counts` above already covers every state inside
                it whether the rows are drawn or not. A hidden project with a
                waiting agent is impossible by construction: the filter is "has
                no agents at all". */}
            {ungroupedQuiet.length > 0 && (
              <button
                data-fleet-ungrouped-filter={showQuietUngrouped ? 'off' : 'on'}
                onClick={() => setShowQuietUngrouped(v => !v)}
                className="ml-3 mt-0.5 text-xs text-fg-ghost hover:text-fg-strong tabular-nums"
                title="Arranging aid only; these projects run no agents at all, so there is no state in them to hide."
              >
                {showQuietUngrouped
                  ? `hide ${ungroupedQuiet.length} with no agents`
                  : `${ungroupedQuiet.length} with no agents — show`}
              </button>
            )}
          </div>
        )}

        {/* ------------------------------------------------------------ */}
        {/* Projects discovery found that the arrangement places nowhere.  */}
        {/* ------------------------------------------------------------ */}
        {orphans.length > 0 && (
          <div data-fleet-orphans className="rounded border border-amber-500/40 p-1">
            <div className="text-xs text-amber-400 px-1 py-0.5">
              {orphans.length} projects are not in the arrangement — the two answers differ when asked separately
              <button onClick={() => { void loadLayout() }} className="ml-1 underline underline-offset-2">refresh</button>
            </div>
            {orphans.map((name, i) => (
              <ProjectRow
                key={name}
                name={name}
                last={i === orphans.length - 1}
                project={byName.get(name)}
                active={selected === name}
                waitingKnown={waitingKnown}
                onSelect={() => onSelect(name)}
                menuOpen={menuFor === name}
                onMenu={() => setMenuFor(menuFor === name ? null : name)}
                groups={view.groups}
                currentGroupId={null}
                parked={false}
                onAssign={target => { setMenuFor(null); void save(assign(view, name, target)) }}
              />
            ))}
          </div>
        )}

        {/* ------------------------------------------------------------ */}
        {/* Parked — collapsed, with its own counter.                     */}
        {/* ------------------------------------------------------------ */}
        {(view.parked.length > 0 || view.parkedMissing.length > 0) && (
          <div data-fleet-parked data-fleet-parked-open={parkedOpen ? 'true' : 'false'} className="rounded border border-surface-line/60 mt-2">
            <button
              onClick={() => setParkedOpen(v => !v)}
              aria-expanded={parkedOpen}
              className="w-full flex items-center gap-1.5 px-1.5 py-1 text-xs text-fg-muted hover:text-fg-strong"
            >
              <span aria-hidden className="inline-block w-3">{parkedOpen ? '▾' : '▸'}</span>
              <span className="flex-1 text-left">parked</span>
              <span className="tabular-nums text-fg-ghost">{view.parked.length + view.parkedMissing.length}</span>
              {/* The parked section is the most compacted thing on this screen,
                  so it carries the same counters as everything else. It is out
                  of the way, never out of reach — and the header above counts
                  what is in here too. */}
              <Counts t={parkedTally} waitingKnown={waitingKnown} showAgents={false} />
            </button>
            {parkedOpen && (
              /* Same stored-order rendering as a group: `parked_order` is the
                 authority, so a parked project discovery cannot find keeps its
                 place instead of being flattened to the bottom on every save. */
              <div ref={parkedList} className="pl-2 pb-1 space-y-0.5">
                {view.parkedOrder.map((name, i) => (
                  parkedFound.has(name) ? (
                    <ProjectRow
                      key={name}
                      name={name}
                      index={i}
                      last={i === view.parkedOrder.length - 1}
                      project={byName.get(name)}
                      active={selected === name}
                      waitingKnown={waitingKnown}
                      onSelect={() => onSelect(name)}
                      handle={handleAttrs(parkedReorder.handlers, i, `parked:${name}`, `order of ${name} among the parked`)}
                      dragging={parkedReorder.dragFrom === i}
                      dropTarget={parkedReorder.dragFrom !== null && parkedReorder.dragTo === i && parkedReorder.dragFrom !== i}
                      menuOpen={menuFor === name}
                      onMenu={() => setMenuFor(menuFor === name ? null : name)}
                      groups={view.groups}
                      currentGroupId={null}
                      parked
                      onAssign={target => { setMenuFor(null); void save(assign(view, name, target)) }}
                    />
                  ) : (
                    <MissingRow key={name} name={name} index={i} onForget={() => void save(forgetMissing(view, name))} />
                  )
                ))}
              </div>
            )}
          </div>
        )}
      </div>

      {/* ------------------------------------------------------------ */}
      {/* Making a group. A prefix may SEED one; it is never stored.     */}
      {/* ------------------------------------------------------------ */}
      <div className="shrink-0 border-t border-surface-line p-1.5">
        {newGroup === null ? (
          <button
            onClick={() => setNewGroup({ name: '', prefix: '' })}
            className="text-xs text-fg-muted hover:text-fg-strong"
          >
            + group
          </button>
        ) : (
          <form
            data-fleet-new-group
            onSubmit={e => {
              e.preventDefault()
              if (!newGroup.name.trim()) return
              void save(createGroup(view, newGroup.name, seedCandidates(view, newGroup.prefix)))
              setNewGroup(null)
            }}
            className="space-y-1"
          >
            <input
              autoFocus
              value={newGroup.name}
              onChange={e => setNewGroup({ ...newGroup, name: e.target.value })}
              placeholder="group name"
              aria-label="group name"
              className="w-full bg-surface-panel border border-surface-line rounded px-1.5 py-1 text-xs text-fg-strong"
            />
            <input
              value={newGroup.prefix}
              onChange={e => setNewGroup({ ...newGroup, prefix: e.target.value })}
              placeholder="seed with a prefix (optional)"
              aria-label="prefix to seed with"
              className="w-full bg-surface-panel border border-surface-line rounded px-1.5 py-1 text-xs text-fg-strong"
            />
            <div className="text-xs text-fg-ghost leading-snug">
              {newGroup.prefix.trim()
                ? `${seedCandidates(view, newGroup.prefix).length} projects go in now — a one-time act; from then on membership is the stored fact and the prefix is not a rule`
                : 'the prefix fills the group once; it never runs again as a rule'}
            </div>
            <div className="flex gap-2">
              <button type="submit" className="text-xs text-sky-300 hover:underline">create</button>
              <button type="button" onClick={() => setNewGroup(null)} className="text-xs text-fg-muted hover:text-fg-strong">cancel</button>
            </div>
          </form>
        )}
      </div>
    </div>
  )
}
