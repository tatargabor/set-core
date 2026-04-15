import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import {
  Background,
  Controls,
  ReactFlow,
  ReactFlowProvider,
  useEdgesState,
  useNodesState,
  useReactFlow,
  type Node as RFNode,
} from '@xyflow/react'
import '@xyflow/react/dist/style.css'
import './dag/dag.css'
import {
  getChangeJournal,
  getChangeTimeline,
  type ChangeJournal,
  type ChangeTimelineData,
} from '../lib/api'
import { journalToAttemptGraph } from '../lib/dag/journalToAttemptGraph'
import { enrichWithSessions } from '../lib/dag/enrichWithSessions'
import { layoutAttemptGraph } from '../lib/dag/layout'
import type { AttemptGraph, AttemptNode } from '../lib/dag/types'
import ChangeTimelineDetail from './ChangeTimelineDetail'
import DagToolbar from './dag/DagToolbar'
import DagDetailPanel from './dag/DagDetailPanel'
import GateNode from './dag/GateNode'
import ImplNode from './dag/ImplNode'
import TerminalNode from './dag/TerminalNode'

interface Props {
  project: string
  changeName: string
  autoFollow: boolean
  onAutoFollowChange: (value: boolean) => void
}

const NODE_TYPES = {
  gate: GateNode,
  impl: ImplNode,
  terminal: TerminalNode,
}

const EMPTY_GRAPH: AttemptGraph = {
  attempts: [],
  terminal: 'in-progress',
  totalMs: 0,
  totalGateRuns: 0,
}

interface InnerProps {
  layout: { nodes: RFNode[]; edges: import('@xyflow/react').Edge[] }
  onNodeClick: (_: unknown, node: RFNode) => void
  autoFollow: boolean
  changeName: string
}

// DAG row stride in layout coordinates (see lib/dag/layout.ts: rowHeight +
// attemptGap = 130 + 20 = 150). Two bounds shape the default viewport:
//   - MAX_ROWS_VISIBLE caps zoom-in when there is only one attempt (no
//     point in stretching one row to fill a 900px canvas).
//   - MIN_READABLE_ZOOM floors zoom-out for long histories. Without this
//     floor, a change with 14 attempts rendered every row visible but at
//     zoom~0.19, which turned every node into an unreadable smudge.
// When the floor wins, we pan so the LAST attempt sits at the bottom of
// the canvas (most recent work is what the user wants to see first; older
// rows stay reachable by scrolling up with the mouse wheel).
const ROW_STRIDE_PX = 150
const MAX_ROWS_VISIBLE = 2.5
// Hard floor. At zoom < 1.0 the gate-node text becomes smudgy and the user
// cannot read which gate is which. Raised explicitly — the previous 0.7
// still let ReactFlow's built-in fitView squeeze 8 rows into 640px at
// ~0.53 zoom, which is exactly the illegible-smudge case we're preventing.
const MIN_READABLE_ZOOM = 1.0

