import { createContext, useCallback, useContext, useEffect, useMemo, useState } from 'react'
import {
  Background, BaseEdge, Controls, EdgeLabelRenderer, Handle, MarkerType, Position, ReactFlow, ReactFlowProvider,
  type Edge as RFEdge, type EdgeProps, type Node as RFNode, type NodeProps,
} from '@xyflow/react'
import '@xyflow/react/dist/style.css'
import { Maximize2, PanelBottom, PanelRight, Waypoints, X } from 'lucide-react'

import {
  layoutMap, openerSummary, routePath,
  type EdgeMarker, type MapEdge, type MapModel, type MapNode, type MapPayload,
} from '../lib/fleetMap'

/**
 * The relation map — who exists for what, and who is asking whom.
 *
 * One control in the fleet header, one floating panel. Everything about WHAT
 * is drawn is decided in `lib/fleetMap.ts`; this file draws it and keeps three
 * rules of the screen:
 *
 * - **The closed map still reports.** The control carries the count of agents
 *   with no mandate and of requests that are waiting or failed, so nothing the
 *   map would mark is hidden by the map being shut. A read that failed shows
 *   as unread — never as two zeros, which is what calm looks like.
 * - **The panel floats.** It is `fixed`, above the fleet, and takes no room
 *   from it: opening the map moves nothing on the screen underneath. It can be
 *   held against the right edge, the bottom edge, or the whole area — the map
 *   is machine-wide, so it does not join the per-project dock store.
 * - **A detail floats too, inside the panel.** Clicking a node or an edge
 *   opens an overlay in the corner; no node moves, the canvas keeps its size,
 *   and the overlay has its own control to close it.
 *
 * It fetches its own data, like the wave chip beside it: the map joins the
 * inventory, the bus and the role file, and none of that may delay the agent
 * list.
 */

// The map joins the whole inventory, and one inventory read was measured at
// about three seconds of server time on a machine with fourteen agents. So the
// closed control asks once a minute, and the open map every fifteen seconds —
// ages on the edges are shown in minutes, and nothing here needs to be faster.
const CLOSED_INTERVAL_MS = 60_000
const OPEN_INTERVAL_MS = 15_000
const DOCK_KEY = 'fleet-map-dock'

type Dock = 'right' | 'bottom' | 'full'
// `left-16`, not `left-2`: the application's own navigation rail sits at the
// left edge above everything, and a panel that starts under it has its title
// cut off — seen on the running screen with the first build of this.
const DOCK_CLASS: Record<Dock, string> = {
  right: 'top-14 right-2 bottom-2 w-[min(1040px,64vw)]',
  bottom: 'left-16 right-2 bottom-2 h-[56vh]',
  full: 'top-14 left-16 right-2 bottom-2',
}

// One stroke per relation kind. They differ in dash pattern and weight, not
// only in colour, so the kinds stay apart for a reader who cannot tell the
// colours from each other.
const STROKE = {
  engagement: { stroke: '#38bdf8', strokeWidth: 2 },
  started: { stroke: '#a9afbc', strokeWidth: 1.5, strokeDasharray: '7 5' },
  flow: { stroke: '#878a98', strokeWidth: 1.25, strokeDasharray: '2 5' },
} as const
const MARKER_STROKE: Record<Exclude<EdgeMarker, null>, string> = {
  waiting: '#fbbf24',
  failed: '#f87171',
  unmeasured: '#878a98',
}

const STATE_DOT: Record<string, string> = {
  working: 'bg-emerald-400',
  waiting: 'bg-amber-400',
  quiet: 'bg-fg-ghost',
}

type Detail = { title: string; lines: string[] }

const HANDLE = '!w-1 !h-1 !min-w-0 !min-h-0 !border-0 !bg-transparent'

/* The library draws an edge only between two handles, so every node has a
   pair. Where the edge actually RUNS is not decided by them: `RoutedEdge`
   draws the route `lib/fleetMap.ts` computed, through the gaps between boxes. */
