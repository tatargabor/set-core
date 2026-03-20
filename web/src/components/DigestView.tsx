import { useState, useEffect, useMemo, useCallback, useRef, Fragment } from 'react'
import { getDigest, getCoverageReport, getRequirements, getLog, getProjectSessions, getProjectSession, type DigestData, type DigestReq, type SessionInfo, type RequirementsData, type ReqChangeInfo } from '../lib/api'

interface Props {
  project: string
}

type DigestTab = 'overview' | 'requirements' | 'domains' | 'triage' | 'ac' | 'coverage' | 'deptree'

type Ambiguity = NonNullable<DigestData['ambiguities']>[number]
type Dependency = { from: string; to: string; type: string }

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

const DONE_STATUSES = new Set(['done', 'merged', 'completed', 'skip_merged'])

function isReqDone(reqId: string, coverage: Record<string, { change: string; status: string }>): boolean {
  const cov = coverage[reqId]
  return !!cov && DONE_STATUSES.has(cov.status)
}

/** Render AC items for a requirement as checkbox-style lines */
function ACItems({ req, coverage }: {
  req: DigestReq
  coverage: Record<string, { change: string; status: string }>
}) {
  const ac = req.acceptance_criteria
  if (!ac || ac.length === 0) return null
  const done = isReqDone(req.id, coverage)

  return (
    <div className="pl-6 py-1 space-y-0.5">
      {ac.map((item, i) => (
        <div key={i} className={`text-[11px] flex items-start gap-1.5 ${done ? 'text-blue-400' : 'text-neutral-500'}`}>
          <span className="shrink-0 mt-0.5">{done ? '\u2611' : '\u2610'}</span>
          <span>{item}</span>
        </div>
      ))}
    </div>
  )
}

