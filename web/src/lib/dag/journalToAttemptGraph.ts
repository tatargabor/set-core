import type { JournalEntry } from '../api'
import type {
  Attempt,
  AttemptGraph,
  AttemptNode,
  GateKind,
  GateResult,
  VerdictSidecar,
} from './types'

const GATE_KINDS: ReadonlyArray<Exclude<GateKind, 'impl' | 'terminal'>> = [
  'build',
  'test',
  'e2e',
  'review',
  'smoke',
  'scope_check',
  'rules',
  'e2e_coverage',
  'merge',
]

const MS_WINDOW = 2000

function parseTs(ts: string): number {
  const n = Date.parse(ts)
  return Number.isNaN(n) ? 0 : n
}

function resultFieldToKind(field: string): GateKind | null {
  if (!field.endsWith('_result')) return null
  const kind = field.slice(0, -'_result'.length)
  return (GATE_KINDS as ReadonlyArray<string>).includes(kind) ? (kind as GateKind) : null
}

function outputFieldToKind(field: string): GateKind | null {
  if (!field.endsWith('_output')) return null
  const kind = field.slice(0, -'_output'.length)
  return (GATE_KINDS as ReadonlyArray<string>).includes(kind) ? (kind as GateKind) : null
}

function msFieldToKind(field: string): GateKind | null {
  if (!field.startsWith('gate_') || !field.endsWith('_ms')) return null
  const kind = field.slice('gate_'.length, -'_ms'.length)
  return (GATE_KINDS as ReadonlyArray<string>).includes(kind) ? (kind as GateKind) : null
}

function normalizeResult(raw: unknown): GateResult {
  if (raw === null || raw === undefined) return null
  if (typeof raw !== 'string') return null
  const lower = raw.toLowerCase()
  if (lower === 'pass' || lower === 'passed' || lower === 'success') return 'pass'
  if (lower === 'fail' || lower === 'failed' || lower === 'conflict') return 'fail'
  if (lower === 'warn' || lower === 'warning') return 'warn'
  if (lower === 'skip' || lower === 'skipped') return 'skip'
  if (lower === 'running' || lower === 'in_progress' || lower === 'in-progress') return 'running'
  return null
}

function pickClosest<T extends { _ts: number }>(
  candidates: T[],
  targetTs: number,
  windowMs = MS_WINDOW,
): T | null {
  let best: T | null = null
  let bestDelta = windowMs
  for (const c of candidates) {
    const delta = Math.abs(c._ts - targetTs)
    if (delta <= bestDelta) {
      best = c
      bestDelta = delta
    }
  }
  return best
}

