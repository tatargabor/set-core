import { useState, useEffect, useMemo } from 'react'
import { getRequirements, getDigest, type RequirementsData, type ReqChangeInfo, type DigestReq, type DigestData } from '../lib/api'

interface Props {
  project: string
}

const STATUS_COLOR: Record<string, string> = {
  merged: 'bg-blue-500',
  done: 'bg-blue-500',
  completed: 'bg-blue-500',
  skip_merged: 'bg-blue-400',
  running: 'bg-green-500',
  implementing: 'bg-green-500',
  verifying: 'bg-cyan-500',
  failed: 'bg-red-500',
  'verify-failed': 'bg-red-500',
  stalled: 'bg-yellow-500',
  pending: 'bg-neutral-600',
  planned: 'bg-neutral-700',
}

const STATUS_TEXT: Record<string, string> = {
  merged: 'text-blue-400',
  done: 'text-blue-400',
  completed: 'text-blue-400',
  running: 'text-green-400',
  implementing: 'text-green-400',
  verifying: 'text-cyan-400',
  failed: 'text-red-400',
  'verify-failed': 'text-red-400',
  stalled: 'text-yellow-400',
  pending: 'text-neutral-500',
  planned: 'text-neutral-600',
}

function ProgressBar({ done, inProgress, failed, total }: {
  done: number; inProgress: number; failed: number; total: number
}) {
  if (total === 0) return null
  const doneP = (done / total) * 100
  const ipP = (inProgress / total) * 100
  const failP = (failed / total) * 100

  return (
    <div className="flex h-2 rounded-full overflow-hidden bg-neutral-800 w-full">
      {doneP > 0 && <div className="bg-blue-500 transition-all" style={{ width: `${doneP}%` }} />}
      {ipP > 0 && <div className="bg-green-500 animate-pulse transition-all" style={{ width: `${ipP}%` }} />}
      {failP > 0 && <div className="bg-red-500 transition-all" style={{ width: `${failP}%` }} />}
    </div>
  )
}

function DependencyTree({ changes }: { changes: ReqChangeInfo[] }) {
  // Build adjacency: who blocks whom
  const blockedBy = useMemo(() => {
    const map = new Map<string, string[]>()
    for (const c of changes) {
      if (c.depends_on.length > 0) {
        map.set(c.name, c.depends_on.filter(d => changes.some(ch => ch.name === d)))
      }
    }
    return map
  }, [changes])

  // Find roots (no dependencies)
  const roots = useMemo(() => {
    return changes.filter(c => !blockedBy.has(c.name) || blockedBy.get(c.name)!.length === 0)
  }, [changes, blockedBy])

  // Build children map
  const children = useMemo(() => {
    const map = new Map<string, string[]>()
    for (const [child, deps] of blockedBy) {
      for (const dep of deps) {
        if (!map.has(dep)) map.set(dep, [])
        map.get(dep)!.push(child)
      }
    }
    return map
  }, [blockedBy])

  // Only auto-expand roots that have active/failed children
  const [expanded, setExpanded] = useState<Set<string>>(() => {
    const activeStatuses = new Set(['running', 'implementing', 'verifying', 'failed', 'verify-failed'])
    const cMap = new Map(changes.map(c => [c.name, c]))
    const active = new Set<string>()
    for (const r of roots) {
      if (activeStatuses.has(r.status)) active.add(r.name)
      const kids = children.get(r.name) ?? []
      if (kids.some(k => { const c = cMap.get(k); return c && activeStatuses.has(c.status) })) {
        active.add(r.name)
      }
    }
    return active
  })

  const toggle = (name: string) => {
    setExpanded(prev => {
      const next = new Set(prev)
      if (next.has(name)) next.delete(name)
      else next.add(name)
      return next
    })
  }

  const changeMap = useMemo(() => {
    const m = new Map<string, ReqChangeInfo>()
    for (const c of changes) m.set(c.name, c)
    return m
  }, [changes])

  const rendered = new Set<string>()

  function renderNode(name: string, depth: number): React.ReactNode {
    if (rendered.has(name)) return null
    rendered.add(name)
    const c = changeMap.get(name)
    if (!c) return null
    const kids = children.get(name) ?? []
    const hasKids = kids.length > 0
    const isExpanded = expanded.has(name)
    const statusColor = STATUS_COLOR[c.status] ?? 'bg-neutral-700'
    const statusText = STATUS_TEXT[c.status] ?? 'text-neutral-600'
    const doneStatuses = new Set(['done', 'merged', 'completed', 'skip_merged'])
    const isDone = doneStatuses.has(c.status)

    return (
      <div key={name}>
        <div
          className={`flex items-center gap-2 py-1 px-2 hover:bg-neutral-800/50 rounded cursor-pointer ${isDone ? 'opacity-60' : ''}`}
          style={{ paddingLeft: `${depth * 20 + 8}px` }}
          onClick={() => hasKids && toggle(name)}
        >
          {hasKids ? (
            <span className="text-neutral-500 w-3 text-center text-[10px]">
              {isExpanded ? '▾' : '▸'}
            </span>
          ) : (
            <span className="w-3" />
          )}
          <span className={`w-2 h-2 rounded-full shrink-0 ${statusColor}`} />
          <span className="font-mono text-[11px] text-neutral-300 truncate">{name}</span>
          <span className={`text-[10px] ml-auto shrink-0 ${statusText}`}>{c.status}</span>
          <span className="text-[10px] text-neutral-600 shrink-0">{c.requirements.length} reqs</span>
          {c.complexity && (
            <span className="text-[10px] text-neutral-600 shrink-0">{c.complexity}</span>
          )}
        </div>
        {isExpanded && kids.map(kid => renderNode(kid, depth + 1))}
      </div>
    )
  }

  return (
    <div className="space-y-0.5">
      {roots.map(r => renderNode(r.name, 0))}
      {/* Render any orphans not reached from roots */}
      {changes.filter(c => !rendered.has(c.name)).map(c => renderNode(c.name, 0))}
    </div>
  )
}