function Handles() {
  return (
    <>
      <Handle type="target" position={Position.Left} className={HANDLE} isConnectable={false} />
      <Handle type="source" position={Position.Right} className={HANDLE} isConnectable={false} />
    </>
  )
}

/** A click on an edge's label opens that edge's detail, like a click on its line. */
const OpenEdge = createContext<(id: string) => void>(() => {})

interface RoutedData {
  path: string
  labelAt: [number, number]
  label: string | null
  labelColor: string
  kind: MapEdge['kind']
  marker: EdgeMarker
  [key: string]: unknown
}

function RoutedEdge({ id, data, style, markerEnd }: EdgeProps) {
  const d = data as RoutedData
  const open = useContext(OpenEdge)
  return (
    <>
      <BaseEdge id={id} path={d.path} style={style} markerEnd={markerEnd} interactionWidth={16} />
      {d.label && (
        <EdgeLabelRenderer>
          <button
            onClick={() => open(id)}
            data-fleet-map-edge-label={id}
            data-fleet-map-edge-marker={d.marker ?? undefined}
            className="nodrag nopan absolute px-1 rounded bg-surface-page text-xs leading-4 whitespace-nowrap
                       border border-surface-line cursor-pointer"
            style={{
              transform: `translate(-50%, -50%) translate(${d.labelAt[0]}px, ${d.labelAt[1]}px)`,
              color: d.labelColor,
              pointerEvents: 'all',
              // Above the edges: a line drawn across a label strikes it out,
              // which is what the first routed build looked like.
              zIndex: 5,
            }}
          >{d.label}</button>
        </EdgeLabelRenderer>
      )}
    </>
  )
}

const EDGE_TYPES = { routed: RoutedEdge }

function ProjectNode({ data }: NodeProps) {
  const node = data as unknown as Extract<MapNode, { type: 'project' }>
  return (
    /* Border and title only: the edges run UNDER nodes, and a filled group
       would cover every relation that crosses it. */
    <div className="w-full h-full rounded border border-surface-strong pointer-events-none"
         data-fleet-map-project={node.name}>
      <div className="px-2 py-1 text-xs text-fg-loud truncate">
        {node.name}
        <span className="ml-1.5 text-fg-ghost tabular-nums">{node.agents}</span>
      </div>
      <Handles />
    </div>
  )
}

/** Context-fill bands from the server (`context_fill.band_for`): one colour per meaning. */
const FILL_TEXT: Record<string, string> = { normal: 'text-fg-muted', warning: 'text-amber-400', critical: 'text-rose-400' }
const FILL_BAR: Record<string, string> = { normal: 'bg-emerald-500/60', warning: 'bg-amber-400', critical: 'bg-rose-400' }

