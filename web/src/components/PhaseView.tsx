import type { ChangeInfo, StateData } from '../lib/api'
import { TuiStatus, statusColor as tuiStatusColor } from './tui'
import GateBar from './GateBar'

interface Props {
  changes: ChangeInfo[]
  state: StateData | null
}

interface TreeNode {
  change: ChangeInfo
  children: TreeNode[]
}

const TERMINAL_STATUSES = new Set(['merged', 'done', 'skipped', 'failed'])
const RUNNING_STATUSES = new Set(['running', 'implementing', 'verifying'])


const phaseStatusIcon: Record<string, string> = {
  completed: '✅',
  running: '🔄',
  pending: '⏳',
}

function formatDuration(s?: number): string {
  if (!s) return '—'
  if (s < 60) return `${s.toFixed(0)}s`
  const m = Math.floor(s / 60)
  const rem = Math.floor(s % 60)
  return `${m}m${rem}s`
}

function formatTokens(n?: number): string {
  if (!n) return '—'
  if (n >= 1_000_000) return `${(n / 1_000_000).toFixed(1)}M`
  if (n >= 1_000) return `${(n / 1_000).toFixed(1)}k`
  return String(n)
}

function changeDuration(c: ChangeInfo): number | undefined {
  if (!c.started_at) return undefined
  const start = new Date(c.started_at).getTime()
  if (isNaN(start)) return undefined
  const end = c.completed_at ? new Date(c.completed_at).getTime() : Date.now()
  return (end - start) / 1000
}

function derivePhaseStatus(changes: ChangeInfo[]): string {
  if (changes.length === 0) return 'pending'
  if (changes.every(c => TERMINAL_STATUSES.has(c.status))) return 'completed'
  if (changes.some(c => RUNNING_STATUSES.has(c.status))) return 'running'
  return 'pending'
}

function isBlocked(change: ChangeInfo, phaseChanges: ChangeInfo[]): string | null {
  if (!change.depends_on?.length) return null
  const phaseNames = new Set(phaseChanges.map(c => c.name))
  for (const dep of change.depends_on) {
    if (!phaseNames.has(dep)) continue
    const depChange = phaseChanges.find(c => c.name === dep)
    if (depChange && !TERMINAL_STATUSES.has(depChange.status)) return dep
  }
  return null
}

function buildTree(phaseChanges: ChangeInfo[]): TreeNode[] {
  const nameSet = new Set(phaseChanges.map(c => c.name))
  const childrenOf = new Map<string, ChangeInfo[]>()
  const roots: ChangeInfo[] = []

  for (const c of phaseChanges) {
    const parent = c.depends_on?.find(d => nameSet.has(d))
    if (parent) {
      const list = childrenOf.get(parent) ?? []
      list.push(c)
      childrenOf.set(parent, list)
    } else {
      roots.push(c)
    }
  }

  function buildNode(change: ChangeInfo): TreeNode {
    const kids = childrenOf.get(change.name) ?? []
    return { change, children: kids.map(buildNode) }
  }

  return roots.map(buildNode)
}

// Grid column template: name(tree) | status | complexity | type | sessions | duration | tokens | model | gates
const GRID_COLS = 'minmax(180px,1fr) 90px 50px 70px 40px 70px 100px 80px 120px'

