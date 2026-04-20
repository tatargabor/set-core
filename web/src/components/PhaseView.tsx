import { useMemo, useState } from 'react'
import type { ChangeInfo, StateData } from '../lib/api'
import { TuiStatus, statusColor as tuiStatusColor } from './tui'
import GateBar from './GateBar'
import StepBar from './StepBar'

interface Props {
  changes: ChangeInfo[]
  state: StateData | null
}

const UNKNOWN_LINEAGE = '__unknown__'

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

// Grid column template: name(tree) | status | complexity | type | sessions | duration | tokens | gates
const GRID_COLS = 'minmax(160px,1.5fr) 80px 40px 60px 30px 65px 95px minmax(100px,1fr)'

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

        {/* Gates */}
        <div className="flex justify-end gap-2">
          <StepBar current_step={c.current_step} />
          <GateBar
            test_result={c.test_result}
            smoke_result={c.smoke_result}
            e2e_result={c.e2e_result}
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
  // All-lineages mode was removed — the view is always lineage-scoped to
  // the sidebar selection, so phase groups no longer split by lineage.
  const [showUnattributed, setShowUnattributed] = useState(false)

  // Section 15.1 — hide `__unknown__` entries by default.  They are
  // unrecoverable backfill leftovers and would otherwise pollute the
  // phase layout with a synthetic group.  An opt-in affordance lets
  // operators still inspect them.
  const attributedChanges = useMemo(() => {
    return changes.filter(c => {
      if (showUnattributed) return true
      return c.spec_lineage_id !== UNKNOWN_LINEAGE
    })
  }, [changes, showUnattributed])
  const unattributedCount = useMemo(
    () => changes.filter(c => c.spec_lineage_id === UNKNOWN_LINEAGE).length,
    [changes],
  )

  if (attributedChanges.length === 0 && unattributedCount === 0) {
    return <div className="p-4 text-neutral-500 text-sm">No changes</div>
  }

  // Section 9.2 / AC-20 — when two plan versions share a phase number
  // we split into separate groups labelled "Phase N (plan vX)".  Single-
  // version phases render without the suffix to keep the common case
  // unchanged.  Section 14.9 / AC-48 — when the operator is viewing the
  // __all__ union we additionally split by lineage so entries from
  // different specs do not get mixed into one phase group.
  type GroupKey = { phase: number; planVersion: string | null; lineage: string | null }
  const groups = new Map<string, ChangeInfo[]>()
  const groupMeta = new Map<string, GroupKey>()
  const phaseHasMultipleVersions = new Map<number, Set<string>>()
  for (const c of attributedChanges) {
    const p = c.phase ?? 1
    const pv = c.plan_version == null ? null : String(c.plan_version)
    if (pv != null) {
      const versions = phaseHasMultipleVersions.get(p) ?? new Set<string>()
      versions.add(pv)
      phaseHasMultipleVersions.set(p, versions)
    }
  }
  for (const c of attributedChanges) {
    const p = c.phase ?? 1
    const pv = c.plan_version == null ? null : String(c.plan_version)
    const key = `${p}|${pv ?? ''}|`
    const list = groups.get(key) ?? []
    list.push(c)
    groups.set(key, list)
    if (!groupMeta.has(key)) {
      groupMeta.set(key, { phase: p, planVersion: pv, lineage: null })
    }
  }

  const orderedKeys = Array.from(groups.keys()).sort((a, b) => {
    const ma = groupMeta.get(a)!
    const mb = groupMeta.get(b)!
    if (ma.phase !== mb.phase) return ma.phase - mb.phase
    const pva = ma.planVersion ?? ''
    const pvb = mb.planVersion ?? ''
    if (pva !== pvb) return pva.localeCompare(pvb)
    return (ma.lineage ?? '').localeCompare(mb.lineage ?? '')
  })

  return (
    <div className="divide-y divide-neutral-800/50">
      {orderedKeys.map(key => {
        const meta = groupMeta.get(key)!
        const phaseChanges = groups.get(key)!
        const tree = buildTree(phaseChanges)

        const versionsForPhase = phaseHasMultipleVersions.get(meta.phase)
        const showVersionLabel = meta.planVersion != null
          && versionsForPhase != null
          && versionsForPhase.size > 1

        const extPhase = state?.phases?.[String(meta.phase)]
        const phaseStatus = extPhase?.status ?? derivePhaseStatus(phaseChanges)

        const doneCount = phaseChanges.filter(c => TERMINAL_STATUSES.has(c.status)).length
        const totalCount = phaseChanges.length
        const totalTokens = phaseChanges.reduce((s, c) => s + (c.input_tokens ?? 0) + (c.output_tokens ?? 0), 0)
        const totalDuration = phaseChanges.reduce((s, c) => s + (changeDuration(c) ?? 0), 0)

        const headerLabel = showVersionLabel
          ? `Phase ${meta.phase} (plan v${meta.planVersion})`
          : `Phase ${meta.phase}`

        return (
          <div key={key} data-testid={`phase-group-${key}`}>
            {/* Phase header */}
            <div className="flex items-center gap-3 px-3 py-2.5 bg-neutral-900/50">
              <span className="text-sm">{phaseStatusIcon[phaseStatus] ?? '⏳'}</span>
              <span className="text-sm font-medium text-neutral-200">{headerLabel}</span>
              {meta.lineage && (
                <span className="text-xs text-neutral-500" title={`Lineage: ${meta.lineage}`}>
                  {meta.lineage}
                </span>
              )}
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
      {unattributedCount > 0 && (
        <div className="px-3 py-2 text-xs text-neutral-500 flex items-center gap-2">
          <span>{unattributedCount} unattributed legacy change{unattributedCount === 1 ? '' : 's'}</span>
          <button
            type="button"
            onClick={() => setShowUnattributed(v => !v)}
            className="px-2 py-0.5 rounded border border-neutral-700 hover:bg-neutral-800 text-neutral-400"
            data-testid="toggle-unattributed"
          >
            {showUnattributed ? 'Hide unattributed' : 'Show unattributed'}
          </button>
        </div>
      )}
    </div>
  )
}