function DagCanvas({ layout, onNodeClick, autoFollow, changeName }: InnerProps) {
  const [nodes, setNodes, onNodesChange] = useNodesState(layout.nodes)
  const [edges, setEdges, onEdgesChange] = useEdgesState(layout.edges)
  const rfApi = useReactFlow()
  const { fitView, setViewport, getViewport, setCenter } = rfApi
  const containerRef = useRef<HTMLDivElement | null>(null)
  // Initialize to '' (not the current layout's id-set) so the very first
  // effect tick sees `prevIdSet !== newIdSet` → wasEmpty=true → pendingFit=true.
  // Previous bug: initializing to the layout's id-set made the first effect
  // tick no-op; combined with removing ReactFlow's `fitView` prop, it left
  // the canvas at the default (0,0) viewport — top-anchored, left-hugged.
  const nodeIdSetRef = useRef<string>('')
  const lastFitChangeRef = useRef<string>(changeName)
  const pendingFitRef = useRef<boolean>(false)

  // Pass 1: push the new layout into React Flow's internal state and flag a
  // pending fit when appropriate. The fit itself runs in pass 2 once RF has
  // actually committed the new node positions — otherwise fitView() would
  // operate on the stale node set.
  useEffect(() => {
    setNodes(layout.nodes)
    setEdges(layout.edges)
    const prevIdSet = nodeIdSetRef.current
    const newIdSet = layout.nodes.map((n) => n.id).sort().join(',')
    const idSetChanged = newIdSet !== prevIdSet
    nodeIdSetRef.current = newIdSet
    if (!idSetChanged || layout.nodes.length === 0) return
    // idSetChanged bundles three distinct triggers:
    //   A) mid-run inside the current change — a new gate/attempt arrived.
    //      Fit only when autoFollow is on (manual mode keeps the user's pan).
    //   B) first data arrival after the canvas mounted empty — always fit
    //      so the DAG doesn't sit at RF's default offset.
    //   C) change switch — the selected change just changed under us. Always
    //      fit because a fresh DAG at the previous change's viewport is
    //      almost certainly clipped off-screen ("kilog"), and the user
    //      clicked a different row on purpose.
    const isChangeSwitch = changeName !== lastFitChangeRef.current
    const wasEmpty = prevIdSet === ''
    if (autoFollow || isChangeSwitch || wasEmpty) {
      pendingFitRef.current = true
    }
  }, [layout, setNodes, setEdges, autoFollow, changeName])

  // Core fit routine: zoom + pan so the last MAX_ROWS_VISIBLE attempt rows
  // sit at the bottom of the canvas, horizontally centered. Invoked from
  // both onInit (first paint) and the useEffect below (layout change).
  const runBottomAnchorFit = useCallback(() => {
    if (nodes.length === 0) return
    const container = containerRef.current
    if (!container) {
      fitView({ duration: 300, padding: 0.15 })
      return
    }
    const h = container.clientHeight || 400
    type RFGeom = {
      position?: { x: number; y: number }
      width?: number
      height?: number
      measured?: { width?: number; height?: number }
    }
    const geom = (nodes as unknown as RFGeom[]).map((n) => ({
      x: n.position?.x ?? 0,
      y: n.position?.y ?? 0,
      w: n.measured?.width ?? n.width ?? 150,
      h: n.measured?.height ?? n.height ?? 100,
    }))
    if (geom.length === 0) {
      fitView({ duration: 300, padding: 0.15 })
      return
    }
    const sortedYs = [...new Set(geom.map((g) => g.y))].sort((a, b) => a - b)
    const rowsToShow = Math.max(1, Math.floor(MAX_ROWS_VISIBLE))
    const visibleYs = sortedYs.slice(-rowsToShow)
    const visible = geom.filter((g) => visibleYs.includes(g.y))
    const minX = Math.min(...visible.map((g) => g.x))
    const maxX = Math.max(...visible.map((g) => g.x + g.w))
    const minYvis = Math.min(...visible.map((g) => g.y))
    const maxY = Math.max(...visible.map((g) => g.y + g.h))
    const bounds = {
      x: minX,
      y: minYvis,
      width: Math.max(1, maxX - minX),
      height: Math.max(1, maxY - minYvis),
    }
    const idealZoom = h / (MAX_ROWS_VISIBLE * ROW_STRIDE_PX)
    const cappedZoom = Math.min(1.2, Math.max(MIN_READABLE_ZOOM, idealZoom))
    rfApi.fitBounds(bounds, { duration: 300, padding: 0.08 })
    window.setTimeout(() => {
      const vp = getViewport()
      if (Math.abs(vp.zoom - cappedZoom) > 0.02 && vp.zoom < cappedZoom) {
        const cx = (minX + maxX) / 2
        const cy = (minYvis + maxY) / 2
        setCenter(cx, cy, { zoom: cappedZoom, duration: 200 })
      }
    }, 340)
  }, [nodes, fitView, getViewport, setCenter, rfApi])

  // Pass 2: fire the fit whenever pendingFitRef was set AND nodes have
  // committed. onInit fires this for the initial mount; this effect
  // handles subsequent layout changes (new attempts, change switch, etc.).
  useEffect(() => {
    if (!pendingFitRef.current || nodes.length === 0) return
    pendingFitRef.current = false
    lastFitChangeRef.current = changeName
    const id = window.setTimeout(() => runBottomAnchorFit(), 60)
    return () => window.clearTimeout(id)
  }, [nodes, changeName, runBottomAnchorFit])

  return (
    <div ref={containerRef} className="w-full h-full">
      <ReactFlow
        nodes={nodes}
        edges={edges}
        onNodesChange={onNodesChange}
        onEdgesChange={onEdgesChange}
        onNodeClick={onNodeClick}
        nodeTypes={NODE_TYPES}
        // NO `fitView` prop — ReactFlow's built-in fit ignores our readable-
        // zoom floor. Instead we fire our own fitBounds from onInit (which
        // runs exactly when the RF instance is ready — no 60ms guess), and
        // again from the useEffect below whenever the layout changes.
        onInit={() => {
          pendingFitRef.current = true
          // Yield one frame so node sizes are measured before we compute
          // bounds. Without this yield, n.measured is undefined and the
          // fallback heights (100px) get used — usually correct but brittle.
          requestAnimationFrame(() => runBottomAnchorFit())
        }}
        minZoom={0.3}
        maxZoom={2}
        nodesDraggable={false}
        nodesConnectable={false}
        proOptions={{ hideAttribution: true }}
      >
        <Background gap={20} color="#262626" />
        <Controls showInteractive={false} position="bottom-left" />
      </ReactFlow>
    </div>
  )
}

