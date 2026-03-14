import { useState, useEffect, useMemo, useRef } from 'react'
import { getDigest, getLog, getProjectSessions, getProjectSession, type DigestData, type DigestReq, type SessionInfo } from '../lib/api'

interface Props {
  project: string
}

type DigestTab = 'overview' | 'requirements' | 'domains' | 'triage'

function extractReqs(data: DigestData): DigestReq[] {
  const raw = data.requirements
  if (!raw) return []
  // raw is {requirements: [...]} dict
  if (!Array.isArray(raw) && typeof raw === 'object' && 'requirements' in raw) {
    return (raw as { requirements: DigestReq[] }).requirements ?? []
  }
  // raw is [{requirements: [...]}] wrapped in array
  if (Array.isArray(raw) && raw.length === 1 && typeof raw[0] === 'object' && 'requirements' in (raw[0] as Record<string, unknown>)) {
    return (raw[0] as { requirements: DigestReq[] }).requirements ?? []
  }
  if (Array.isArray(raw)) return raw as DigestReq[]
  return []
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
        {tab === 'overview' && <OverviewPanel reqs={reqs} coverage={coverage} uncovered={uncovered} domains={domains} />}
        {tab === 'requirements' && <RequirementsPanel reqs={reqs} coverage={coverage} />}
        {tab === 'domains' && <DomainsPanel domains={domains} />}
        {tab === 'triage' && data.triage && <MarkdownPanel content={data.triage} />}
      </div>
    </div>
  )
}