export default function ProgressView({ project }: Props) {
  const [data, setData] = useState<RequirementsData | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [view, setView] = useState<'groups' | 'tree'>('groups')

  useEffect(() => {
    let cancelled = false
    const load = () => {
      getRequirements(project)
        .then(d => { if (!cancelled) { setData(d); setError(null) } })
        .catch(e => { if (!cancelled) setError(String(e)) })
    }
    load()
    const interval = setInterval(load, 10000)
    return () => { cancelled = true; clearInterval(interval) }
  }, [project])

  if (error) {
    return <div className="p-4 text-xs text-red-400">{error}</div>
  }
  if (!data) {
    return <div className="p-4 text-xs text-neutral-500">Loading requirements...</div>
  }
  if (data.total_reqs === 0 && data.changes.length === 0) {
    return <div className="p-4 text-xs text-neutral-500">No plan data found</div>
  }

  // When no formal plan requirements, try digest requirements
  const hasReqs = data.total_reqs > 0
  if (!hasReqs) {
    return <DigestFallbackView project={project} changes={data.changes} />
  }
  const doneStatuses = new Set(['done', 'merged', 'completed', 'skip_merged'])
  const ipStatuses = new Set(['running', 'implementing', 'verifying'])
  const failStatuses = new Set(['failed', 'verify-failed'])

  const trackTotal = hasReqs ? data.total_reqs : data.changes.length
  const trackDone = hasReqs ? data.done_reqs : data.changes.filter(c => doneStatuses.has(c.status)).length
  const trackIp = hasReqs
    ? data.groups.reduce((s, g) => s + g.in_progress, 0)
    : data.changes.filter(c => ipStatuses.has(c.status)).length
  const trackFailed = hasReqs
    ? data.groups.reduce((s, g) => s + g.failed, 0)
    : data.changes.filter(c => failStatuses.has(c.status)).length
  const pctDone = trackTotal > 0 ? Math.round((trackDone / trackTotal) * 100) : 0

  return (
    <div className="flex flex-col h-full">
      {/* Sub-header: progress + view toggle */}
      <div className="flex items-center gap-3 px-4 py-1.5 border-b border-neutral-800/50 shrink-0">
        <span className="text-xs font-medium text-neutral-300">
          {trackDone}/{trackTotal}
        </span>
        <span className="text-[10px] text-neutral-500">{pctDone}%</span>
        <div className="flex-1 max-w-xs">
          <ProgressBar done={trackDone} inProgress={trackIp} failed={trackFailed} total={trackTotal} />
        </div>
        {hasReqs && (
          <div className="flex gap-1 ml-auto">
            <button
              onClick={() => setView('groups')}
              className={`px-2 py-0.5 text-[10px] rounded ${view === 'groups' ? 'bg-neutral-700 text-neutral-200' : 'text-neutral-500 hover:text-neutral-300'}`}
            >
              Groups
            </button>
            <button
              onClick={() => setView('tree')}
              className={`px-2 py-0.5 text-[10px] rounded ${view === 'tree' ? 'bg-neutral-700 text-neutral-200' : 'text-neutral-500 hover:text-neutral-300'}`}
            >
              Dep Tree
            </button>
          </div>
        )}
        <span className={`text-[10px] text-neutral-600 ${hasReqs ? '' : 'ml-auto'}`}>
          {data.plan_versions.length} plan{data.plan_versions.length !== 1 ? 's' : ''} / {data.changes.length} changes
        </span>
      </div>

      {/* Content */}
      <div className="flex-1 overflow-y-auto min-h-0">
        {hasReqs && view === 'groups' ? (
          <GroupsView data={data} />
        ) : (
          <div className="p-2">
            <DependencyTree changes={data.changes} />
          </div>
        )}
      </div>
    </div>
  )
}

