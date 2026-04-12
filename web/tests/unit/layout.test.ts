import { describe, expect, it } from 'vitest'
import { DEFAULT_LAYOUT, layoutAttemptGraph } from '../../src/lib/dag/layout'
import type { AttemptGraph } from '../../src/lib/dag/types'

function buildGraph(override: Partial<AttemptGraph> = {}): AttemptGraph {
  return {
    attempts: [],
    terminal: 'in-progress',
    totalMs: 0,
    totalGateRuns: 0,
    ...override,
  }
}

describe('layoutAttemptGraph', () => {
  it('one attempt with 3 gates produces 4 nodes at expected x positions', () => {
    const graph = buildGraph({
      attempts: [
        {
          n: 1,
          startedAt: 't0',
          endedAt: null,
          outcome: 'in-progress',
          nodes: [
            {
              id: 'a1-impl',
              attempt: 1,
              kind: 'impl',
              runIndexForKind: 1,
              result: 'pass',
              ms: 1000,
              startedAt: 't0',
              endedAt: 't1',
            },
            {
              id: 'a1-build-1',
              attempt: 1,
              kind: 'build',
              runIndexForKind: 1,
              result: 'pass',
              ms: 2000,
              startedAt: 't1',
              endedAt: 't2',
            },
            {
              id: 'a1-test-1',
              attempt: 1,
              kind: 'test',
              runIndexForKind: 1,
              result: 'pass',
              ms: 3000,
              startedAt: 't2',
              endedAt: 't3',
            },
            {
              id: 'a1-e2e-1',
              attempt: 1,
              kind: 'e2e',
              runIndexForKind: 1,
              result: 'running',
              ms: null,
              startedAt: 't3',
              endedAt: null,
            },
          ],
        },
      ],
    })
    const { nodes, edges } = layoutAttemptGraph(graph)
    expect(nodes).toHaveLength(4)
    for (let j = 0; j < 4; j++) {
      const expectedX =
        DEFAULT_LAYOUT.leftMargin + j * (DEFAULT_LAYOUT.nodeWidth + DEFAULT_LAYOUT.columnGap)
      expect(nodes[j].position.x).toBe(expectedX)
      expect(nodes[j].position.y).toBe(DEFAULT_LAYOUT.topMargin)
    }
    // happy edges between j and j+1 = 3 edges
    expect(edges).toHaveLength(3)
  })

  it('three attempts stack on y axis', () => {
    const graph = buildGraph({
      attempts: [1, 2, 3].map((n) => ({
        n,
        startedAt: `t${n}`,
        endedAt: null,
        outcome: n < 3 ? 'retry' : 'merged',
        retryReason: n < 3 ? 'gate-fail' : undefined,
        nodes: [
          {
            id: `a${n}-impl`,
            attempt: n,
            kind: 'impl',
            runIndexForKind: n,
            result: 'pass',
            ms: 1000,
            startedAt: `t${n}`,
            endedAt: `t${n}b`,
          },
          {
            id: `a${n}-build-${n}`,
            attempt: n,
            kind: 'build',
            runIndexForKind: n,
            result: n < 3 ? 'fail' : 'pass',
            ms: 2000,
            startedAt: `t${n}b`,
            endedAt: `t${n}c`,
          },
        ],
      })),
      terminal: 'merged',
    })
    const { nodes, edges } = layoutAttemptGraph(graph)
    const byAttempt: Record<number, number> = {}
    for (const n of nodes) {
      if (typeof n.position.y === 'number') {
        byAttempt[n.position.y] = (byAttempt[n.position.y] ?? 0) + 1
      }
    }
    const ys = Object.keys(byAttempt).map(Number).sort((a, b) => a - b)
    // 3 attempt rows (terminal node is added onto the last row, same y)
    expect(ys).toHaveLength(3)
    expect(ys[0]).toBe(DEFAULT_LAYOUT.topMargin)
    expect(ys[1]).toBe(DEFAULT_LAYOUT.topMargin + 1 * (DEFAULT_LAYOUT.rowHeight + DEFAULT_LAYOUT.attemptGap))
    expect(ys[2]).toBe(DEFAULT_LAYOUT.topMargin + 2 * (DEFAULT_LAYOUT.rowHeight + DEFAULT_LAYOUT.attemptGap))
    // retry edges: 2 (between attempt 1→2 and 2→3)
    const retryEdges = edges.filter((e) => e.id.includes('retry'))
    expect(retryEdges).toHaveLength(2)
  })

  it('retry edge uses source bottom handle and target top handle', () => {
    const graph = buildGraph({
      attempts: [
        {
          n: 1,
          startedAt: 't0',
          endedAt: 't1',
          outcome: 'retry',
          retryReason: 'gate-fail',
          nodes: [
            {
              id: 'a1-impl',
              attempt: 1,
              kind: 'impl',
              runIndexForKind: 1,
              result: 'pass',
              ms: 1000,
              startedAt: 't0',
              endedAt: 't1',
            },
            {
              id: 'a1-build-1',
              attempt: 1,
              kind: 'build',
              runIndexForKind: 1,
              result: 'fail',
              ms: 2000,
              startedAt: 't1',
              endedAt: 't2',
            },
          ],
        },
        {
          n: 2,
          startedAt: 't3',
          endedAt: null,
          outcome: 'in-progress',
          nodes: [
            {
              id: 'a2-impl',
              attempt: 2,
              kind: 'impl',
              runIndexForKind: 2,
              result: 'running',
              ms: 500,
              startedAt: 't3',
              endedAt: null,
            },
          ],
        },
      ],
    })
    const { edges } = layoutAttemptGraph(graph)
    const retry = edges.find((e) => e.id.includes('retry'))
    expect(retry).toBeDefined()
    expect(retry!.sourceHandle).toBe('bottom')
    expect(retry!.targetHandle).toBe('top')
    expect(retry!.type).toBe('smoothstep')
  })

  it('merged graph adds terminal node with incoming edge', () => {
    const graph = buildGraph({
      attempts: [
        {
          n: 1,
          startedAt: 't0',
          endedAt: 't2',
          outcome: 'merged',
          nodes: [
            {
              id: 'a1-impl',
              attempt: 1,
              kind: 'impl',
              runIndexForKind: 1,
              result: 'pass',
              ms: 1000,
              startedAt: 't0',
              endedAt: 't1',
            },
            {
              id: 'a1-build-1',
              attempt: 1,
              kind: 'build',
              runIndexForKind: 1,
              result: 'pass',
              ms: 2000,
              startedAt: 't1',
              endedAt: 't2',
            },
          ],
        },
      ],
      terminal: 'merged',
    })
    const { nodes, edges } = layoutAttemptGraph(graph)
    const terminal = nodes.find((n) => n.id === 'terminal-merged')
    expect(terminal).toBeDefined()
    expect(terminal!.type).toBe('terminal')
    const terminalEdge = edges.find((e) => e.target === 'terminal-merged')
    expect(terminalEdge).toBeDefined()
    expect(terminalEdge!.source).toBe('a1-build-1')
  })

  it('in-progress graph has no terminal node', () => {
    const graph = buildGraph({
      attempts: [
        {
          n: 1,
          startedAt: 't0',
          endedAt: null,
          outcome: 'in-progress',
          nodes: [
            {
              id: 'a1-impl',
              attempt: 1,
              kind: 'impl',
              runIndexForKind: 1,
              result: 'running',
              ms: 1000,
              startedAt: 't0',
              endedAt: null,
            },
          ],
        },
      ],
      terminal: 'in-progress',
    })
    const { nodes } = layoutAttemptGraph(graph)
    const terminal = nodes.find((n) => n.type === 'terminal')
    expect(terminal).toBeUndefined()
  })

  it('custom constants override defaults', () => {
    const graph = buildGraph({
      attempts: [
        {
          n: 1,
          startedAt: 't0',
          endedAt: null,
          outcome: 'in-progress',
          nodes: [
            {
              id: 'a1-impl',
              attempt: 1,
              kind: 'impl',
              runIndexForKind: 1,
              result: 'pass',
              ms: 1000,
              startedAt: 't0',
              endedAt: 't1',
            },
          ],
        },
      ],
    })
    const { nodes } = layoutAttemptGraph(graph, { leftMargin: 100, topMargin: 50 })
    expect(nodes[0].position.x).toBe(100)
    expect(nodes[0].position.y).toBe(50)
  })
})