export function journalToAttemptGraph(
  entries: JournalEntry[],
  verdictSidecars?: VerdictSidecar[],
): AttemptGraph {
  const sorted = [...entries].sort((a, b) => {
    const ta = parseTs(a.ts)
    const tb = parseTs(b.ts)
    if (ta !== tb) return ta - tb
    return (a.seq ?? 0) - (b.seq ?? 0)
  })

  const outputsByKind = new Map<GateKind, Array<{ _ts: number; value: string }>>()
  const msByKind = new Map<GateKind, Array<{ _ts: number; value: number }>>()
  for (const e of sorted) {
    const ok = outputFieldToKind(e.field)
    if (ok) {
      const list = outputsByKind.get(ok) ?? []
      const val = typeof e.new === 'string' ? e.new : ''
      list.push({ _ts: parseTs(e.ts), value: val })
      outputsByKind.set(ok, list)
      continue
    }
    const mk = msFieldToKind(e.field)
    if (mk) {
      const list = msByKind.get(mk) ?? []
      const val = typeof e.new === 'number' ? e.new : Number(e.new) || 0
      list.push({ _ts: parseTs(e.ts), value: val })
      msByKind.set(mk, list)
    }
  }

  const attempts: Attempt[] = []
  const runIndexByKind = new Map<GateKind, number>()
  let terminal: AttemptGraph['terminal'] = 'in-progress'

  function openNewAttempt(startTs: string): Attempt {
    const n = attempts.length + 1
    const attempt: Attempt = {
      n,
      startedAt: startTs,
      endedAt: null,
      outcome: 'in-progress',
      nodes: [],
    }
    attempts.push(attempt)
    return attempt
  }

  function closeAttemptOnRetry(attempt: Attempt, ts: string): void {
    attempt.endedAt = ts
    attempt.outcome = 'retry'
    const lastNode = attempt.nodes[attempt.nodes.length - 1]
    if (lastNode && lastNode.kind === 'merge' && lastNode.result === 'fail') {
      attempt.retryReason = 'merge-conflict'
    } else if (attempt.nodes.some((n) => n.result === 'fail')) {
      attempt.retryReason = 'gate-fail'
    } else {
      attempt.retryReason = 'unknown'
    }
  }

  function current(): Attempt | null {
    return attempts.length > 0 ? attempts[attempts.length - 1] : null
  }

  let pendingRetry = false

  for (const e of sorted) {
    if (e.field === 'status') {
      const value = typeof e.new === 'string' ? e.new : ''
      const cur = current()
      if (value === 'running') {
        if (!cur) {
          openNewAttempt(e.ts)
        } else if (pendingRetry) {
          closeAttemptOnRetry(cur, e.ts)
          openNewAttempt(e.ts)
          pendingRetry = false
        } else if (cur.outcome === 'failed' || cur.outcome === 'merged') {
          // Reset cycle: previous attempt reached a terminal state and is
          // now being redispatched (e.g. via reset_failed). Close history,
          // open a fresh attempt, and re-arm the terminal flag so the new
          // run isn't pre-stamped with the prior outcome.
          cur.retryReason = 'reset-failed'
          openNewAttempt(e.ts)
          terminal = 'in-progress'
        }
      } else if (value === 'verify-failed') {
        pendingRetry = true
      } else if (value === 'merged') {
        terminal = 'merged'
        if (cur) {
          cur.endedAt = e.ts
          cur.outcome = 'merged'
        }
      } else if (value === 'failed') {
        terminal = 'failed'
        if (cur) {
          cur.endedAt = e.ts
          cur.outcome = 'failed'
        }
      }
      continue
    }

    const resultKind = resultFieldToKind(e.field)
    if (resultKind) {
      const result = normalizeResult(e.new)
      if (result === 'skip') continue
      let attempt = current()
      if (!attempt) attempt = openNewAttempt(e.ts)
      const runIdx = (runIndexByKind.get(resultKind) ?? 0) + 1
      runIndexByKind.set(resultKind, runIdx)
      const targetTs = parseTs(e.ts)
      const outputMatch = pickClosest(outputsByKind.get(resultKind) ?? [], targetTs)
      const msMatch = pickClosest(msByKind.get(resultKind) ?? [], targetTs)
      const node: AttemptNode = {
        id: `a${attempt.n}-${resultKind}-${runIdx}`,
        attempt: attempt.n,
        kind: resultKind,
        runIndexForKind: runIdx,
        result,
        ms: msMatch ? msMatch.value : null,
        startedAt: e.ts,
        endedAt: e.ts,
        output: outputMatch ? outputMatch.value : undefined,
      }
      attempt.nodes.push(node)
      continue
    }
  }

  const lastAttempt = current()
  if (lastAttempt && lastAttempt.outcome === 'in-progress') {
    const lastNode = lastAttempt.nodes[lastAttempt.nodes.length - 1]
    if (lastNode && lastNode.result === null) {
      lastNode.result = 'running'
    }
  }

  for (const attempt of attempts) {
    const firstGate = attempt.nodes[0]
    const implEndMs = firstGate ? parseTs(firstGate.startedAt) : Date.now()
    const implStartMs = parseTs(attempt.startedAt)
    const implMs = implEndMs > implStartMs ? implEndMs - implStartMs : 0
    const implNode: AttemptNode = {
      id: `a${attempt.n}-impl`,
      attempt: attempt.n,
      kind: 'impl',
      runIndexForKind: attempt.n,
      result: firstGate ? 'pass' : attempt.outcome === 'in-progress' ? 'running' : 'pass',
      ms: implMs,
      startedAt: attempt.startedAt,
      endedAt: firstGate ? firstGate.startedAt : null,
    }
    attempt.nodes.unshift(implNode)
  }

  if (verdictSidecars && verdictSidecars.length > 0) {
    for (const sidecar of verdictSidecars) {
      if (!sidecar.gate) continue
      for (const attempt of attempts) {
        for (const node of attempt.nodes) {
          if (node.kind === sidecar.gate) {
            if (sidecar.source) node.verdictSource = sidecar.source
            if (sidecar.downgrades && sidecar.downgrades.length > 0) {
              node.downgrades = sidecar.downgrades
            }
          }
        }
      }
    }
  }

  let totalMs = 0
  let totalGateRuns = 0
  for (const attempt of attempts) {
    for (const node of attempt.nodes) {
      if (node.ms) totalMs += node.ms
      if (node.kind !== 'impl' && node.kind !== 'terminal') totalGateRuns += 1
    }
  }

  return {
    attempts,
    terminal,
    totalMs,
    totalGateRuns,
  }
}