function OverviewPanel({ reqs, coverage, uncovered, domains }: {
  reqs: DigestReq[]
  coverage: Record<string, { change: string; status: string }>
  uncovered: string[]
  domains: Record<string, string>
}) {
  const [showAll, setShowAll] = useState(false)
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

  const MOBILE_LIMIT = 20
  const visibleReqs = showAll ? reqs : reqs.slice(0, MOBILE_LIMIT)
  const hasMore = reqs.length > MOBILE_LIMIT && !showAll

  return (
    <div className="p-3 space-y-3 text-xs">
      {/* Compact progress row */}
      <div className="flex items-center gap-3 text-[11px]">
        <span className="text-neutral-200 font-medium">{doneCount}/{totalReqs}</span>
        {totalReqs > 0 && (
          <div className="flex-1 h-1.5 rounded-full overflow-hidden bg-neutral-800 max-w-xs">
            {doneCount > 0 && <div className="h-full bg-blue-500" style={{ width: `${(doneCount / totalReqs) * 100}%` }} />}
          </div>
        )}
        <span className="text-blue-400">{coveredCount} covered</span>
        {uncovered.length > 0 && <span className="text-yellow-400">{uncovered.length} uncovered</span>}
        <span className="text-neutral-500">{Object.keys(domains).length} domains</span>
      </div>

      {/* Requirements table — compact, capped on mobile */}
      <table className="w-full text-[11px]">
        <thead>
          <tr className="text-neutral-500 border-b border-neutral-800">
            <th className="text-left px-2 py-1 font-medium">Req</th>
            <th className="text-left px-2 py-1 font-medium hidden md:table-cell">Title</th>
            <th className="text-left px-2 py-1 font-medium">Domain</th>
            <th className="text-left px-2 py-1 font-medium">Change</th>
            <th className="text-left px-2 py-1 font-medium">Status</th>
          </tr>
        </thead>
        <tbody>
          {visibleReqs.map(r => {
            const cov = coverage[r.id]
            return (
              <tr key={r.id} className="border-b border-neutral-800/30">
                <td className="px-2 py-1 font-mono text-neutral-300 truncate max-w-[100px]" title={r.brief}>{r.id}</td>
                <td className="px-2 py-1 text-neutral-400 truncate max-w-[200px] hidden md:table-cell" title={r.brief}>{r.title}</td>
                <td className="px-2 py-1 text-neutral-500 truncate max-w-[80px]">{r.domain}</td>
                <td className="px-2 py-1 font-mono text-neutral-500 truncate max-w-[100px]">{cov?.change ?? '—'}</td>
                <td className={`px-2 py-1 ${cov ? statusColor(cov.status) : 'text-yellow-500'}`}>
                  {cov?.status ?? '—'}
                </td>
              </tr>
            )
          })}
        </tbody>
      </table>

      {hasMore && (
        <button
          onClick={() => setShowAll(true)}
          className="w-full py-1.5 text-[11px] text-neutral-400 hover:text-neutral-200 bg-neutral-800/50 rounded transition-colors"
        >
          Show all {reqs.length} requirements ({reqs.length - MOBILE_LIMIT} more)
        </button>
      )}

      {/* Domain summary — compact inline */}
      {Object.keys(domainCounts).length > 0 && (
        <div className="flex flex-wrap gap-1">
          {Object.entries(domainCounts).sort((a, b) => b[1] - a[1]).map(([domain, count]) => (
            <span key={domain} className="px-1.5 py-0.5 bg-neutral-900/50 rounded text-[10px] text-neutral-400">
              {domain} <span className="text-neutral-600">{count}</span>
            </span>
          ))}
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
  const sortedDomains = Object.keys(domains).sort()

  return (
    <div className="flex flex-col md:flex-row h-full">
      {/* Mobile: dropdown domain picker */}
      <div className="flex items-center gap-2 px-3 py-2 border-b border-neutral-800 md:hidden shrink-0">
        <select
          value={selected ?? ''}
          onChange={e => setSelected(e.target.value || null)}
          className="bg-neutral-800 text-neutral-300 text-[11px] rounded px-2 py-1 border border-neutral-700 flex-1"
        >
          {sortedDomains.map(name => (
            <option key={name} value={name}>{name}</option>
          ))}
        </select>
      </div>

      {/* Desktop: domain list sidebar */}
      <div className="hidden md:block w-36 shrink-0 border-r border-neutral-800 overflow-y-auto">
        {sortedDomains.map(name => (
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
      <div className="flex-1 overflow-y-auto p-3 min-h-0">
        {selected && domains[selected] && <MarkdownPanel content={domains[selected]} />}
      </div>
    </div>
  )
}

function parseTableRows(line: string): string[] {
  return line.split('|').slice(1, -1).map(cell => cell.trim())
}

function isTableSep(line: string): boolean {
  return /^\|[\s:?-]+\|/.test(line) && line.replace(/[\s|:-]/g, '').length === 0
}

function MarkdownPanel({ content }: { content: string }) {
  const lines = content.split('\n')
  const elements: React.ReactNode[] = []
  let i = 0

  while (i < lines.length) {
    const line = lines[i]

    // Detect markdown table: header row + separator row
    if (line.trim().startsWith('|') && i + 1 < lines.length && isTableSep(lines[i + 1])) {
      const headers = parseTableRows(line)
      i += 2 // skip header + separator
      const rows: string[][] = []
      while (i < lines.length && lines[i].trim().startsWith('|') && !isTableSep(lines[i])) {
        rows.push(parseTableRows(lines[i]))
        i++
      }
      elements.push(
        <table key={`tbl-${i}`} className="w-full text-[11px] my-2 border-collapse">
          <thead>
            <tr className="border-b border-neutral-700">
              {headers.map((h, hi) => (
                <th key={hi} className="text-left px-2 py-1 font-medium text-neutral-300">{h}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {rows.map((row, ri) => (
              <tr key={ri} className="border-b border-neutral-800/30 hover:bg-neutral-900/50">
                {row.map((cell, ci) => (
                  <td key={ci} className="px-2 py-1 text-neutral-400">{cell}</td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      )
      continue
    }

    // Regular line rendering
    if (line.startsWith('# ')) {
      elements.push(<div key={i} className="text-neutral-100 font-bold mt-4 mb-1 text-base">{line.slice(2)}</div>)
    } else if (line.startsWith('## ')) {
      elements.push(<div key={i} className="text-neutral-200 font-semibold mt-3 mb-1 text-sm">{line.slice(3)}</div>)
    } else if (line.startsWith('### ')) {
      elements.push(<div key={i} className="text-neutral-300 font-medium mt-2 mb-0.5 text-xs">{line.slice(4)}</div>)
    } else if (line.startsWith('**') && line.endsWith('**')) {
      elements.push(<div key={i} className="text-neutral-300 font-medium mt-2">{line.slice(2, -2)}</div>)
    } else if (line.startsWith('**')) {
      elements.push(<div key={i} className="text-neutral-300">{line}</div>)
    } else if (line.startsWith('- [x] ')) {
      elements.push(<div key={i} className="pl-3 text-blue-400">{line}</div>)
    } else if (line.startsWith('- [ ] ')) {
      elements.push(<div key={i} className="pl-3 text-neutral-500">{line}</div>)
    } else if (line.startsWith('- ')) {
      elements.push(<div key={i} className="pl-3 text-neutral-400">{line}</div>)
    } else {
      elements.push(<div key={i}>{line || '\u00A0'}</div>)
    }
    i++
  }

  return (
    <div className="p-3 text-xs text-neutral-400 font-mono whitespace-pre-wrap leading-5">
      {elements}
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
