import { useState, useEffect, useMemo, useRef } from 'react'
import { getDigest, getLog, getProjectSessions, getProjectSession, type DigestData, type DigestReq, type SessionInfo } from '../lib/api'

interface Props {
  project: string
}

type DigestTab = 'overview' | 'requirements' | 'domains' | 'triage'

function extractReqs(data: DigestData): DigestReq[] {
  const raw = data.requirements
  if (!raw) return []
  if (Array.isArray(raw) && raw.length === 1 && 'requirements' in (raw[0] as Record<string, unknown>)) {
    return (raw[0] as { requirements: DigestReq[] }).requirements
  }
  return raw as DigestReq[]
}

export default function DigestView({ project }: Props) {
  const [data, setData] = useState<DigestData | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [tab, setTab] = useState<DigestTab>('overview')

  useEffect(() => {
    let cancelled = false
    const load = () => {
      getDigest(project)
        .then(d => { if (!cancelled) { setData(d); setError(null) } })
        .catch(e => { if (!cancelled) setError(String(e)) })
    }
    load()
    // Re-poll until digest exists
    const iv = setInterval(load, 8000)
    return () => { cancelled = true; clearInterval(iv) }
  }, [project])

  if (error) return <div className="p-4 text-xs text-red-400">{error}</div>
  if (!data) return <div className="p-4 text-xs text-neutral-500">Loading digest...</div>
  if (!data.exists) return <DigestPendingView project={project} />

  const reqs = extractReqs(data)
  const coverage = data.coverage?.coverage ?? {}
  const uncovered = data.coverage?.uncovered ?? []
  const domains = data.domains ?? {}
  const hasTriage = !!data.triage

  const tabs: { id: DigestTab; label: string; hidden?: boolean }[] = [
    { id: 'overview', label: 'Overview' },
    { id: 'requirements', label: `Reqs (${reqs.length})` },
    { id: 'domains', label: `Domains (${Object.keys(domains).length})`, hidden: Object.keys(domains).length === 0 },
    { id: 'triage', label: 'Triage', hidden: !hasTriage },
  ]

  return (
    <div className="flex flex-col h-full">
      {/* Sub-tabs */}
      <div className="flex items-center gap-1 px-3 py-1 border-b border-neutral-800/50 shrink-0">
        {tabs.filter(t => !t.hidden).map(t => (
          <button
            key={t.id}
            onClick={() => setTab(t.id)}
            className={`px-2 py-0.5 text-[10px] rounded transition-colors ${
              tab === t.id
                ? 'bg-neutral-700 text-neutral-200'
                : 'text-neutral-500 hover:text-neutral-300'
            }`}
          >
            {t.label}
          </button>
        ))}
        {data.index && (
          <span className="ml-auto text-[10px] text-neutral-600">
            {data.index.file_count} files | {new Date(data.index.timestamp).toLocaleDateString()}
          </span>
        )}
      </div>

      {/* Content */}
      <div className="flex-1 overflow-y-auto min-h-0">
        {tab === 'overview' && <OverviewPanel data={data} reqs={reqs} coverage={coverage} uncovered={uncovered} domains={domains} />}
        {tab === 'requirements' && <RequirementsPanel reqs={reqs} coverage={coverage} />}
        {tab === 'domains' && <DomainsPanel domains={domains} />}
        {tab === 'triage' && data.triage && <MarkdownPanel content={data.triage} />}
      </div>
    </div>
  )
}

