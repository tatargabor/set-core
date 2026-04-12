export type GateKind =
  | 'impl'
  | 'build'
  | 'test'
  | 'e2e'
  | 'review'
  | 'smoke'
  | 'scope_check'
  | 'rules'
  | 'e2e_coverage'
  | 'merge'
  | 'terminal'

export type GateResult =
  | 'pass'
  | 'fail'
  | 'warn'
  | 'skip'
  | 'running'
  | null

export interface DowngradeEntry {
  from: string
  to: string
  reason: string
}

export interface AttemptNode {
  id: string
  attempt: number
  kind: GateKind
  runIndexForKind: number
  result: GateResult
  ms: number | null
  startedAt: string
  endedAt: string | null
  output?: string
  verdictSource?: string
  downgrades?: DowngradeEntry[]
  issueRefs?: string[]
}

export type AttemptOutcome = 'retry' | 'merged' | 'failed' | 'in-progress'
export type RetryReason = 'gate-fail' | 'merge-conflict' | 'replan' | 'unknown'

export interface Attempt {
  n: number
  startedAt: string
  endedAt: string | null
  outcome: AttemptOutcome
  retryReason?: RetryReason
  nodes: AttemptNode[]
}

export type TerminalState = 'merged' | 'failed' | 'in-progress'

export interface AttemptGraph {
  attempts: Attempt[]
  terminal: TerminalState
  totalMs: number
  totalGateRuns: number
}

export interface VerdictSidecar {
  change: string
  session?: number
  gate?: string
  source?: string
  downgrades?: DowngradeEntry[]
}