function AgentNode({ data }: NodeProps) {
  const node = data as unknown as Extract<MapNode, { type: 'agent' }>
  return (
    <div
      className={`relative w-full h-full px-2 py-1 rounded border bg-surface-panel cursor-pointer flex flex-col justify-center ${
        node.noMandate ? 'border-amber-400/60' : 'border-surface-line'
      }`}
      data-fleet-map-agent={node.label}
      data-fleet-map-no-mandate={node.noMandate ? 'yes' : undefined}
    >
      <div className="flex items-center gap-1.5 min-w-0">
        <span className={`w-1.5 h-1.5 rounded-full shrink-0 ${STATE_DOT[node.state ?? ''] ?? 'bg-amber-400/60'}`}
              title={`state: ${node.state ?? 'unknown'}`} />
        <span className="text-xs text-fg-strong truncate">{node.label}</span>
        {node.worktree && (
          <span className="ml-auto shrink-0 max-w-[45%] truncate text-xs text-sky-300"
                data-fleet-map-worktree={node.worktree}
                title={node.worktree === '?' ? 'runs outside the main tree, in no listed worktree' : `worktree ${node.worktree}`}>
            ⎇ {node.worktree}
          </span>
        )}
        {node.fill !== null && (
          <span className={`${node.worktree ? '' : 'ml-auto '}shrink-0 text-xs tabular-nums ${FILL_TEXT[node.band ?? ''] ?? 'text-fg-ghost'}`}
                data-fleet-map-fill={Math.round(node.fill * 100)}
                title="context fill">
            {Math.round(node.fill * 100)}%
          </span>
        )}
      </div>
      <div className="flex items-baseline gap-1.5 min-w-0 text-xs">
        {node.badge && (
          <span className={`shrink-0 ${node.badge === 'desk' ? 'text-violet-300' : 'text-sky-300'}`}>{node.badge}</span>
        )}
        {node.goal && <span className="text-fg-muted truncate">{node.goal}</span>}
        {node.noMandate && <span className="text-amber-400 shrink-0">⚠ no mandate</span>}
        {node.mandateUnmeasured && (
          <span className="text-amber-400 shrink-0" title="The mandate store could not be read.">mandate ?</span>
        )}
      </div>
      {/* The fill as a 2 px bar on the node's bottom edge: inside the box, so the
          layout does not move, and absent (not empty) when the fill is unmeasured. */}
      {node.fill !== null && (
        <span className="absolute left-0 bottom-0 h-0.5 pointer-events-none"
              style={{ width: `${Math.min(100, Math.max(2, node.fill * 100))}%` }}
              data-fleet-map-fill-bar>
          <span className={`block h-full ${FILL_BAR[node.band ?? ''] ?? 'bg-fg-ghost'}`} />
        </span>
      )}
      <Handles />
    </div>
  )
}

function SmallNode({ data }: NodeProps) {
  const node = data as unknown as Extract<MapNode, { type: 'collapsed' | 'idle' }>
  const idle = node.type === 'idle'
  const known = idle || node.known
  return (
    <div
      className={`w-full h-full px-2 flex items-center rounded border text-xs truncate ${
        idle ? 'border-surface-line text-fg-ghost cursor-pointer'
          : known ? 'border-surface-line text-fg-muted cursor-pointer'
            : 'border-dashed border-amber-400/50 text-amber-300 cursor-pointer'
      }`}
      data-fleet-map-small={idle ? 'idle' : node.name}
      title={idle ? 'Registered projects with no live agent and no open request.'
        : known ? 'A registered project with no live agent.'
          : 'Not a registered project — named by a relation, and nothing else is known about it.'}
    >
      {idle ? `${node.names.length} idle project${node.names.length === 1 ? '' : 's'}` : node.name}
      <Handles />
    </div>
  )
}

const NODE_TYPES = { project: ProjectNode, agent: AgentNode, collapsed: SmallNode, idle: SmallNode }

function nodeDetail(node: MapNode): Detail | null {
  if (node.type === 'agent') return { title: node.label, lines: node.detail }
  if (node.type === 'idle') {
    return { title: `${node.names.length} idle projects`, lines: ['No live agent and no open request:', node.names.join(', ')] }
  }
  if (node.type === 'collapsed') {
    return {
      title: node.name,
      lines: [node.known
        ? 'A registered project with no live agent. It is drawn because a relation ends on it.'
        : 'Not a registered project. A relation names it, and nothing else is known about it.'],
    }
  }
  return null
}