export default function ChangeDagPanel({ project, changeName, autoFollow, onAutoFollowChange }: Props) {
  const [journal, setJournal] = useState<ChangeJournal | null>(null)
  const [timeline, setTimeline] = useState<ChangeTimelineData | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [viewMode, setViewMode] = useState<'dag' | 'linear'>('dag')
  const [selectedNodeId, setSelectedNodeId] = useState<string | null>(null)

  useEffect(() => {
    let cancelled = false
    // Reset per-change state on every change switch so the graph/layout
    // memos drop to EMPTY_GRAPH immediately. This makes the "wasEmpty"
    // trigger in DagCanvas fire reliably when the new journal arrives,
    // and avoids a flicker where the old change's DAG is briefly
    // rendered at the new change's viewport during the async fetch.
    setJournal(null)
    setTimeline(null)
    setError(null)
    const load = () => {
      getChangeJournal(project, changeName)
        .then((d) => {
          if (cancelled) return
          setJournal(d)
          setError(null)
        })
        .catch((e) => {
          if (cancelled) return
          // Old servers without the /journal endpoint return the SPA
          // index.html, which makes res.json() throw with "Unexpected
          // token '<'". That path is indistinguishable from "no journal
          // data" from the user's perspective — surface it as the empty
          // state, not a red error banner. Explicit 4xx/5xx with a JSON
          // body (or the fetcher's explicit "HTTP N" message) still
          // shows the error banner so real problems stay visible.
          const msg = e instanceof Error ? e.message : String(e)
          const looksLikeSpaFallback =
            msg.includes("Unexpected token '<'") ||
            msg.includes('is not valid JSON')
          if (looksLikeSpaFallback) {
            setJournal({ entries: [], grouped: {} })
            setError(null)
          } else {
            setError(msg)
          }
        })
      // /timeline carries per-session model + token info that the journal
      // doesn't. Failure here is non-fatal — nodes just miss the 4th line.
      getChangeTimeline(project, changeName)
        .then((d) => {
          if (cancelled) return
          setTimeline(d)
        })
        .catch(() => {
          if (cancelled) return
          setTimeline(null)
        })
    }
    load()
    const iv = setInterval(load, 10000)
    return () => {
      cancelled = true
      clearInterval(iv)
    }
  }, [project, changeName])

  const graph = useMemo<AttemptGraph>(() => {
    if (!journal) return EMPTY_GRAPH
    try {
      const g = journalToAttemptGraph(journal.entries)
      if (timeline?.sessions) {
        enrichWithSessions(g, timeline.sessions)
      }
      return g
    } catch (err) {
      console.error('journalToAttemptGraph failed for', changeName, err, journal.entries)
      return EMPTY_GRAPH
    }
  }, [journal, timeline, changeName])

  const layout = useMemo(() => layoutAttemptGraph(graph), [graph])

  const selectedNode = useMemo<AttemptNode | null>(() => {
    if (!selectedNodeId) return null
    for (const attempt of graph.attempts) {
      for (const node of attempt.nodes) {
        if (node.id === selectedNodeId) return node
      }
    }
    return null
  }, [graph, selectedNodeId])

  const onNodeClick = useCallback(
    (_: unknown, node: RFNode) => {
      setSelectedNodeId((prev) => (prev === node.id ? null : node.id))
    },
    [],
  )

  const toolbar = (
    <DagToolbar
      attemptCount={graph.attempts.length}
      totalDurationMs={graph.totalMs}
      totalGateRuns={graph.totalGateRuns}
      viewMode={viewMode}
      onViewModeChange={setViewMode}
      autoFollow={autoFollow}
      onAutoFollowChange={onAutoFollowChange}
    />
  )

  if (error && !journal) {
    return (
      <div className="h-full flex flex-col">
        {toolbar}
        <div className="flex-1 flex items-center justify-center p-6">
          <div className="max-w-sm rounded border border-red-700/40 bg-red-900/20 p-4 text-sm text-red-300">
            <div className="font-medium mb-1">Failed to load journal for {changeName}</div>
            <div className="text-xs text-red-400/80">{error}</div>
            <button
              onClick={() => setViewMode('linear')}
              className="mt-3 px-2 py-1 text-xs rounded bg-neutral-800 text-neutral-200 hover:bg-neutral-700"
            >
              Switch to Linear view
            </button>
          </div>
        </div>
      </div>
    )
  }

  if (viewMode === 'linear') {
    return (
      <div className="h-full flex flex-col">
        {toolbar}
        <div className="flex-1 overflow-auto">
          <ChangeTimelineDetail project={project} changeName={changeName} />
        </div>
      </div>
    )
  }

  if (graph.attempts.length === 0) {
    return (
      <div className="h-full flex flex-col">
        {toolbar}
        <div className="flex-1 flex items-center justify-center p-6">
          <div className="max-w-sm rounded border border-neutral-800 bg-neutral-900/50 p-4 text-center">
            <div className="text-sm text-neutral-300 mb-1">No journal data for this change yet</div>
            <div className="text-xs text-neutral-500 mb-3">
              The DAG fills in as gates run. Switch to Linear view to see session cards.
            </div>
            <button
              onClick={() => setViewMode('linear')}
              className="px-2.5 py-1 text-xs rounded bg-neutral-800 text-neutral-200 hover:bg-neutral-700"
            >
              Switch to Linear view
            </button>
          </div>
        </div>
      </div>
    )
  }

  return (
    <div className="h-full flex flex-col">
      {toolbar}
      <div className="flex-1 min-h-0 relative">
        <ReactFlowProvider>
          <DagCanvas
            layout={layout}
            onNodeClick={onNodeClick}
            autoFollow={autoFollow}
            changeName={changeName}
          />
        </ReactFlowProvider>
      </div>
      <DagDetailPanel node={selectedNode} onClose={() => setSelectedNodeId(null)} />
    </div>
  )
}