function GroupsView({ data }: { data: RequirementsData }) {
  // Build change lookup
  const changeMap = useMemo(() => {
    const m = new Map<string, ReqChangeInfo>()
    for (const c of data.changes) m.set(c.name, c)
    return m
  }, [data.changes])

  // Only expand groups that have active/failed items by default
  const [expanded, setExpanded] = useState<Set<string>>(() => {
    const active = new Set<string>()
    for (const g of data.groups) {
      if (g.in_progress > 0 || g.failed > 0) active.add(g.group)
    }
    return active
  })

  const toggle = (group: string) => {
    setExpanded(prev => {
      const next = new Set(prev)
      if (next.has(group)) next.delete(group)
      else next.add(group)
      return next
    })
  }

  return (
    <div className="divide-y divide-neutral-800/50">
      {data.groups.map(g => {
        const pct = g.total > 0 ? Math.round((g.done / g.total) * 100) : 0
        const isOpen = expanded.has(g.group)
        return (
          <div key={g.group}>
            <div
              className="flex items-center gap-3 px-4 py-2 cursor-pointer hover:bg-neutral-800/30"
              onClick={() => toggle(g.group)}
            >
              <span className="text-neutral-500 w-3 text-center text-[10px]">
                {isOpen ? '▾' : '▸'}
              </span>
              <span className="text-xs font-medium text-neutral-300 w-16">{g.group}</span>
              <div className="flex-1 max-w-[200px]">
                <ProgressBar done={g.done} inProgress={g.in_progress} failed={g.failed} total={g.total} />
              </div>
              <span className="text-[11px] text-neutral-400 w-16 text-right">{g.done}/{g.total}</span>
              <span className="text-[10px] text-neutral-500 w-10 text-right">{pct}%</span>
              {g.in_progress > 0 && (
                <span className="text-[10px] text-green-400">{g.in_progress} active</span>
              )}
              {g.failed > 0 && (
                <span className="text-[10px] text-red-400">{g.failed} failed</span>
              )}
            </div>
            {isOpen && (
              <div className="px-4 pb-2">
                <table className="w-full text-[11px]">
                  <tbody>
                    {g.requirements.map(req => {
                      const ch = changeMap.get(req.change)
                      const statusColor = STATUS_TEXT[req.status] ?? 'text-neutral-600'
                      return (
                        <tr key={req.id} className="hover:bg-neutral-800/20">
                          <td className="py-0.5 pl-6 font-mono text-neutral-400 w-32">{req.id}</td>
                          <td className={`py-0.5 w-20 ${statusColor}`}>{req.status}</td>
                          <td className="py-0.5 font-mono text-neutral-500 truncate">
                            {req.change}
                            {ch?.complexity && (
                              <span className="ml-2 text-neutral-600">[{ch.complexity}]</span>
                            )}
                          </td>
                        </tr>
                      )
                    })}
                  </tbody>
                </table>
              </div>
            )}
          </div>
        )
      })}
    </div>
  )
}

