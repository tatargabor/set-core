import type { Edge, Node } from '@xyflow/react'
import type { AttemptGraph, AttemptNode, RetryReason } from './types'

export interface LayoutConstants {
  nodeWidth: number
  nodeHeight: number
  columnGap: number
  rowHeight: number
  attemptGap: number
  leftMargin: number
  topMargin: number
}

export const DEFAULT_LAYOUT: LayoutConstants = {
  nodeWidth: 150,
  nodeHeight: 100,
  columnGap: 30,
  rowHeight: 130,
  attemptGap: 20,
  leftMargin: 20,
  topMargin: 20,
}

const RETRY_EDGE_COLORS: Record<RetryReason, string> = {
  'gate-fail': '#f59e0b',
  'merge-conflict': '#f97316',
  replan: '#a78bfa',
  'reset-failed': '#ec4899',
  unknown: '#737373',
}

function rfTypeFromKind(kind: AttemptNode['kind']): string {
  if (kind === 'impl') return 'impl'
  if (kind === 'terminal') return 'terminal'
  return 'gate'
}

export function layoutAttemptGraph(
  graph: AttemptGraph,
  constants: Partial<LayoutConstants> = {},
): { nodes: Node[]; edges: Edge[] } {
  const c: LayoutConstants = { ...DEFAULT_LAYOUT, ...constants }
  const nodes: Node[] = []
  const edges: Edge[] = []

  const attemptCount = graph.attempts.length
  for (let k = 0; k < attemptCount; k++) {
    const attempt = graph.attempts[k]
    const y = c.topMargin + k * (c.rowHeight + c.attemptGap)
    for (let j = 0; j < attempt.nodes.length; j++) {
      const node = attempt.nodes[j]
      const x = c.leftMargin + j * (c.nodeWidth + c.columnGap)
      nodes.push({
        id: node.id,
        type: rfTypeFromKind(node.kind),
        position: { x, y },
        data: node as unknown as Record<string, unknown>,
        draggable: false,
        selectable: true,
      })
      if (j > 0) {
        const prev = attempt.nodes[j - 1]
        edges.push({
          id: `${prev.id}->${node.id}`,
          source: prev.id,
          target: node.id,
          type: 'default',
          style: { stroke: '#737373', strokeWidth: 1.5 },
        })
      }
    }
  }

  for (let k = 0; k < attemptCount - 1; k++) {
    const attempt = graph.attempts[k]
    const nextAttempt = graph.attempts[k + 1]
    const lastNode = attempt.nodes[attempt.nodes.length - 1]
    const firstNextNode = nextAttempt.nodes[0]
    if (!lastNode || !firstNextNode) continue
    if (attempt.outcome !== 'retry') continue
    const reason: RetryReason = attempt.retryReason ?? 'unknown'
    const color = RETRY_EDGE_COLORS[reason]
    edges.push({
      id: `${lastNode.id}->retry->${firstNextNode.id}`,
      source: lastNode.id,
      target: firstNextNode.id,
      sourceHandle: 'bottom',
      targetHandle: 'top',
      type: 'smoothstep',
      label: reason === 'merge-conflict' ? 'conflict' : 'retry',
      style: { stroke: color, strokeWidth: 2 },
      labelStyle: { fill: color, fontSize: 10 },
      labelBgStyle: { fill: '#171717' },
    })
  }

  if (attemptCount > 0 && (graph.terminal === 'merged' || graph.terminal === 'failed')) {
    const lastAttempt = graph.attempts[attemptCount - 1]
    const lastNode = lastAttempt.nodes[lastAttempt.nodes.length - 1]
    if (lastNode) {
      const terminalId = `terminal-${graph.terminal}`
      const lastX = c.leftMargin + lastAttempt.nodes.length * (c.nodeWidth + c.columnGap)
      const lastY = c.topMargin + (attemptCount - 1) * (c.rowHeight + c.attemptGap)
      nodes.push({
        id: terminalId,
        type: 'terminal',
        position: { x: lastX, y: lastY },
        data: {
          terminal: graph.terminal,
          attemptNumber: lastAttempt.n,
          totalMs: graph.totalMs,
        },
        draggable: false,
        selectable: false,
      })
      edges.push({
        id: `${lastNode.id}->${terminalId}`,
        source: lastNode.id,
        target: terminalId,
        type: 'default',
        style: {
          stroke: graph.terminal === 'merged' ? '#22c55e' : '#ef4444',
          strokeWidth: 2,
        },
      })
    }
  }

  return { nodes, edges }
}