function OverviewPanel({ data, reqs, coverage, uncovered, domains }: {
  data: DigestData
  reqs: DigestReq[]
  coverage: Record<string, { change: string; status: string }>
  uncovered: string[]
  domains: Record<string, string>
}) {
  const coveredCount = Object.keys(coverage).length
  const totalReqs = reqs.length
  const doneStatuses = new Set(['done', 'merged', 'completed', 'skip_merged'])
  const doneCount = Object.values(coverage).filter(c => doneStatuses.has(c.status)).length

  // Group reqs by domain
  const domainCounts = useMemo(() => {
    const counts: Record<string, number> = {}
    for (const r of reqs) {
      counts[r.domain] = (counts[r.domain] ?? 0) + 1
    }
    return counts
  }, [reqs])

  return (
    <div className="p-4 space-y-4 text-xs">
      {/* Progress summary */}
      <div className="flex gap-6">
        <div>
          <div className="text-neutral-500">Requirements</div>
          <div className="text-lg font-medium text-neutral-200">{totalReqs}</div>
        </div>
        <div>
          <div className="text-neutral-500">Covered</div>
          <div className="text-lg font-medium text-blue-400">{coveredCount}</div>
        </div>
        <div>
          <div className="text-neutral-500">Done</div>
          <div className="text-lg font-medium text-green-400">{doneCount}</div>
        </div>
        <div>
          <div className="text-neutral-500">Uncovered</div>
          <div className="text-lg font-medium text-yellow-400">{uncovered.length}</div>
        </div>
        <div>
          <div className="text-neutral-500">Domains</div>
          <div className="text-lg font-medium text-neutral-300">{Object.keys(domains).length}</div>
        </div>
      </div>

      {/* Progress bar */}
      {totalReqs > 0 && (
        <div className="flex h-2 rounded-full overflow-hidden bg-neutral-800 max-w-md">
          {doneCount > 0 && <div className="bg-blue-500" style={{ width: `${(doneCount / totalReqs) * 100}%` }} />}
          {(coveredCount - doneCount) > 0 && <div className="bg-neutral-600" style={{ width: `${((coveredCount - doneCount) / totalReqs) * 100}%` }} />}
        </div>
      )}

      {/* Domain breakdown */}
      <div>
        <div className="text-neutral-500 mb-2">Domains</div>
        <div className="grid grid-cols-3 gap-1">
          {Object.entries(domainCounts).sort((a, b) => b[1] - a[1]).map(([domain, count]) => (
            <div key={domain} className="flex items-center gap-2 px-2 py-1 rounded bg-neutral-900/50">
              <span className="text-neutral-300 font-mono">{domain}</span>
              <span className="text-neutral-500 ml-auto">{count}</span>
            </div>
          ))}
        </div>
      </div>

      {/* Execution hints */}
      {data.index?.execution_hints?.suggested_implementation_order && (
        <div>
          <div className="text-neutral-500 mb-2">Implementation Order</div>
          <div className="space-y-0.5">
            {data.index.execution_hints.suggested_implementation_order.map((step, i) => (
              <div key={i} className="text-neutral-400 pl-2">{step}</div>
            ))}
          </div>
        </div>
      )}

      {/* Uncovered list */}
      {uncovered.length > 0 && (
        <div>
          <div className="text-yellow-500 mb-1">Uncovered Requirements</div>
          <div className="font-mono text-neutral-400 flex flex-wrap gap-1">
            {uncovered.map(id => (
              <span key={id} className="px-1.5 py-0.5 bg-yellow-900/20 rounded text-yellow-400">{id}</span>
            ))}
          </div>
        </div>
      )}
    </div>
  )
}

