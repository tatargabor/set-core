import { Fragment, useState } from 'react'
import type { ChangeInfo } from '../lib/api'
// Action imports preserved for future re-enable
// import { stopChange, skipChange, pauseChange, resumeChange } from '../lib/api'
import { TuiStatus, statusColor as tuiStatusColor } from './tui'
import GateBar from './GateBar'
import StepBar from './StepBar'
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

  if (changes.length === 0) {
    return (
      <div className="p-4 text-neutral-500 text-sm">No changes</div>
    )
  }

  // Mobile: compact expandable rows
  if (isMobile) {
    return (
      <div className="divide-y divide-neutral-800/50">
        {changes.map((c) => {
          const isExpanded = selected === c.name
          const hasGates = !!(c.build_result || c.test_result || c.review_result || c.smoke_result || c.e2e_result || c.spec_coverage_result)
          const isGateExpanded = expandedGate === c.name
          return (
            <div key={c.name}>
              {/* Compact row */}
              <button
                onClick={() => onSelect?.(c.name)}
                className={`w-full flex items-center gap-2 px-3 py-2.5 text-left transition-colors active:bg-neutral-800/50 ${
                  isExpanded ? 'bg-neutral-900/70' : ''
                }`}
              >
                <TuiStatus status={c.status} label={false} />
                <span className="text-sm text-neutral-200 truncate flex-1">{c.name}</span>
                <span className="text-sm text-neutral-500 shrink-0">{formatDuration(changeDuration(c))}</span>
                <span className="text-sm shrink-0"><TuiStatus status={c.status} /></span>
                <span className="text-neutral-600 text-sm">{isExpanded ? '▲' : '▼'}</span>
              </button>

              {/* Expanded details */}
              {isExpanded && (
                <div className="px-3 pb-3 space-y-2 bg-neutral-900/30">
                  {/* Tokens + model */}
                  <div className="flex gap-4 text-sm text-neutral-400">
                    <span>In: {formatTokens(c.input_tokens)}</span>
                    <span>Out: {formatTokens(c.output_tokens)}</span>
                    {c.context_tokens_end != null && (
                      <span
                        className={c.context_tokens_end / 200_000 >= 0.8 ? 'text-orange-400' : 'text-neutral-400'}
                        title={c.context_breakdown_start
                          ? `Base: ${Math.round(c.context_breakdown_start.base_context / 1000)}K | Memory: ${Math.round(c.context_breakdown_start.memory_injection / 1000)}K | Prompt: ${Math.round(c.context_breakdown_start.prompt_overhead / 1000)}K | Tools: ${Math.round(c.context_breakdown_start.tool_output / 1000)}K`
                          : undefined}
                      >
                        ctx: {c.context_tokens_start != null
                          ? `${Math.round(c.context_tokens_start / 1000)}K→`
                          : ''}{Math.round(c.context_tokens_end / 1000)}K ({Math.round(c.context_tokens_end / 200_000 * 100)}%)
                      </span>
                    )}
                    {c.session_count && <span>Sessions: {c.session_count}</span>}
                    {c.model && <span className="text-neutral-500">{c.model}</span>}
                  </div>

                  {/* Gates */}
                  <StepBar current_step={c.current_step} />
                  {hasGates && (
                    <div
                      className="cursor-pointer"
                      onClick={(e) => toggleGate(e, c.name)}
                    >
                      <GateBar
                        test_result={c.test_result}
                        smoke_result={c.smoke_result}
                        e2e_result={c.e2e_result}
                        review_result={c.review_result}
                        build_result={c.build_result}
                        spec_coverage_result={c.spec_coverage_result}
                        hasScreenshots={!!c.smoke_screenshot_count || !!c.e2e_screenshot_count}
                        onScreenshots={(e) => toggleScreenshots(e, c.name)}
                      />
                    </div>
                  )}

                  {/* Gate detail */}
                  {isGateExpanded && hasGates && (
                    <div className="rounded border border-neutral-800/50 bg-neutral-950/50 p-2">
                      <ChangeTimeline change={c} />
                      <GateDetail change={c} />
                    </div>
                  )}

                  {/* Screenshots */}
                  {screenshotChange === c.name && (
                    <div className="rounded border border-neutral-800/50 bg-neutral-950/50 p-2">
                      <ScreenshotGallery
                        project={project}
                        changeName={c.name}
                        onClose={() => setScreenshotChange(null)}
                      />
                    </div>
                  )}

                  {/* Actions hidden — sentinel manages change lifecycle */}
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
        <tr className="text-sm text-neutral-500 border-b border-neutral-800">
          <th className="text-left px-4 py-2 font-medium">Name</th>
          <th className="text-left px-2 py-2 font-medium">Status</th>
          <th className="text-center px-2 py-2 font-medium">Sess</th>
          <th className="text-right px-2 py-2 font-medium">Duration</th>
          <th className="text-right px-2 py-2 font-medium">Tokens</th>
          <th className="text-center px-2 py-2 font-medium">Gates</th>
          {/* Actions column hidden */}
        </tr>
      </thead>
      <tbody>
        {changes.map((c) => {
          const clickable = !!c.worktree_path
          const isSelected = selected === c.name
          const hasGates = !!(c.build_result || c.test_result || c.review_result || c.smoke_result || c.e2e_result || c.spec_coverage_result)
          const isGateExpanded = expandedGate === c.name
          return (
            <Fragment key={c.name}>
            <tr
              onClick={clickable && onSelect ? () => onSelect(c.name) : undefined}
              className={`border-b ${isGateExpanded ? 'border-b-0' : 'border-b'} border-neutral-800/50 transition-colors ${
                clickable ? 'cursor-pointer hover:bg-neutral-900/50' : ''
              } ${isSelected ? 'bg-neutral-900/70 border-l-2 border-l-blue-500' : ''}`}
            >
              <td className="px-4 py-2 text-neutral-200">{c.name}</td>
              <td className={`px-2 py-2 font-medium ${tuiStatusColor(c.status)}`}>
                {c.status}
              </td>
              <td className="px-2 py-2 text-center text-neutral-400">{c.session_count ?? '—'}</td>
              <td className="px-2 py-2 text-right text-neutral-400">{formatDuration(changeDuration(c))}</td>
              <td className="px-2 py-2 text-right text-neutral-400 text-sm">
                {formatTokens(c.input_tokens)}/{formatTokens(c.output_tokens)}
                {c.context_tokens_end != null && (
                  <span
                    className={`ml-1 ${c.context_tokens_end / 200_000 >= 0.8 ? 'text-orange-400' : 'text-neutral-500'}`}
                    title={c.context_breakdown_start
                      ? `Base: ${Math.round(c.context_breakdown_start.base_context / 1000)}K | Memory: ${Math.round(c.context_breakdown_start.memory_injection / 1000)}K | Prompt: ${Math.round(c.context_breakdown_start.prompt_overhead / 1000)}K | Tools: ${Math.round(c.context_breakdown_start.tool_output / 1000)}K`
                      : undefined}
                  >
                    {' '}ctx:{Math.round(c.context_tokens_end / 1000)}K
                  </span>
                )}
              </td>
              <td className="px-2 py-2">
                <div className="flex justify-center gap-2">
                  <StepBar current_step={c.current_step} />
                  <div
                    className="cursor-pointer"
                    onClick={(e) => toggleGate(e, c.name)}
                    title="Click to expand gate details"
                  >
                  <GateBar
                    test_result={c.test_result}
                    smoke_result={c.smoke_result}
                    e2e_result={c.e2e_result}
                    review_result={c.review_result}
                    build_result={c.build_result}
                    spec_coverage_result={c.spec_coverage_result}
                    hasScreenshots={!!c.smoke_screenshot_count || !!c.e2e_screenshot_count}
                    onScreenshots={(e) => toggleScreenshots(e, c.name)}
                  />
                  </div>
                </div>
              </td>
              {/* Actions column hidden — sentinel manages change lifecycle */}
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
