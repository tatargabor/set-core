import type { TimelineSession } from '../api'
import type { AttemptGraph, AttemptNode, GateKind } from './types'

/** Match a session label to a gate kind. Returns null if the label looks
 * like a plain impl session. Labels come from the ralph loop session
 * metadata — user-visible strings like "Review", "Spec Verify", etc. */
function labelToGateKind(label?: string): GateKind | null {
  if (!label) return null
  const l = label.toLowerCase()
  if (l.includes('review')) return 'review'
  if (l.includes('spec verify') || l.includes('scope')) return 'scope_check'
  if (l.includes('rules')) return 'rules'
  if (l.includes('e2e coverage')) return 'e2e_coverage'
  if (l.includes('smoke')) return 'smoke'
  // "Task", "Planning", "Fixing", "" — all belong to impl work
  return null
}

function parseTs(ts: string): number {
  const n = Date.parse(ts)
  return Number.isNaN(n) ? 0 : n
}

/** Mutates nodes in the passed graph in place, adding model/token fields
 * where a matching timeline session exists. Returns the same graph for
 * fluent chaining. Session→node matching strategy:
 *
 *  - For each attempt, take sessions whose `started` timestamp falls
 *    within the attempt's [startedAt, endedAt] window.
 *  - Label-tagged sessions route to a gate node by labelToGateKind().
 *  - Untagged sessions aggregate into the impl node for that attempt.
 */
export function enrichWithSessions(
  graph: AttemptGraph,
  sessions: TimelineSession[],
): AttemptGraph {
  if (!sessions || sessions.length === 0) return graph

  for (const attempt of graph.attempts) {
    const start = parseTs(attempt.startedAt)
    const end = attempt.endedAt ? parseTs(attempt.endedAt) : Date.now()

    const inWindow = sessions.filter((s) => {
      const t = parseTs(s.started)
      return t >= start - 2000 && t <= end + 2000
    })
    if (inWindow.length === 0) continue

    // Buckets: impl (aggregate) vs gate-kind buckets
    const implBucket: TimelineSession[] = []
    const gateBuckets = new Map<GateKind, TimelineSession>()
    for (const s of inWindow) {
      const kind = labelToGateKind(s.label)
      if (kind) {
        // If multiple, keep the latest (most-recent mtime)
        const existing = gateBuckets.get(kind)
        if (!existing || parseTs(s.started) > parseTs(existing.started)) {
          gateBuckets.set(kind, s)
        }
      } else {
        implBucket.push(s)
      }
    }

    // Attach impl aggregate
    const implNode = attempt.nodes.find((n) => n.kind === 'impl')
    if (implNode && implBucket.length > 0) {
      implNode.inputTokens = sum(implBucket.map((s) => s.input_tokens))
      implNode.outputTokens = sum(implBucket.map((s) => s.output_tokens))
      implNode.cacheTokens = sum(implBucket.map((s) => s.cache_read_tokens))
      implNode.model = pickMajorityModel(implBucket)
    }

    // Attach gate sessions
    for (const [kind, s] of gateBuckets.entries()) {
      const node = findNode(attempt.nodes, kind)
      if (!node) continue
      node.inputTokens = s.input_tokens ?? 0
      node.outputTokens = s.output_tokens ?? 0
      node.cacheTokens = s.cache_read_tokens ?? 0
      node.model = s.model
    }
  }

  return graph
}

function sum(vals: Array<number | undefined>): number {
  let total = 0
  for (const v of vals) total += v ?? 0
  return total
}

function pickMajorityModel(sessions: TimelineSession[]): string | undefined {
  const counts = new Map<string, number>()
  for (const s of sessions) {
    if (!s.model) continue
    counts.set(s.model, (counts.get(s.model) ?? 0) + 1)
  }
  if (counts.size === 0) return undefined
  let best: string | undefined
  let bestCount = 0
  for (const [model, count] of counts) {
    if (count > bestCount) {
      best = model
      bestCount = count
    }
  }
  return best
}

function findNode(nodes: AttemptNode[], kind: GateKind): AttemptNode | undefined {
  // Latest run of the given kind within the attempt (last-wins).
  for (let i = nodes.length - 1; i >= 0; i--) {
    if (nodes[i].kind === kind) return nodes[i]
  }
  return undefined
}