function extractDigestReqs(data: DigestData): DigestReq[] {
  const raw = data.requirements
  if (!raw) return []
  if (!Array.isArray(raw) && typeof raw === 'object' && 'requirements' in raw) {
    return (raw as { requirements: DigestReq[] }).requirements ?? []
  }
  if (Array.isArray(raw) && raw.length === 1 && typeof raw[0] === 'object' && 'requirements' in (raw[0] as Record<string, unknown>)) {
    return (raw[0] as { requirements: DigestReq[] }).requirements ?? []
  }
  if (Array.isArray(raw)) return raw as DigestReq[]
  return []
}

function DigestFallbackView({ project, changes }: { project: string; changes: ReqChangeInfo[] }) {
  const [digestReqs, setDigestReqs] = useState<DigestReq[]>([])
  const [coverage, setCoverage] = useState<Record<string, { change: string; status: string }>>({})
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    let cancelled = false
    const load = () => {
      getDigest(project)
        .then(d => {
          if (cancelled) return
          if (d.exists) {
            setDigestReqs(extractDigestReqs(d))
            setCoverage(d.coverage?.coverage ?? {})
          }
          setLoading(false)
        })
        .catch(() => { if (!cancelled) setLoading(false) })
    }
    load()
    const iv = setInterval(load, 10000)
    return () => { cancelled = true; clearInterval(iv) }
  }, [project])

  // Group by domain — must be before early returns (rules of hooks)
  const byDomain = useMemo(() => {
    if (!Array.isArray(digestReqs) || digestReqs.length === 0) return []
    const groups: Record<string, DigestReq[]> = {}
    for (const r of digestReqs) {
      if (!r?.domain) continue
      if (!groups[r.domain]) groups[r.domain] = []
      groups[r.domain].push(r)
    }
    return Object.entries(groups).sort((a, b) => a[0].localeCompare(b[0]))
  }, [digestReqs])

  if (loading) {
    return <div className="p-4 text-xs text-neutral-500">Loading requirements...</div>
  }

  // No digest reqs either — show change tree
  if (digestReqs.length === 0) {
    const doneS = new Set(['done', 'merged', 'completed', 'skip_merged'])
    const ipS = new Set(['running', 'implementing', 'verifying'])
    const failS = new Set(['failed', 'verify-failed'])
    const tDone = changes.filter(c => doneS.has(c.status)).length
    const tIp = changes.filter(c => ipS.has(c.status)).length
    const tFail = changes.filter(c => failS.has(c.status)).length
    const pct = changes.length > 0 ? Math.round((tDone / changes.length) * 100) : 0
    return (
      <div className="flex flex-col h-full">
        <div className="flex items-center gap-3 px-4 py-1.5 border-b border-neutral-800/50 shrink-0">
          <span className="text-xs font-medium text-neutral-300">{tDone}/{changes.length}</span>
          <span className="text-[10px] text-neutral-500">{pct}%</span>
          <div className="flex-1 max-w-xs">
            <ProgressBar done={tDone} inProgress={tIp} failed={tFail} total={changes.length} />
          </div>
          <span className="text-[10px] text-neutral-600 ml-auto">{changes.length} changes</span>
        </div>
        <div className="flex-1 overflow-y-auto min-h-0 p-2">
          <DependencyTree changes={changes} />
        </div>
      </div>
    )
  }

  // Show digest requirements with coverage
  const doneStatuses = new Set(['done', 'merged', 'completed', 'skip_merged'])
  const coveredCount = Object.keys(coverage).length
  const doneCount = Object.values(coverage).filter(c => doneStatuses.has(c.status)).length
  const totalReqs = digestReqs.length
  const pctDone = totalReqs > 0 ? Math.round((doneCount / totalReqs) * 100) : 0

  return (
    <div className="flex flex-col h-full">
      <div className="flex items-center gap-3 px-4 py-1.5 border-b border-neutral-800/50 shrink-0">
        <span className="text-xs font-medium text-neutral-300">{doneCount}/{totalReqs}</span>
        <span className="text-[10px] text-neutral-500">{pctDone}%</span>
        <div className="flex-1 max-w-xs">
          <ProgressBar done={doneCount} inProgress={coveredCount - doneCount} failed={0} total={totalReqs} />
        </div>
        <span className="text-[10px] text-neutral-600 ml-auto">
          {coveredCount} covered · {byDomain.length} domains
        </span>
      </div>
      <div className="flex-1 overflow-y-auto min-h-0">
        <div className="divide-y divide-neutral-800/50">
          {byDomain.map(([domain, reqs]) => {
            const ipStatuses = new Set(['running', 'implementing', 'verifying', 'failed', 'verify-failed'])
            const hasActive = reqs.some(r => coverage[r.id] && ipStatuses.has(coverage[r.id].status))
            return (
              <DigestDomainGroup key={domain} domain={domain} reqs={reqs} coverage={coverage} defaultOpen={hasActive} />
            )
          })}
        </div>
      </div>
    </div>
  )
}