function RequirementsPanel({ reqs, coverage }: {
  reqs: DigestReq[]
  coverage: Record<string, { change: string; status: string }>
}) {
  const [filter, setFilter] = useState('')
  const [domainFilter, setDomainFilter] = useState<string | null>(null)

  const allDomains = useMemo(() => [...new Set(reqs.map(r => r.domain))].sort(), [reqs])

  const filtered = useMemo(() => {
    let result = reqs
    if (domainFilter) result = result.filter(r => r.domain === domainFilter)
    if (filter) {
      const q = filter.toLowerCase()
      result = result.filter(r =>
        r.id.toLowerCase().includes(q) ||
        r.title.toLowerCase().includes(q) ||
        r.brief.toLowerCase().includes(q)
      )
    }
    return result
  }, [reqs, filter, domainFilter])

  return (
    <div className="flex flex-col h-full">
      <div className="flex items-center gap-2 px-3 py-1.5 border-b border-neutral-800/50 shrink-0">
        <input
          type="text"
          value={filter}
          onChange={e => setFilter(e.target.value)}
          placeholder="Filter..."
          className="bg-neutral-800 text-neutral-300 text-[11px] rounded px-2 py-0.5 border border-neutral-700 w-40"
        />
        <select
          value={domainFilter ?? ''}
          onChange={e => setDomainFilter(e.target.value || null)}
          className="bg-neutral-800 text-neutral-300 text-[11px] rounded px-2 py-0.5 border border-neutral-700"
        >
          <option value="">All domains</option>
          {allDomains.map(d => <option key={d} value={d}>{d}</option>)}
        </select>
        <span className="text-[10px] text-neutral-600 ml-auto">{filtered.length} reqs</span>
      </div>
      <div className="flex-1 overflow-y-auto">
        <table className="w-full text-[11px]">
          <thead>
            <tr className="text-neutral-500 border-b border-neutral-800 sticky top-0 bg-neutral-950">
              <th className="text-left px-3 py-1 font-medium w-28">ID</th>
              <th className="text-left px-2 py-1 font-medium">Title</th>
              <th className="text-left px-2 py-1 font-medium w-16">Domain</th>
              <th className="text-left px-2 py-1 font-medium w-28">Change</th>
              <th className="text-left px-2 py-1 font-medium w-16">Status</th>
            </tr>
          </thead>
          <tbody>
            {filtered.map(r => {
              const cov = coverage[r.id]
              return (
                <tr key={r.id} className="border-b border-neutral-800/30 hover:bg-neutral-900/50">
                  <td className="px-3 py-1 font-mono text-neutral-300">{r.id}</td>
                  <td className="px-2 py-1 text-neutral-400" title={r.brief}>{r.title}</td>
                  <td className="px-2 py-1 text-neutral-500">{r.domain}</td>
                  <td className="px-2 py-1 font-mono text-neutral-500 truncate">{cov?.change ?? '—'}</td>
                  <td className={`px-2 py-1 ${cov ? statusColor(cov.status) : 'text-yellow-500'}`}>
                    {cov?.status ?? 'uncovered'}
                  </td>
                </tr>
              )
            })}
          </tbody>
        </table>
      </div>
    </div>
  )
}

function statusColor(status: string): string {
  if (['done', 'merged', 'completed', 'skip_merged'].includes(status)) return 'text-blue-400'
  if (['running', 'implementing'].includes(status)) return 'text-green-400'
  if (['failed', 'verify-failed'].includes(status)) return 'text-red-400'
  return 'text-neutral-500'
}

function DomainsPanel({ domains }: { domains: Record<string, string> }) {
  const [selected, setSelected] = useState<string | null>(Object.keys(domains)[0] ?? null)

  return (
    <div className="flex h-full">
      {/* Domain list */}
      <div className="w-36 shrink-0 border-r border-neutral-800 overflow-y-auto">
        {Object.keys(domains).sort().map(name => (
          <button
            key={name}
            onClick={() => setSelected(name)}
            className={`w-full text-left px-3 py-1.5 text-[11px] transition-colors ${
              selected === name ? 'bg-neutral-800 text-neutral-200' : 'text-neutral-400 hover:bg-neutral-800/50'
            }`}
          >
            {name}
          </button>
        ))}
      </div>
      {/* Content */}
      <div className="flex-1 overflow-y-auto p-3">
        {selected && domains[selected] && <MarkdownPanel content={domains[selected]} />}
      </div>
    </div>
  )
}

function MarkdownPanel({ content }: { content: string }) {
  return (
    <div className="p-3 text-xs text-neutral-400 font-mono whitespace-pre-wrap leading-5">
      {content.split('\n').map((line, i) => {
        if (line.startsWith('## ')) return <div key={i} className="text-neutral-200 font-semibold mt-3 mb-1 text-sm">{line.slice(3)}</div>
        if (line.startsWith('**') && line.endsWith('**')) return <div key={i} className="text-neutral-300 font-medium mt-2">{line.slice(2, -2)}</div>
        if (line.startsWith('**')) return <div key={i} className="text-neutral-300">{line}</div>
        if (line.startsWith('- ')) return <div key={i} className="pl-3 text-neutral-400">{line}</div>
        return <div key={i}>{line || '\u00A0'}</div>
      })}
    </div>
  )
}

function colorSessionLine(line: string): string {
  if (line.startsWith('>>>')) return 'text-neutral-200'
  if (line.startsWith('  [Edit]') || line.startsWith('  [Write]')) return 'text-yellow-400'
  if (line.startsWith('  [Bash]')) return 'text-green-400'
  if (line.startsWith('  [Read]') || line.startsWith('  [Glob]') || line.startsWith('  [Grep]')) return 'text-blue-400'
  if (line.startsWith('  [')) return 'text-cyan-400'
  if (line.startsWith('---')) return 'text-neutral-600'
  return 'text-neutral-400'
}