function ChangeRow({ node, depth, phaseChanges }: { node: TreeNode; depth: number; phaseChanges: ChangeInfo[] }) {
  const c = node.change
  const dur = changeDuration(c)
  const blockedBy = isBlocked(c, phaseChanges)
  const displayStatus = blockedBy && c.status === 'pending' ? 'blocked' : c.status

  return (
    <>
      <div
        className="grid items-center py-1.5 px-3 hover:bg-neutral-900/30 transition-colors"
        style={{ gridTemplateColumns: GRID_COLS }}
      >
        {/* Name with tree indent */}
        <div className="flex items-center gap-1.5 min-w-0" style={{ paddingLeft: `${depth * 20}px` }}>
          {depth > 0 && (
            <span className="text-neutral-700 text-sm shrink-0">└</span>
          )}
          <TuiStatus status={displayStatus} label={false} />
          <span className="text-sm text-neutral-200 truncate">{c.name}</span>
          {blockedBy && (
            <span className="text-sm text-neutral-600 shrink-0 truncate">← {blockedBy}</span>
          )}
        </div>

        {/* Status */}
        <span className={`text-sm ${tuiStatusColor(displayStatus)}`}>
          {displayStatus}
        </span>

        {/* Complexity */}
        <span className="text-sm text-neutral-500 text-center">
          {c.complexity ?? '—'}
        </span>

        {/* Type */}
        <span className="text-sm text-neutral-600 truncate">
          {c.change_type ?? '—'}
        </span>

        {/* Sessions */}
        <span className="text-sm text-neutral-500 text-center">
          {c.session_count ?? '—'}
        </span>

        {/* Duration */}
        <span className="text-sm text-neutral-500 text-right">{formatDuration(dur)}</span>

        {/* Tokens */}
        <span className="text-sm text-neutral-500 text-right">
          {formatTokens(c.input_tokens)}/{formatTokens(c.output_tokens)}
        </span>

        {/* Model */}
        <span className="text-sm text-neutral-600 truncate">
          {c.model ? c.model.replace('claude-', '').replace('-latest', '') : '—'}
        </span>

        {/* Gates */}
        <div className="flex justify-end">
          <GateBar
            test_result={c.test_result}
            smoke_result={c.smoke_result}
            review_result={c.review_result}
            build_result={c.build_result}
            spec_coverage_result={c.spec_coverage_result}
          />
        </div>
      </div>

      {node.children.map(child => (
        <ChangeRow key={child.change.name} node={child} depth={depth + 1} phaseChanges={phaseChanges} />
      ))}
    </>
  )
}

export default function PhaseView({ changes, state }: Props) {
  if (changes.length === 0) {
    return <div className="p-4 text-neutral-500 text-sm">No changes</div>
  }

  // Group by phase
  const phaseMap = new Map<number, ChangeInfo[]>()
  for (const c of changes) {
    const p = c.phase ?? 1
    const list = phaseMap.get(p) ?? []
    list.push(c)
    phaseMap.set(p, list)
  }
  const phaseNums = Array.from(phaseMap.keys()).sort((a, b) => a - b)

  return (
    <div className="divide-y divide-neutral-800/50">
      {phaseNums.map(phaseNum => {
        const phaseChanges = phaseMap.get(phaseNum)!
        const tree = buildTree(phaseChanges)

        const extPhase = state?.phases?.[String(phaseNum)]
        const phaseStatus = extPhase?.status ?? derivePhaseStatus(phaseChanges)

        const doneCount = phaseChanges.filter(c => TERMINAL_STATUSES.has(c.status)).length
        const totalCount = phaseChanges.length
        const totalTokens = phaseChanges.reduce((s, c) => s + (c.input_tokens ?? 0) + (c.output_tokens ?? 0), 0)
        const totalDuration = phaseChanges.reduce((s, c) => s + (changeDuration(c) ?? 0), 0)

        return (
          <div key={phaseNum}>
            {/* Phase header */}
            <div className="flex items-center gap-3 px-3 py-2.5 bg-neutral-900/50">
              <span className="text-sm">{phaseStatusIcon[phaseStatus] ?? '⏳'}</span>
              <span className="text-sm font-medium text-neutral-200">Phase {phaseNum}</span>
              <span className={`text-sm ${
                phaseStatus === 'completed' ? 'text-blue-400' :
                phaseStatus === 'running' ? 'text-green-400' :
                'text-neutral-500'
              }`}>{phaseStatus}</span>

              <span className="flex-1" />

              <span className="text-sm text-neutral-400">{doneCount}/{totalCount}</span>
              {totalTokens > 0 && (
                <span className="text-sm text-neutral-500">{formatTokens(totalTokens)}</span>
              )}
              {totalDuration > 0 && (
                <span className="text-sm text-neutral-500">{formatDuration(totalDuration)}</span>
              )}
            </div>

            {/* Column headers */}
            <div
              className="grid items-center px-3 py-1 text-sm text-neutral-600 border-b border-neutral-800/30"
              style={{ gridTemplateColumns: GRID_COLS }}
            >
              <span>Name</span>
              <span>Status</span>
              <span className="text-center">Cplx</span>
              <span>Type</span>
              <span className="text-center">Ss</span>
              <span className="text-right">Duration</span>
              <span className="text-right">In/Out</span>
              <span>Model</span>
              <span className="text-right">Gates</span>
            </div>

            {/* Change tree */}
            <div className="pb-1">
              {tree.map(node => (
                <ChangeRow key={node.change.name} node={node} depth={0} phaseChanges={phaseChanges} />
              ))}
            </div>
          </div>
        )
      })}
    </div>
  )
}
