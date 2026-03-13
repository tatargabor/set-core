import { Fragment, useState } from 'react'
import type { ChangeInfo } from '../lib/api'
import { stopChange, skipChange } from '../lib/api'
import GateBar from './GateBar'
import GateDetail from './GateDetail'
import ScreenshotGallery from './ScreenshotGallery'
import ChangeTimeline from './ChangeTimeline'
import useIsMobile from '../hooks/useIsMobile'

interface Props {
  changes: ChangeInfo[]
  project: string
  selected?: string | null
  onSelect?: (name: string | null) => void
}

const statusColor: Record<string, string> = {
  running: 'text-green-400',
  implementing: 'text-green-400',
  verifying: 'text-cyan-400',
  completed: 'text-blue-400',
  done: 'text-blue-400',
  merged: 'text-blue-400',
  failed: 'text-red-400',
  'verify-failed': 'text-red-400',
  skipped: 'text-neutral-500',
  skip_merged: 'text-neutral-500',
  pending: 'text-neutral-500',
  stalled: 'text-yellow-400',
  checkpoint: 'text-yellow-400',
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

export default function ChangeTable({ changes, project, selected, onSelect }: Props) {
  const [actionLoading, setActionLoading] = useState<string | null>(null)
  const [expandedGate, setExpandedGate] = useState<string | null>(null)
  const [screenshotChange, setScreenshotChange] = useState<string | null>(null)
  const isMobile = useIsMobile()

  const toggleGate = (e: React.MouseEvent, name: string) => {
    e.stopPropagation()
    setExpandedGate(prev => prev === name ? null : name)
  }

  const toggleScreenshots = (e: React.MouseEvent, name: string) => {
    e.stopPropagation()
    setScreenshotChange(prev => prev === name ? null : name)
  }

  const handleAction = async (e: React.MouseEvent, name: string, action: 'stop' | 'skip') => {
    e.stopPropagation()
    setActionLoading(`${name}:${action}`)
    try {
      if (action === 'stop') await stopChange(project, name)
      if (action === 'skip') await skipChange(project, name)
    } catch {
      // will be reflected in next state update
    }
    setActionLoading(null)
  }

  if (changes.length === 0) {
    return (
      <div className="p-4 text-neutral-500 text-sm">No changes</div>
    )
  }

  // Mobile: card layout
  if (isMobile) {
    return (
      <div className="p-2 space-y-2">
        {changes.map((c) => {
          const clickable = !!c.worktree_path
          const isSelected = selected === c.name
          const hasGates = !!(c.build_result || c.test_result || c.review_result || c.smoke_result)
          const isGateExpanded = expandedGate === c.name
          return (
            <div key={c.name}>
              <div
                onClick={clickable && onSelect ? () => onSelect(isSelected ? null : c.name) : undefined}
                className={`rounded-lg border border-neutral-800 p-3 transition-colors ${
                  clickable ? 'active:bg-neutral-800/70' : ''
                } ${isSelected ? 'bg-neutral-900/70 border-l-2 border-l-blue-500' : 'bg-neutral-900/30'}`}
              >
                {/* Row 1: name + status */}
                <div className="flex items-center justify-between gap-2 mb-2">
                  <span className="font-mono text-sm text-neutral-200 truncate">{c.name}</span>
                  <span className={`text-sm font-medium shrink-0 ${statusColor[c.status] ?? 'text-neutral-400'}`}>
                    {c.status}
                  </span>
                </div>

                {/* Row 2: duration + gates */}
                <div className="flex items-center justify-between gap-2 mb-2">
                  <span className="text-xs text-neutral-400">{formatDuration(changeDuration(c))}</span>
                  <div
                    className="cursor-pointer"
                    onClick={(e) => toggleGate(e, c.name)}
                  >
                    <GateBar
                      test_result={c.test_result}
                      smoke_result={c.smoke_result}
                      review_result={c.review_result}
                      build_result={c.build_result}
                      hasScreenshots={!!c.smoke_screenshot_count || !!c.e2e_screenshot_count}
                      onScreenshots={(e) => toggleScreenshots(e, c.name)}
                    />
                  </div>
                </div>

                {/* Row 3: actions */}
                <div className="flex gap-2">
                  {['running', 'verifying', 'implementing'].includes(c.status) && (
                    <button
                      onClick={(e) => handleAction(e, c.name, 'stop')}
                      disabled={actionLoading === `${c.name}:stop`}
                      className="px-3 min-h-[44px] text-sm bg-red-900/50 text-red-300 rounded hover:bg-red-900 disabled:opacity-50"
                    >
                      Stop
                    </button>
                  )}
                  {(c.status === 'pending' || c.status === 'failed' || c.status === 'verify-failed' || c.status === 'stalled') && (
                    <button
                      onClick={(e) => handleAction(e, c.name, 'skip')}
                      disabled={actionLoading === `${c.name}:skip`}
                      className="px-3 min-h-[44px] text-sm bg-neutral-800 text-neutral-400 rounded hover:bg-neutral-700 disabled:opacity-50"
                    >
                      Skip
                    </button>
                  )}
                </div>
              </div>

              {/* Expanded gate detail */}
              {isGateExpanded && hasGates && (
                <div className="mt-1 rounded-lg border border-neutral-800/50 bg-neutral-950/50 p-2">
                  <ChangeTimeline change={c} />
                  <GateDetail change={c} />
                </div>
              )}
              {screenshotChange === c.name && (
                <div className="mt-1 rounded-lg border border-neutral-800/50 bg-neutral-950/50 p-2">
                  <ScreenshotGallery
                    project={project}
                    changeName={c.name}
                    onClose={() => setScreenshotChange(null)}
                  />
                </div>
              )}
            </div>
          )
        })}
      </div>
    )
  }

  // Desktop: table layout
  return (
    <table className="w-full text-sm">
      <thead>
        <tr className="text-xs text-neutral-500 border-b border-neutral-800">
          <th className="text-left px-4 py-2 font-medium">Name</th>
          <th className="text-left px-2 py-2 font-medium">Status</th>
          <th className="text-center px-2 py-2 font-medium">Sess</th>
          <th className="text-right px-2 py-2 font-medium">Duration</th>
          <th className="text-right px-2 py-2 font-medium">Tokens</th>
          <th className="text-center px-2 py-2 font-medium">Gates</th>
          <th className="text-right px-4 py-2 font-medium">Actions</th>
        </tr>
      </thead>
      <tbody>
        {changes.map((c) => {
          const clickable = !!c.worktree_path
          const isSelected = selected === c.name
          const hasGates = !!(c.build_result || c.test_result || c.review_result || c.smoke_result)
          const isGateExpanded = expandedGate === c.name
          return (
            <Fragment key={c.name}>
            <tr
              onClick={clickable && onSelect ? () => onSelect(isSelected ? null : c.name) : undefined}
              className={`border-b ${isGateExpanded ? 'border-b-0' : 'border-b'} border-neutral-800/50 transition-colors ${
                clickable ? 'cursor-pointer hover:bg-neutral-900/50' : ''
              } ${isSelected ? 'bg-neutral-900/70 border-l-2 border-l-blue-500' : ''}`}
            >
              <td className="px-4 py-2 font-mono text-neutral-200">{c.name}</td>
              <td className={`px-2 py-2 font-medium ${statusColor[c.status] ?? 'text-neutral-400'}`}>
                {c.status}
              </td>
              <td className="px-2 py-2 text-center text-neutral-400">{c.session_count ?? '—'}</td>
              <td className="px-2 py-2 text-right text-neutral-400">{formatDuration(changeDuration(c))}</td>
              <td className="px-2 py-2 text-right text-neutral-400 font-mono text-xs">
                {formatTokens(c.input_tokens)}/{formatTokens(c.output_tokens)}
              </td>
              <td className="px-2 py-2">
                <div
                  className="flex justify-center cursor-pointer"
                  onClick={(e) => toggleGate(e, c.name)}
                  title="Click to expand gate details"
                >
                  <GateBar
                    test_result={c.test_result}
                    smoke_result={c.smoke_result}
                    review_result={c.review_result}
                    build_result={c.build_result}
                    hasScreenshots={!!c.smoke_screenshot_count || !!c.e2e_screenshot_count}
                    onScreenshots={(e) => toggleScreenshots(e, c.name)}
                  />
                </div>
              </td>
              <td className="px-4 py-2 text-right">
                <div className="flex gap-1 justify-end">
                  {['running', 'verifying', 'implementing'].includes(c.status) && (
                    <button
                      onClick={(e) => handleAction(e, c.name, 'stop')}
                      disabled={actionLoading === `${c.name}:stop`}
                      className="px-2 py-0.5 text-xs bg-red-900/50 text-red-300 rounded hover:bg-red-900 disabled:opacity-50"
                    >
                      Stop
                    </button>
                  )}
                  {(c.status === 'pending' || c.status === 'failed' || c.status === 'verify-failed' || c.status === 'stalled') && (
                    <button
                      onClick={(e) => handleAction(e, c.name, 'skip')}
                      disabled={actionLoading === `${c.name}:skip`}
                      className="px-2 py-0.5 text-xs bg-neutral-800 text-neutral-400 rounded hover:bg-neutral-700 disabled:opacity-50"
                    >
                      Skip
                    </button>
                  )}
                </div>
              </td>
            </tr>
            {isGateExpanded && hasGates && (
              <tr className="border-b border-neutral-800/50 bg-neutral-950/50">
                <td colSpan={7}>
                  <ChangeTimeline change={c} />
                  <GateDetail change={c} />
                </td>
              </tr>
            )}
            {screenshotChange === c.name && (
              <tr className="border-b border-neutral-800/50 bg-neutral-950/50">
                <td colSpan={7}>
                  <ScreenshotGallery
                    project={project}
                    changeName={c.name}
                    onClose={() => setScreenshotChange(null)}
                  />
                </td>
              </tr>
            )}
            </Fragment>
          )
        })}
      </tbody>
    </table>
  )
}