function DigestPendingView({ project }: { project: string }) {
  const [logLines, setLogLines] = useState<string[]>([])
  const [sessionLines, setSessionLines] = useState<string[]>([])
  const [digestSession, setDigestSession] = useState<SessionInfo | null>(null)
  const bottomRef = useRef<HTMLDivElement>(null)

  // Fetch orchestration log, filter for digest/plan lines
  useEffect(() => {
    let cancelled = false
    const load = () => {
      getLog(project)
        .then(d => {
          if (cancelled) return
          const relevant = d.lines.filter(l => {
            const low = l.toLowerCase()
            return low.includes('digest') || low.includes('plan') || low.includes('spec')
              || low.includes('scan') || low.includes('claude') || low.includes('creating')
              || low.includes('reading') || low.includes('auto-gen') || low.includes('domain')
              || low.includes('requirement') || low.includes('decompos')
          })
          setLogLines(relevant.slice(-30))
        })
        .catch(() => {})
    }
    load()
    const iv = setInterval(load, 5000)
    return () => { cancelled = true; clearInterval(iv) }
  }, [project])

  // Find the most recent Digest session and stream it
  useEffect(() => {
    let cancelled = false
    const findDigest = () => {
      getProjectSessions(project)
        .then(d => {
          if (cancelled) return
          // Find newest Digest session
          const ds = d.sessions.find(s => s.label === 'Digest')
          if (ds) setDigestSession(ds)
          else {
            // Fallback: most recent Planner session
            const ps = d.sessions.find(s => s.label === 'Planner')
            if (ps) setDigestSession(ps)
          }
        })
        .catch(() => {})
    }
    findDigest()
    const iv = setInterval(findDigest, 10000)
    return () => { cancelled = true; clearInterval(iv) }
  }, [project])

  // Stream the digest/planner session content
  useEffect(() => {
    if (!digestSession) return
    let cancelled = false
    const load = () => {
      getProjectSession(project, digestSession.id, 100)
        .then(d => { if (!cancelled) setSessionLines(d.lines) })
        .catch(() => {})
    }
    load()
    const iv = setInterval(load, 4000)
    return () => { cancelled = true; clearInterval(iv) }
  }, [project, digestSession])

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [sessionLines])

  return (
    <div className="flex flex-col h-full">
      {/* Header */}
      <div className="px-4 py-2 border-b border-neutral-800/50 shrink-0">
        <div className="flex items-center gap-2">
          <span className="text-xs text-neutral-300 font-medium">Digest generating...</span>
          <span className="w-2 h-2 rounded-full bg-green-500 animate-pulse" />
        </div>
        <div className="text-[10px] text-neutral-500 mt-0.5">
          Parsing specs into requirements, domains, and coverage map
        </div>
      </div>

      {/* Orchestration log (digest-relevant lines) */}
      {logLines.length > 0 && (
        <div className="px-4 py-2 border-b border-neutral-800/50 shrink-0 max-h-32 overflow-y-auto">
          <div className="text-[10px] text-neutral-600 mb-1">Orchestration Log</div>
          {logLines.map((line, i) => (
            <div key={i} className="text-[11px] text-neutral-400 font-mono whitespace-pre-wrap break-all leading-4">
              {line}
            </div>
          ))}
        </div>
      )}

      {/* Live session output */}
      <div className="flex-1 overflow-y-auto min-h-0 p-3">
        {digestSession ? (
          <>
            <div className="text-[10px] text-neutral-600 mb-2">
              {digestSession.label} session · {(digestSession.size / 1024).toFixed(0)}KB
            </div>
            {sessionLines.map((line, i) => (
              <div key={i} className={`text-[11px] font-mono whitespace-pre-wrap break-all leading-5 ${colorSessionLine(line)}`}>
                {line}
              </div>
            ))}
            <div ref={bottomRef} />
          </>
        ) : (
          <div className="text-xs text-neutral-500">Waiting for session to start...</div>
        )}
      </div>
    </div>
  )
}