function toFlow(model: MapModel): { nodes: RFNode[]; edges: RFEdge[] } {
  const nodes: RFNode[] = model.nodes.map(n => ({
    id: n.id,
    type: n.type,
    position: { x: n.x, y: n.y },
    data: n as unknown as Record<string, unknown>,
    style: { width: n.w, height: n.h },
    draggable: false,
    selectable: n.type !== 'project',
    zIndex: n.type === 'project' ? 0 : 1,
  }))
  const edges: RFEdge[] = model.edges.map(e => {
    const base = STROKE[e.kind]
    const stroke = e.marker ? MARKER_STROKE[e.marker] : base.stroke
    const data: RoutedData = {
      path: routePath(e.points),
      labelAt: e.labelAt,
      // A start relation carries no label on the canvas: its stroke and the
      // legend name it, and a sentence on every one of them buries the nodes.
      // An engagement's label is its state and age, which is the point of it.
      label: e.kind === 'started' ? null
        : e.marker === 'waiting' || e.marker === 'failed' ? `⚠ ${e.label}` : e.label,
      labelColor: e.marker ? stroke : e.kind === 'flow' ? '#878a98' : '#c9cfd8',
      kind: e.kind,
      marker: e.marker,
    }
    return {
      id: e.id,
      type: 'routed',
      source: e.source,
      target: e.target,
      style: { ...base, stroke, fill: 'none' },
      // The arrow says which way a request or a start went. A declared flow
      // is not traffic, so it carries none.
      markerEnd: e.kind === 'flow' ? undefined
        : { type: e.kind === 'engagement' ? MarkerType.ArrowClosed : MarkerType.Arrow, color: stroke, width: 16, height: 16 },
      data,
      // Above the group boxes' borders, below nothing that matters: the route
      // runs in the gaps, so it has no node to hide behind.
      zIndex: e.kind === 'flow' ? 0 : 2,
    }
  })
  return { nodes, edges }
}

function LegendStroke({ kind }: { kind: keyof typeof STROKE }) {
  const s = STROKE[kind]
  return (
    <svg width="26" height="8" viewBox="0 0 26 8" className="shrink-0" aria-hidden>
      <line x1="1" y1="4" x2="25" y2="4" stroke={s.stroke} strokeWidth={s.strokeWidth}
            strokeDasharray={'strokeDasharray' in s ? s.strokeDasharray : undefined} />
    </svg>
  )
}