export default function DigestView({ project }: Props) {
  const [data, setData] = useState<DigestData | null>(null)
  const [error, setError] = useState<string | null>(null)
  // URL-backed sub-tab: ?sub=domains (default: domains)
  const VALID_TABS: DigestTab[] = ['domains', 'overview', 'ac', 'coverage', 'deptree', 'triage']
  const initTab = useMemo(() => {
    const s = new URLSearchParams(window.location.search).get('sub')
    return (s && VALID_TABS.includes(s as DigestTab)) ? s as DigestTab : 'domains'
  }, [])
  const [tab, setTabRaw] = useState<DigestTab>(initTab)
  const setTab = useCallback((t: DigestTab) => {
    setTabRaw(t)
    const url = new URL(window.location.href)
    url.searchParams.set('sub', t)
    window.history.replaceState(null, '', url.toString())
  }, [])

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
  // Prefer coverage-merged over coverage when it has actual entries
  const mergedCov = data.coverage_merged?.coverage ?? {}
  const coverageSource = Object.keys(mergedCov).length > 0 ? data.coverage_merged : data.coverage
  const coverage = coverageSource?.coverage ?? {}
  const uncovered = coverageSource?.uncovered ?? []
  const domains = data.domains ?? {}
  const hasTriage = !!data.triage
  const dependencies: Dependency[] = data.dependencies?.dependencies ?? []
  const rawAmb = data.ambiguities
  const ambiguities: Ambiguity[] = Array.isArray(rawAmb) ? rawAmb : (rawAmb as unknown as { ambiguities: Ambiguity[] })?.ambiguities ?? []

  // Count total AC items
  const totalAC = reqs.reduce((sum, r) => sum + (r.acceptance_criteria?.length ?? 0), 0)

  const tabs: { id: DigestTab; label: string; hidden?: boolean }[] = [
    { id: 'domains', label: `Domains (${Object.keys(domains).length})`, hidden: Object.keys(domains).length === 0 },
    { id: 'overview', label: `Reqs (${reqs.length})` },
    { id: 'ac', label: `AC (${totalAC})`, hidden: totalAC === 0 },
    { id: 'coverage', label: 'Coverage' },
    { id: 'deptree', label: 'Dep Tree' },
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
        {tab === 'ac' && <ACPanel reqs={reqs} coverage={coverage} />}
        {tab === 'domains' && <DomainsPanel domains={domains} reqs={reqs} coverage={coverage} dependencies={dependencies} ambiguities={ambiguities} />}
        {tab === 'coverage' && <CoverageReportPanel project={project} />}
        {tab === 'deptree' && <DepTreePanel project={project} />}
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
  const [expandedReqs, setExpandedReqs] = useState<Set<number>>(new Set())
  const toggleReq = (idx: number) => setExpandedReqs(prev => {
    const next = new Set(prev)
    if (next.has(idx)) next.delete(idx); else next.add(idx)
    return next
  })
  const coveredCount = Object.keys(coverage).length
  const totalReqs = reqs.length
  const doneCount = Object.values(coverage).filter(c => DONE_STATUSES.has(c.status)).length

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
        <span className="text-neutral-200 font-medium">{doneCount}/{totalReqs} merged</span>
        {totalReqs > 0 && (
          <div className="flex-1 h-1.5 rounded-full overflow-hidden bg-neutral-800 max-w-xs">
            {coveredCount > 0 && <div className="h-full bg-neutral-700" style={{ width: `${(coveredCount / totalReqs) * 100}%` }} />}
            {doneCount > 0 && <div className="h-full bg-blue-500 -mt-1.5" style={{ width: `${(doneCount / totalReqs) * 100}%` }} />}
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
            <th className="text-left px-2 py-1 font-medium">
              <span>Req</span>
              <button
                onClick={() => setExpandedReqs(new Set(reqs.map((r, i) => (r.acceptance_criteria?.length ?? 0) > 0 ? i : -1).filter(i => i >= 0)))}
                className="ml-2 px-1.5 py-0.5 text-[10px] text-neutral-400 hover:text-neutral-200 bg-neutral-800 hover:bg-neutral-700 rounded" title="Expand All"
              >Expand All</button>
              <button
                onClick={() => setExpandedReqs(new Set())}
                className="ml-1 px-1.5 py-0.5 text-[10px] text-neutral-400 hover:text-neutral-200 bg-neutral-800 hover:bg-neutral-700 rounded" title="Collapse All"
              >Collapse</button>
            </th>
            <th className="text-left px-2 py-1 font-medium hidden md:table-cell">Title</th>
            <th className="text-left px-2 py-1 font-medium">Domain</th>
            <th className="text-left px-2 py-1 font-medium">Change</th>
            <th className="text-left px-2 py-1 font-medium">Status</th>
          </tr>
        </thead>
        <tbody>
          {visibleReqs.map((r, idx) => {
            const cov = coverage[r.id]
            const hasAC = (r.acceptance_criteria?.length ?? 0) > 0
            const isExpanded = expandedReqs.has(idx)
            return (
              <Fragment key={idx}>
                <tr
                  className={`border-b border-neutral-800/30 ${hasAC ? 'cursor-pointer hover:bg-neutral-900/50' : ''}`}
                  onClick={hasAC ? () => toggleReq(idx) : undefined}
                >
                  <td className="px-2 py-1 font-mono text-neutral-300 truncate max-w-[100px]" title={r.brief}>
                    {hasAC && <span className="text-neutral-600 mr-1">{isExpanded ? '\u25BE' : '\u25B8'}</span>}
                    {r.id}
                  </td>
                  <td className="px-2 py-1 text-neutral-400 truncate max-w-[200px] hidden md:table-cell" title={r.brief}>{r.title}</td>
                  <td className="px-2 py-1 text-neutral-500 truncate max-w-[80px]">{r.domain}</td>
                  <td className="px-2 py-1 font-mono text-neutral-500 truncate max-w-[100px]">{cov?.change ?? '\u2014'}</td>
                  <td className={`px-2 py-1 ${cov ? statusColor(cov.status) : 'text-yellow-500'}`}>
                    {cov?.status ?? '\u2014'}
                  </td>
                </tr>
                {isExpanded && hasAC && (
                  <tr className="border-b border-neutral-800/30 bg-neutral-950/30">
                    <td colSpan={5}>
                      <ACItems req={r} coverage={coverage} />
                    </td>
                  </tr>
                )}
              </Fragment>
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

function ACPanel({ reqs, coverage }: {
  reqs: DigestReq[]
  coverage: Record<string, { change: string; status: string }>
}) {
  const [domainFilter, setDomainFilter] = useState<string | null>(null)

  // Filter to reqs with AC
  const reqsWithAC = useMemo(() => reqs.filter(r => (r.acceptance_criteria?.length ?? 0) > 0), [reqs])

  if (reqsWithAC.length === 0) {
    return <div className="p-4 text-xs text-neutral-500">No acceptance criteria extracted</div>
  }

  const allDomains = [...new Set(reqsWithAC.map(r => r.domain))].sort()
  const filtered = domainFilter ? reqsWithAC.filter(r => r.domain === domainFilter) : reqsWithAC

  const totalAC = filtered.reduce((sum, r) => sum + (r.acceptance_criteria?.length ?? 0), 0)
  const checkedAC = filtered.reduce((sum, r) => {
    if (!isReqDone(r.id, coverage)) return sum
    return sum + (r.acceptance_criteria?.length ?? 0)
  }, 0)
  const pct = totalAC > 0 ? Math.round((checkedAC / totalAC) * 100) : 0

  // Group by domain
  const byDomain = useMemo(() => {
    const groups: Record<string, DigestReq[]> = {}
    for (const r of filtered) {
      if (!groups[r.domain]) groups[r.domain] = []
      groups[r.domain].push(r)
    }
    return Object.entries(groups).sort((a, b) => a[0].localeCompare(b[0]))
  }, [filtered])

  return (
    <div className="flex flex-col h-full">
      {/* Header: progress + filter */}
      <div className="flex items-center gap-3 px-3 py-1.5 border-b border-neutral-800/50 shrink-0">
        <span className="text-xs font-medium text-neutral-300">{checkedAC}/{totalAC} AC</span>
        <span className="text-[10px] text-neutral-500">{pct}%</span>
        <div className="flex-1 h-1.5 rounded-full overflow-hidden bg-neutral-800 max-w-xs">
          {checkedAC > 0 && <div className="h-full bg-blue-500 transition-all" style={{ width: `${pct}%` }} />}
        </div>
        <select
          value={domainFilter ?? ''}
          onChange={e => setDomainFilter(e.target.value || null)}
          className="bg-neutral-800 text-neutral-300 text-[11px] rounded px-2 py-0.5 border border-neutral-700 ml-auto"
        >
          <option value="">All domains</option>
          {allDomains.map(d => <option key={d} value={d}>{d}</option>)}
        </select>
      </div>

      {/* Domain groups */}
      <div className="flex-1 overflow-y-auto min-h-0">
        {byDomain.map(([domain, domReqs]) => {
          const domTotalAC = domReqs.reduce((s, r) => s + (r.acceptance_criteria?.length ?? 0), 0)
          const domCheckedAC = domReqs.reduce((s, r) => {
            if (!isReqDone(r.id, coverage)) return s
            return s + (r.acceptance_criteria?.length ?? 0)
          }, 0)
          return (
            <div key={domain} className="border-b border-neutral-800/50">
              <div className="flex items-center gap-2 px-3 py-1.5 bg-neutral-900/30">
                <span className="text-[11px] font-medium text-neutral-300">{domain}</span>
                <span className="text-[10px] text-neutral-500">{domCheckedAC}/{domTotalAC}</span>
              </div>
              {domReqs.map(r => (
                <div key={r.id} className="px-3 py-1">
                  <div className="text-[11px] text-neutral-400 mb-0.5">
                    <span className="font-mono text-neutral-500">{r.id}</span>
                    <span className="mx-1 text-neutral-700">/</span>
                    <span>{r.title}</span>
                  </div>
                  {(r.acceptance_criteria ?? []).map((ac, i) => {
                    const done = isReqDone(r.id, coverage)
                    return (
                      <div key={i} className={`text-[11px] flex items-start gap-1.5 pl-4 ${done ? 'text-blue-400' : 'text-neutral-500'}`}>
                        <span className="shrink-0 mt-0.5">{done ? '\u2611' : '\u2610'}</span>
                        <span>{ac}</span>
                      </div>
                    )
                  })}
                </div>
              ))}
            </div>
          )
        })}
      </div>
    </div>
  )
}

function CoverageReportPanel({ project }: { project: string }) {
  const [content, setContent] = useState<string | null>(null)
  const [exists, setExists] = useState<boolean | null>(null)

  useEffect(() => {
    let cancelled = false
    getCoverageReport(project)
      .then(d => {
        if (cancelled) return
        setExists(d.exists)
        if (d.exists && d.content) setContent(d.content)
      })
      .catch(() => { if (!cancelled) setExists(false) })
    return () => { cancelled = true }
  }, [project])

  if (exists === null) return <div className="p-4 text-xs text-neutral-500">Loading coverage report...</div>
  if (!exists || !content) return <div className="p-4 text-xs text-neutral-500">No coverage report generated yet</div>

  return <MarkdownPanel content={content} />
}

function statusColor(status: string): string {
  if (['done', 'merged', 'completed', 'skip_merged'].includes(status)) return 'text-blue-400'
  if (['running', 'implementing'].includes(status)) return 'text-green-400'
  if (['failed', 'verify-failed'].includes(status)) return 'text-red-400'
  if (status === 'planned') return 'text-neutral-400'
  return 'text-neutral-500'
}

function DomainsPanel({ domains, reqs, coverage, dependencies, ambiguities }: {
  domains: Record<string, string>
  reqs: DigestReq[]
  coverage: Record<string, { change: string; status: string }>
  dependencies: Dependency[]
  ambiguities: Ambiguity[]
}) {
  const [selected, setSelected] = useState<string | null>(Object.keys(domains)[0] ?? null)
  const sortedDomains = Object.keys(domains).sort()

  // Pre-compute per-domain stats
  const domainStats = useMemo(() => {
    const stats: Record<string, { reqs: DigestReq[]; done: number; total: number }> = {}
    for (const name of sortedDomains) {
      const domReqs = reqs.filter(r => r.domain === name)
      const done = domReqs.filter(r => isReqDone(r.id, coverage)).length
      stats[name] = { reqs: domReqs, done, total: domReqs.length }
    }
    return stats
  }, [sortedDomains, reqs, coverage])

  // Cross-domain dependency edges
  const domainEdges = useMemo(() => {
    const reqDomain = new Map<string, string>()
    for (const r of reqs) reqDomain.set(r.id, r.domain)
    const incoming: Record<string, { from: string; fromReq: string; toReq: string }[]> = {}
    const outgoing: Record<string, { to: string; fromReq: string; toReq: string }[]> = {}
    for (const dep of dependencies) {
      const fromDom = reqDomain.get(dep.from)
      const toDom = reqDomain.get(dep.to)
      if (fromDom && toDom && fromDom !== toDom) {
        if (!outgoing[fromDom]) outgoing[fromDom] = []
        outgoing[fromDom].push({ to: toDom, fromReq: dep.from, toReq: dep.to })
        if (!incoming[toDom]) incoming[toDom] = []
        incoming[toDom].push({ from: fromDom, fromReq: dep.from, toReq: dep.to })
      }
    }
    return { incoming, outgoing }
  }, [reqs, dependencies])

  // Ambiguities by domain
  const domainAmbiguities = useMemo(() => {
    const reqDomain = new Map<string, string>()
    for (const r of reqs) reqDomain.set(r.id, r.domain)
    const byDom: Record<string, Ambiguity[]> = {}
    for (const amb of ambiguities) {
      const affected = amb.affects_requirements ?? []
      const domains = new Set(affected.map(id => reqDomain.get(id)).filter(Boolean) as string[])
      for (const d of domains) {
        if (!byDom[d]) byDom[d] = []
        byDom[d].push(amb)
      }
    }
    return byDom
  }, [reqs, ambiguities])

  return (
    <div className="flex flex-col md:flex-row h-full">
      {/* Mobile: dropdown domain picker with progress */}
      <div className="flex items-center gap-2 px-3 py-2 border-b border-neutral-800 md:hidden shrink-0">
        <select
          value={selected ?? ''}
          onChange={e => setSelected(e.target.value || null)}
          className="bg-neutral-800 text-neutral-300 text-[11px] rounded px-2 py-1 border border-neutral-700 flex-1"
        >
          {sortedDomains.map(name => {
            const s = domainStats[name]
            return (
              <option key={name} value={name}>
                {name} ({s?.done ?? 0}/{s?.total ?? 0})
              </option>
            )
          })}
        </select>
      </div>

      {/* Desktop: domain list sidebar with mini progress bars */}
      <div className="hidden md:block w-44 shrink-0 border-r border-neutral-800 overflow-y-auto">
        {sortedDomains.map(name => {
          const s = domainStats[name]
          const pct = s && s.total > 0 ? (s.done / s.total) * 100 : 0
          const allDone = s && s.total > 0 && s.done === s.total
          return (
            <button
              key={name}
              onClick={() => setSelected(name)}
              className={`w-full text-left px-3 py-1.5 transition-colors ${
                selected === name ? 'bg-neutral-800 text-neutral-200' : 'text-neutral-400 hover:bg-neutral-800/50'
              }`}
            >
              <div className="flex items-center gap-1.5 text-[11px]">
                <span className="truncate flex-1">{name}</span>
                <span className="text-[10px] text-neutral-500 shrink-0">
                  {s?.done ?? 0}/{s?.total ?? 0}
                </span>
                {allDone && <span className="text-[10px] text-blue-400 shrink-0">&#10003;</span>}
              </div>
              {s && s.total > 0 && (
                <div className="h-1 rounded-full overflow-hidden bg-neutral-700 mt-1">
                  <div className="h-full bg-blue-500 transition-all" style={{ width: `${pct}%` }} />
                </div>
              )}
            </button>
          )
        })}
      </div>

      {/* Content — enriched domain card */}
      <div className="flex-1 overflow-y-auto min-h-0">
        {selected && (
          <DomainCard
            name={selected}
            summary={domains[selected] ?? ''}
            domReqs={domainStats[selected]?.reqs ?? []}
            coverage={coverage}
            incoming={domainEdges.incoming[selected] ?? []}
            outgoing={domainEdges.outgoing[selected] ?? []}
            ambiguities={domainAmbiguities[selected] ?? []}
          />
        )}
      </div>
    </div>
  )
}

function DomainCard({ name, summary, domReqs, coverage, incoming, outgoing, ambiguities: domAmbs }: {
  name: string
  summary: string
  domReqs: DigestReq[]
  coverage: Record<string, { change: string; status: string }>
  incoming: { from: string; fromReq: string; toReq: string }[]
  outgoing: { to: string; fromReq: string; toReq: string }[]
  ambiguities: Ambiguity[]
}) {
  const [expandedReq, setExpandedReq] = useState<string | null>(null)

  const done = domReqs.filter(r => isReqDone(r.id, coverage)).length
  const total = domReqs.length
  const pct = total > 0 ? Math.round((done / total) * 100) : 0

  // AC stats
  const totalAC = domReqs.reduce((s, r) => s + (r.acceptance_criteria?.length ?? 0), 0)
  const doneAC = domReqs.reduce((s, r) => {
    if (!isReqDone(r.id, coverage)) return s
    return s + (r.acceptance_criteria?.length ?? 0)
  }, 0)
  const acPct = totalAC > 0 ? Math.round((doneAC / totalAC) * 100) : 0

  // Source files
  const sources = useMemo(() => {
    const counts: Record<string, number> = {}
    for (const r of domReqs) {
      counts[r.source] = (counts[r.source] ?? 0) + 1
    }
    return Object.entries(counts).sort((a, b) => b[1] - a[1])
  }, [domReqs])

  // Sort reqs: active/failed first, then pending, then done
  const sortedReqs = useMemo(() => {
    const active = new Set(['running', 'implementing', 'verifying'])
    const failed = new Set(['failed', 'verify-failed'])
    return [...domReqs].sort((a, b) => {
      const ca = coverage[a.id]
      const cb = coverage[b.id]
      const sa = ca?.status ?? ''
      const sb = cb?.status ?? ''
      const order = (s: string) => {
        if (failed.has(s)) return 0
        if (active.has(s)) return 1
        if (!s || s === 'planned') return 2
        if (DONE_STATUSES.has(s)) return 3
        return 2
      }
      return order(sa) - order(sb)
    })
  }, [domReqs, coverage])

  // Group outgoing edges by target domain
  const outByDomain = useMemo(() => {
    const groups: Record<string, { fromReq: string; toReq: string }[]> = {}
    for (const e of outgoing) {
      if (!groups[e.to]) groups[e.to] = []
      groups[e.to].push({ fromReq: e.fromReq, toReq: e.toReq })
    }
    return Object.entries(groups)
  }, [outgoing])

  const inByDomain = useMemo(() => {
    const groups: Record<string, { fromReq: string; toReq: string }[]> = {}
    for (const e of incoming) {
      if (!groups[e.from]) groups[e.from] = []
      groups[e.from].push({ fromReq: e.fromReq, toReq: e.toReq })
    }
    return Object.entries(groups)
  }, [incoming])

  return (
    <div className="p-3 space-y-3 text-xs">
      {/* Summary + Progress */}
      <div>
        <div className="text-neutral-200 font-medium text-sm mb-1">{name}</div>
        {summary && <div className="text-neutral-400 text-[11px] mb-2">{summary}</div>}
        <div className="flex items-center gap-3 text-[11px]">
          <span className="text-neutral-200 font-medium">{done}/{total} merged</span>
          <span className="text-neutral-500">{pct}%</span>
          {total > 0 && (
            <div className="flex-1 h-1.5 rounded-full overflow-hidden bg-neutral-800 max-w-xs">
              <div className="h-full bg-blue-500 transition-all" style={{ width: `${pct}%` }} />
            </div>
          )}
        </div>
        {totalAC > 0 && (
          <div className="flex items-center gap-3 text-[11px] mt-1">
            <span className="text-neutral-300">{doneAC}/{totalAC} AC</span>
            <span className="text-neutral-500">{acPct}%</span>
            <div className="flex-1 h-1 rounded-full overflow-hidden bg-neutral-800 max-w-xs">
              <div className="h-full bg-cyan-600 transition-all" style={{ width: `${acPct}%` }} />
            </div>
          </div>
        )}
      </div>

      {/* Requirements list */}
      {sortedReqs.length > 0 && (
        <div>
          <div className="text-[10px] text-neutral-500 font-medium mb-1 uppercase tracking-wider">Requirements</div>
          <table className="w-full text-[11px]">
            <tbody>
              {sortedReqs.map(r => {
                const cov = coverage[r.id]
                const hasAC = (r.acceptance_criteria?.length ?? 0) > 0
                const isExpanded = expandedReq === r.id
                const isDone = cov && DONE_STATUSES.has(cov.status)
                return (
                  <Fragment key={r.id}>
                    <tr
                      className={`border-b border-neutral-800/30 ${hasAC ? 'cursor-pointer' : ''} hover:bg-neutral-900/50 ${isDone ? 'opacity-60' : ''}`}
                      onClick={hasAC ? () => setExpandedReq(isExpanded ? null : r.id) : undefined}
                    >
                      <td className="px-1 py-1 font-mono text-neutral-400 w-28 truncate" title={r.brief}>
                        {hasAC && <span className="text-neutral-600 mr-1">{isExpanded ? '\u25BE' : '\u25B8'}</span>}
                        {r.id}
                      </td>
                      <td className="px-1 py-1 text-neutral-400 truncate max-w-[200px]" title={r.brief}>{r.title}</td>
                      <td className="px-1 py-1 font-mono text-neutral-500 truncate max-w-[100px]">{cov?.change ?? '\u2014'}</td>
                      <td className={`px-1 py-1 w-20 ${cov ? statusColor(cov.status) : 'text-yellow-500'}`}>
                        {cov?.status ?? 'uncovered'}
                      </td>
                    </tr>
                    {isExpanded && hasAC && (
                      <tr className="border-b border-neutral-800/30 bg-neutral-950/30">
                        <td colSpan={4}>
                          <ACItems req={r} coverage={coverage} />
                        </td>
                      </tr>
                    )}
                  </Fragment>
                )
              })}
            </tbody>
          </table>
        </div>
      )}

      {/* Ambiguities */}
      {domAmbs.length > 0 && (
        <div>
          <div className="text-[10px] text-neutral-500 font-medium mb-1 uppercase tracking-wider">Ambiguities</div>
          <div className="space-y-1.5">
            {domAmbs.map((a, i) => (
              <div key={i} className="flex items-start gap-2 text-[11px]">
                <span className="text-yellow-500 shrink-0 mt-0.5">&#9888;</span>
                <div>
                  <span className={`inline-block px-1 py-0 rounded text-[9px] font-medium mr-1.5 ${
                    a.type === 'contradictory' ? 'bg-red-900/50 text-red-400' :
                    a.type === 'underspecified' ? 'bg-yellow-900/50 text-yellow-400' :
                    a.type === 'missing_reference' ? 'bg-orange-900/50 text-orange-400' :
                    'bg-neutral-800 text-neutral-400'
                  }`}>{a.type}</span>
                  <span className="text-neutral-400">{a.description}</span>
                  {a.resolution === 'planner-resolved' && a.resolution_note && (
                    <div className="text-[10px] text-neutral-500 mt-0.5 pl-2 border-l border-neutral-700">
                      Resolved: {a.resolution_note}
                    </div>
                  )}
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Cross-domain dependencies */}
      {(outByDomain.length > 0 || inByDomain.length > 0) && (
        <div>
          <div className="text-[10px] text-neutral-500 font-medium mb-1 uppercase tracking-wider">Dependencies</div>
          {outByDomain.length > 0 && (
            <div className="mb-1">
              <div className="text-[10px] text-neutral-500 mb-0.5">Depends on:</div>
              {outByDomain.map(([dom, edges]) => (
                <div key={dom} className="text-[11px] text-neutral-400 pl-2">
                  <span className="text-neutral-300">{dom}</span>
                  <span className="text-neutral-600 ml-1">
                    ({edges.map(e => `${e.fromReq}\u2192${e.toReq}`).join(', ')})
                  </span>
                </div>
              ))}
            </div>
          )}
          {inByDomain.length > 0 && (
            <div>
              <div className="text-[10px] text-neutral-500 mb-0.5">Depended on by:</div>
              {inByDomain.map(([dom, edges]) => (
                <div key={dom} className="text-[11px] text-neutral-400 pl-2">
                  <span className="text-neutral-300">{dom}</span>
                  <span className="text-neutral-600 ml-1">
                    ({edges.map(e => `${e.fromReq}\u2192${e.toReq}`).join(', ')})
                  </span>
                </div>
              ))}
            </div>
          )}
        </div>
      )}

      {/* Source files */}
      {sources.length > 0 && (
        <div>
          <div className="text-[10px] text-neutral-500 font-medium mb-1 uppercase tracking-wider">Sources</div>
          {sources.map(([path, count]) => (
            <div key={path} className="text-[11px] text-neutral-400 pl-2">
              <span className="font-mono">{path}</span>
              <span className="text-neutral-600 ml-1">({count} reqs)</span>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}

/** Dep Tree panel — lazy-loads requirements data for change-level dependency visualization */
function DepTreePanel({ project }: { project: string }) {
  const [data, setData] = useState<RequirementsData | null>(null)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    let cancelled = false
    getRequirements(project)
      .then(d => { if (!cancelled) setData(d) })
      .catch(e => { if (!cancelled) setError(String(e)) })
    return () => { cancelled = true }
  }, [project])

  if (error) return <div className="p-4 text-xs text-red-400">{error}</div>
  if (!data) return <div className="p-4 text-xs text-neutral-500">Loading dependency tree...</div>
  if (data.changes.length === 0) return <div className="p-4 text-xs text-neutral-500">No change data available</div>

  return (
    <div className="p-2">
      <DepTree changes={data.changes} />
    </div>
  )
}

const DEP_STATUS_COLOR: Record<string, string> = {
  merged: 'bg-blue-500', done: 'bg-blue-500', completed: 'bg-blue-500', skip_merged: 'bg-blue-400',
  running: 'bg-green-500', implementing: 'bg-green-500', verifying: 'bg-cyan-500',
  failed: 'bg-red-500', 'verify-failed': 'bg-red-500', stalled: 'bg-yellow-500',
  pending: 'bg-neutral-600', planned: 'bg-neutral-700',
}

const DEP_STATUS_TEXT: Record<string, string> = {
  merged: 'text-blue-400', done: 'text-blue-400', completed: 'text-blue-400',
  running: 'text-green-400', implementing: 'text-green-400', verifying: 'text-cyan-400',
  failed: 'text-red-400', 'verify-failed': 'text-red-400', stalled: 'text-yellow-400',
  pending: 'text-neutral-500', planned: 'text-neutral-600',
}

function DepTree({ changes }: { changes: ReqChangeInfo[] }) {
  const blockedBy = useMemo(() => {
    const map = new Map<string, string[]>()
    for (const c of changes) {
      if (c.depends_on.length > 0) {
        map.set(c.name, c.depends_on.filter(d => changes.some(ch => ch.name === d)))
      }
    }
    return map
  }, [changes])

  const roots = useMemo(() => {
    return changes.filter(c => !blockedBy.has(c.name) || blockedBy.get(c.name)!.length === 0)
  }, [changes, blockedBy])

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
      if (next.has(name)) next.delete(name); else next.add(name)
      return next
    })
  }

  const changeMap = useMemo(() => new Map(changes.map(c => [c.name, c])), [changes])
  const rendered = new Set<string>()

  function renderNode(name: string, depth: number): React.ReactNode {
    if (rendered.has(name)) return null
    rendered.add(name)
    const c = changeMap.get(name)
    if (!c) return null
    const kids = children.get(name) ?? []
    const hasKids = kids.length > 0
    const isExpanded = expanded.has(name)
    const dotColor = DEP_STATUS_COLOR[c.status] ?? 'bg-neutral-700'
    const txtColor = DEP_STATUS_TEXT[c.status] ?? 'text-neutral-600'
    const isDone = DONE_STATUSES.has(c.status)

    return (
      <div key={name}>
        <div
          className={`flex items-center gap-2 py-1 px-2 hover:bg-neutral-800/50 rounded cursor-pointer ${isDone ? 'opacity-60' : ''}`}
          style={{ paddingLeft: `${depth * 20 + 8}px` }}
          onClick={() => hasKids && toggle(name)}
        >
          {hasKids ? (
            <span className="text-neutral-500 w-3 text-center text-[10px]">{isExpanded ? '\u25BE' : '\u25B8'}</span>
          ) : (
            <span className="w-3" />
          )}
          <span className={`w-2 h-2 rounded-full shrink-0 ${dotColor}`} />
          <span className="font-mono text-[11px] text-neutral-300 truncate">{name}</span>
          <span className={`text-[10px] ml-auto shrink-0 ${txtColor}`}>{c.status}</span>
          <span className="text-[10px] text-neutral-600 shrink-0">{c.requirements.length} reqs</span>
        </div>
        {isExpanded && kids.map(kid => renderNode(kid, depth + 1))}
      </div>
    )
  }

  return (
    <div className="space-y-0.5">
      {roots.map(r => renderNode(r.name, 0))}
      {changes.filter(c => !rendered.has(c.name)).map(c => renderNode(c.name, 0))}
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