function DigestDomainGroup({ domain, reqs, coverage, defaultOpen }: {
  domain: string
  reqs: DigestReq[]
  coverage: Record<string, { change: string; status: string }>
  defaultOpen?: boolean
}) {
  const doneStatuses = new Set(['done', 'merged', 'completed', 'skip_merged'])
  const done = reqs.filter(r => coverage[r.id] && doneStatuses.has(coverage[r.id].status)).length
  const pct = reqs.length > 0 ? Math.round((done / reqs.length) * 100) : 0
  const [open, setOpen] = useState(defaultOpen ?? false)

  return (
    <div>
      <div
        className="flex items-center gap-3 px-4 py-2 cursor-pointer hover:bg-neutral-800/30"
        onClick={() => setOpen(v => !v)}
      >
        <span className="text-neutral-500 w-3 text-center text-[10px]">
          {open ? '▾' : '▸'}
        </span>
        <span className="text-xs font-medium text-neutral-300 w-24 truncate">{domain}</span>
        <div className="flex-1 max-w-[200px]">
          <ProgressBar done={done} inProgress={0} failed={0} total={reqs.length} />
        </div>
        <span className="text-[11px] text-neutral-400 w-16 text-right">{done}/{reqs.length}</span>
        <span className="text-[10px] text-neutral-500 w-10 text-right">{pct}%</span>
      </div>
      {open && (
        <div className="px-4 pb-2">
          <table className="w-full text-[11px]">
            <tbody>
              {reqs.map(r => {
                const cov = coverage[r.id]
                const statusColor = cov ? (STATUS_TEXT[cov.status] ?? 'text-neutral-600') : 'text-yellow-500'
                return (
                  <tr key={r.id} className="hover:bg-neutral-800/20">
                    <td className="py-0.5 pl-6 font-mono text-neutral-400 w-28 truncate" title={r.brief}>{r.id}</td>
                    <td className="py-0.5 text-neutral-400 truncate max-w-[200px] hidden md:table-cell" title={r.brief}>{r.title}</td>
                    <td className={`py-0.5 w-20 ${statusColor}`}>{cov?.status ?? 'uncovered'}</td>
                    <td className="py-0.5 font-mono text-neutral-500 truncate">{cov?.change ?? '—'}</td>
                  </tr>
                )
              })}
            </tbody>
          </table>
        </div>
      )}
    </div>
  )
}