export function FleetMapPanel({ payload, stale, dock, onDock, onClose }: {
  payload: MapPayload | null
  /** The last refresh failed: what is shown is older than it looks. */
  stale: boolean
  dock: Dock
  onDock: (dock: Dock) => void
  onClose: () => void
}) {
  const [detail, setDetail] = useState<Detail | null>(null)
  const model = useMemo(() => (payload ? layoutMap(payload) : null), [payload])
  const flow = useMemo(() => (model ? toFlow(model) : null), [model])
  // Remount — and so re-fit — only when the SET of nodes changes or the panel
  // is re-docked. A poll that changes an age must not move the viewport.
  const shape = useMemo(() => `${dock}|${(model?.nodes ?? []).map(n => n.id).join(',')}`, [model, dock])

  // Escape closes the innermost thing first: the detail, then the panel.
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.key !== 'Escape') return
      if (detail) setDetail(null)
      else onClose()
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [detail, onClose])

  const openNode = useCallback((_: unknown, node: RFNode) => {
    const found = model?.nodes.find(n => n.id === node.id)
    const next = found ? nodeDetail(found) : null
    if (next) setDetail(next)
  }, [model])
  const openEdgeById = useCallback((id: string) => {
    const found: MapEdge | undefined = model?.edges.find(e => e.id === id)
    if (found) setDetail({ title: found.detailTitle, lines: found.detail })
  }, [model])
  const openEdge = useCallback((_: unknown, edge: RFEdge) => openEdgeById(edge.id), [openEdgeById])

  return (
    <div
      className={`fixed z-40 flex flex-col rounded border border-surface-strong bg-surface-page shadow-2xl ${DOCK_CLASS[dock]}`}
      role="dialog"
      aria-label="relation map"
      data-fleet-map-panel={dock}
    >
      <div className="flex items-center gap-3 px-3 py-1.5 border-b border-surface-line shrink-0 flex-wrap">
        <span className="text-sm text-fg-loud shrink-0">Relation map</span>
        <span className="flex items-center gap-3 text-xs text-fg-muted" data-fleet-map-legend>
          <span className="flex items-center gap-1" title="A request one agent sent to a project's desk, with its state and age.">
            <LegendStroke kind="engagement" /> request
          </span>
          <span className="flex items-center gap-1" title="Who the start request said was asking. A claim — nothing verified it.">
            <LegendStroke kind="started" /> said to have asked
          </span>
          <span className="flex items-center gap-1" title="A relation declared in the role file. Not traffic.">
            <LegendStroke kind="flow" /> declared flow
          </span>
        </span>
        {model && (
          <span className="flex items-center gap-2 text-xs tabular-nums" data-fleet-map-counts>
            <span className={model.counts.noMandate ? 'text-amber-400' : 'text-fg-ghost'}>{model.counts.noMandate} no mandate</span>
            <span className={model.counts.waiting ? 'text-amber-400' : 'text-fg-ghost'}>{model.counts.waiting} waiting</span>
            <span className={model.counts.failed ? 'text-red-400' : 'text-fg-ghost'}>{model.counts.failed} failed</span>
          </span>
        )}
        <span className="ml-auto flex items-center gap-1 shrink-0">
          {([['right', PanelRight, 'hold against the right edge'],
             ['bottom', PanelBottom, 'hold against the bottom edge'],
             ['full', Maximize2, 'use the whole area']] as const).map(([edge, Icon, label]) => (
            <button
              key={edge}
              onClick={() => onDock(edge)}
              aria-label={label}
              aria-pressed={dock === edge}
              data-fleet-map-dock={edge}
              title={label}
              className={`p-1 rounded border ${dock === edge
                ? 'border-sky-400/60 bg-sky-400/10 text-sky-300'
                : 'border-transparent text-fg-muted hover:text-fg-strong'}`}
            ><Icon size={13} strokeWidth={1.75} /></button>
          ))}
          <button onClick={onClose} aria-label="close the relation map" data-fleet-map-close
                  className="p-1 text-fg-muted hover:text-fg-strong"><X size={14} strokeWidth={1.75} /></button>
        </span>
      </div>

      {(stale || (model && model.notices.length > 0)) && (
        <div className="flex flex-col gap-0.5 px-3 py-1 border-b border-surface-line shrink-0" data-fleet-map-notices>
          {stale && (
            <span className="text-xs text-amber-400" data-fleet-map-notice="stale">
              The last refresh failed{payload ? ': this is the map as it was last read.' : ', and no map has been read yet.'}
            </span>
          )}
          {model?.notices.map(n => (
            <span key={n.key} data-fleet-map-notice={n.key}
                  className={`text-xs ${n.tone === 'warn' ? 'text-amber-400' : 'text-fg-ghost'}`}>{n.text}</span>
          ))}
        </div>
      )}

      {/* `relative` so the detail can float over the canvas. The canvas fills
          this box and is never resized by anything opening inside it. */}
      <div className="relative flex-1 min-h-0" data-fleet-map-canvas>
        {!payload && !stale && <span className="absolute inset-0 flex items-center justify-center text-xs text-fg-ghost">reading the map…</span>}
        {flow && model && model.nodes.length === 0 && (
          <span className="absolute inset-0 flex items-center justify-center text-xs text-fg-ghost" data-fleet-map-empty>
            {payload?.sources.inventory === false
              ? 'Nothing can be drawn: the fleet inventory could not be read.'
              : 'No registered project and no live agent.'}
          </span>
        )}
        {flow && model && model.nodes.length > 0 && (
          <OpenEdge.Provider value={openEdgeById}>
          <ReactFlowProvider>
            <ReactFlow
              key={shape}
              nodes={flow.nodes}
              edges={flow.edges}
              nodeTypes={NODE_TYPES}
              edgeTypes={EDGE_TYPES}
              onNodeClick={openNode}
              onEdgeClick={openEdge}
              fitView
              fitViewOptions={{ padding: 0.12, maxZoom: 1.1 }}
              minZoom={0.2}
              maxZoom={2}
              nodesDraggable={false}
              nodesConnectable={false}
              elementsSelectable
              proOptions={{ hideAttribution: true }}
            >
              <Background gap={20} color="#363c46" />
              <Controls showInteractive={false} position="bottom-left" />
            </ReactFlow>
          </ReactFlowProvider>
          </OpenEdge.Provider>
        )}
        {detail && (
          <div
            className="absolute top-2 right-2 z-10 w-80 max-w-[80%] max-h-[80%] overflow-auto flex flex-col gap-1
                       rounded border border-surface-strong bg-surface-raised shadow-xl px-2.5 py-2"
            data-fleet-map-detail
          >
            <div className="flex items-start gap-2">
              <span className="text-xs text-fg-loud break-words min-w-0">{detail.title}</span>
              <button onClick={() => setDetail(null)} aria-label="close the detail" data-fleet-map-detail-close
                      className="ml-auto shrink-0 text-fg-muted hover:text-fg-strong"><X size={13} strokeWidth={1.75} /></button>
            </div>
            {detail.lines.map((line, i) => (
              <span key={i} className="text-xs text-fg-normal break-words">{line}</span>
            ))}
          </div>
        )}
      </div>
    </div>
  )
}

function storedDock(): Dock {
  try {
    const v = window.localStorage.getItem(DOCK_KEY)
    return v === 'bottom' || v === 'full' ? v : 'right'
  } catch {
    return 'right'
  }
}

/** The header control: the two counts while closed, the panel while open. */
export default function FleetMap() {
  const [payload, setPayload] = useState<MapPayload | null>(null)
  const [failed, setFailed] = useState(false)
  const [open, setOpen] = useState(false)
  const [dock, setDockState] = useState<Dock>(storedDock)

  useEffect(() => {
    let cancelled = false
    const read = () => {
      fetch('/api/fleet/map')
        .then(r => (r.ok ? r.json() : Promise.reject(new Error(`HTTP ${r.status}`))))
        .then((body: MapPayload) => {
          if (cancelled) return
          if (!body || !Array.isArray(body.projects) || !body.counts || !body.sources) throw new Error('shape')
          setPayload(body)
          setFailed(false)
        })
        .catch(() => { if (!cancelled) setFailed(true) })
    }
    read()
    const timer = window.setInterval(read, open ? OPEN_INTERVAL_MS : CLOSED_INTERVAL_MS)
    return () => { cancelled = true; window.clearInterval(timer) }
  }, [open])

  const setDock = useCallback((next: Dock) => {
    setDockState(next)
    try { window.localStorage.setItem(DOCK_KEY, next) } catch { /* the choice lasts for this page only */ }
  }, [])

  const summary = openerSummary(payload, failed)
  return (
    <>
      <button
        onClick={() => setOpen(o => !o)}
        aria-pressed={open}
        aria-label={`relation map ${open ? 'open' : 'closed'}`}
        data-fleet-map-toggle={open ? 'on' : 'off'}
        data-fleet-map-read={summary.kind}
        title={summary.kind === 'asking' ? 'Relation map — reading…' : summary.title}
        className={`flex items-center gap-1.5 px-1.5 py-1 rounded border shrink-0 text-xs tabular-nums ${
          open ? 'border-sky-400/60 bg-sky-400/10 text-sky-300' : 'border-surface-line text-fg-muted hover:text-fg-strong'
        }`}
      >
        <Waypoints size={13} strokeWidth={1.75} />
        {summary.kind === 'unread' && <span className="text-amber-400" data-fleet-map-count="unread">map ?</span>}
        {summary.kind === 'read' && (
          <>
            {summary.noMandate > 0 && (
              <span className="text-amber-400" data-fleet-map-count="no-mandate">{summary.noMandate} no mandate</span>
            )}
            {summary.waiting > 0 && (
              <span className="text-amber-400" data-fleet-map-count="waiting">{summary.waiting} waiting</span>
            )}
            {summary.failed > 0 && (
              <span className="text-red-400" data-fleet-map-count="failed">{summary.failed} failed</span>
            )}
            {summary.unmeasured && <span className="text-amber-400" data-fleet-map-count="unmeasured">?</span>}
          </>
        )}
      </button>
      {open && (
        <FleetMapPanel payload={payload} stale={failed} dock={dock} onDock={setDock} onClose={() => setOpen(false)} />
      )}
    </>
  )
}
