/**
 * Is every recently active project committed and pushed? — from the fleet header.
 *
 * Asked for by the owner on 2026-11-24 (openspec change fleet-repo-sync): one screen that
 * shows which projects are not pushed, what the second machine is missing, and which worktrees
 * are still worth keeping, loading "when I open it, not continuously".
 *
 * Three rules shape it:
 *
 * - **Measured only on request.** Nothing is fetched until the table is opened; opening,
 *   the refresh control and the fetch control are the only things that measure.
 * - **The chip never claims a calm it did not measure.** Before the first opening it reads
 *   "not measured"; afterwards it carries the problem count and the age of that count.
 * - **The table floats and is read-only.** It pushes nothing, closes on its own control,
 *   Escape and an outside click, and offers no write control except the remote fetch.
 */

import { Fragment, useCallback, useEffect, useRef, useState } from 'react'
import { ChevronDown, ChevronRight, CloudDownload, FolderGit2, RefreshCw, TriangleAlert, X } from 'lucide-react'

import {
  chipText, longAge, parseRepoSync, problemLabel, syncCell, type RepoRow, type RepoSync,
} from '../lib/fleetRepoSync'

const DAY_CHOICES = [7, 14, 30, 90]

const DEPLOY_TONE: Record<string, string> = {
  yes: 'text-red-400',
  unknown: 'text-amber-400',
  no: 'text-fg-muted',
}

function DeployCell({ row }: { row: RepoRow }) {
  const h = row.push_may_deploy
  const where = h.source ?? 'no file'
  const env = h.environment ? ` → ${h.environment}` : ''
  return (
    <span className={`truncate ${DEPLOY_TONE[h.value]}`} data-repo-sync-deploy={h.value}
          title={`${h.reason}${h.job ? ` (job ${h.job}${env})` : ''} — read from ${where}`}>
      {h.value === 'no' ? 'no' : `${h.value}${env}`}
      {h.value !== 'no' && <span className="text-fg-muted"> · {where}</span>}
    </span>
  )
}

function Detail({ row }: { row: RepoRow }) {
  const branches = row.unpushed_branches
  const wts = row.worktrees
  const errs = Object.entries(row.errors)
  return (
    <div className="pl-5 pb-2 text-xs text-fg-muted space-y-1" data-repo-sync-detail={row.name}>
      <div className="truncate" title={row.path}>{row.path}</div>
      {errs.length > 0 && (
        <div className="text-amber-400">
          {errs.map(([k, v]) => <div key={k}>could not read {k}: {v}</div>)}
        </div>
      )}
      <div>
        <span className="text-fg-strong">Unpushed branches: </span>
        {branches === null ? 'not readable'
          : branches.length === 0 ? 'none'
          : branches.map(b => (
            <span key={b.branch} className="mr-2 whitespace-nowrap">
              {b.branch}{b.current ? ' (current)' : ''} <span className="tabular-nums">+{b.commits}</span>
              <span className="tabular-nums"> · {longAge(b.last_commit_age_s)}</span>
            </span>
          ))}
      </div>
      <div>
        <span className="text-fg-strong">Worktrees: </span>
        {wts === null ? 'not readable' : wts.length === 0 ? 'none' : null}
      </div>
      {wts && wts.length > 0 && (
        <ul className="space-y-0.5">
          {wts.map(w => (
            <li key={w.path} className="grid grid-cols-[minmax(0,1fr)_auto] gap-2" data-repo-sync-worktree={w.missing ? 'missing' : w.merged ? 'merged' : 'open'}>
              <span className="truncate" title={w.path}>{w.branch ?? (w.detached ? 'detached' : '—')} · {w.path}</span>
              <span className="tabular-nums whitespace-nowrap">
                {w.missing ? <span className="text-amber-400">directory gone</span>
                  : <>
                    {w.merged === true ? <span className="text-emerald-400">merged</span>
                      : w.merged === false ? 'not merged' : 'merge unknown'}
                    {' · '}{w.uncommitted === null ? '—' : w.uncommitted ? <span className="text-amber-400">{w.uncommitted} uncommitted</span> : 'clean'}
                    {' · '}{longAge(w.last_commit_age_s)}
                  </>}
              </span>
            </li>
          ))}
        </ul>
      )}
      <div>
        Remote {row.remote_host ?? '—'} · last fetch {row.fetch_age_s === null ? 'never' : `${longAge(row.fetch_age_s)} ago`}
        {' · '}stash {row.stash ?? '—'} · active by {row.active_by.join(' + ') || '—'}
      </div>
    </div>
  )
}

function Row({ row, open, onToggle }: { row: RepoRow; open: boolean; onToggle: () => void }) {
  const hasProblem = row.problems.length > 0
  const unpushed = row.unpushed_branches?.filter(b => !b.current || row.no_upstream).length
  return (
    <Fragment>
      <tr className={`text-xs ${hasProblem ? '' : 'text-fg-muted'} hover:bg-surface-line/30 cursor-pointer`}
          onClick={onToggle} data-repo-sync-row={row.name} data-repo-sync-problems={row.problems.join(',')}>
        <td className="py-1 pr-2 whitespace-nowrap">
          {open ? <ChevronDown size={12} className="inline -mt-0.5" aria-hidden />
                : <ChevronRight size={12} className="inline -mt-0.5" aria-hidden />}
          <span className={hasProblem ? 'text-fg-loud' : ''}> {row.name}</span>
        </td>
        <td className="py-1 pr-2 truncate max-w-[8rem]" title={row.upstream ?? undefined}>
          {row.branch ?? (row.detached ? 'detached' : '—')}
        </td>
        <td className={`py-1 pr-2 tabular-nums ${row.uncommitted ? 'text-amber-400' : ''}`}>
          {row.uncommitted === null ? '—' : row.uncommitted}
        </td>
        <td className={`py-1 pr-2 tabular-nums whitespace-nowrap ${
          row.diverged ? 'text-red-400' : row.ahead || row.behind || row.no_upstream ? 'text-amber-400' : ''}`}>
          {syncCell(row)}
        </td>
        <td className={`py-1 pr-2 tabular-nums ${unpushed ? 'text-amber-400' : ''}`}>
          {row.unpushed_branches === null ? '—' : unpushed}
        </td>
        <td className="py-1 pr-2 tabular-nums">{row.worktrees === null ? '—' : row.worktrees.length}</td>
        <td className="py-1 pr-2 max-w-[12rem]"><DeployCell row={row} /></td>
        <td className="py-1 tabular-nums whitespace-nowrap">{row.fetch_age_s === null ? 'never' : longAge(row.fetch_age_s)}</td>
      </tr>
      {hasProblem && !open && (
        <tr className="text-xs">
          <td />
          <td colSpan={7} className="pb-1 text-amber-400/90">
            {row.problems.map(problemLabel).join(' · ')}
          </td>
        </tr>
      )}
      {open && (
        <tr><td colSpan={8}><Detail row={row} /></td></tr>
      )}
    </Fragment>
  )
}

export default function FleetRepoSync() {
  const [open, setOpen] = useState(false)
  const [data, setData] = useState<RepoSync | null>(null)
  const [measuredAt, setMeasuredAt] = useState<number | null>(null)
  const [busy, setBusy] = useState<'measure' | 'fetch' | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [fetchNote, setFetchNote] = useState<string | null>(null)
  const [days, setDays] = useState<number | null>(null)
  const [expanded, setExpanded] = useState<Record<string, boolean>>({})
  const [now, setNow] = useState(() => Date.now())
  const rootRef = useRef<HTMLSpanElement>(null)

  const measure = useCallback((d: number | null) => {
    setBusy('measure')
    setError(null)
    fetch(`/api/fleet/repo-sync${d ? `?days=${d}` : ''}`)
      .then(r => (r.ok ? r.json() : Promise.reject(new Error(`HTTP ${r.status}`))))
      .then(j => {
        const parsed = parseRepoSync(j)
        if (!parsed) throw new Error('unexpected answer shape')
        setData(parsed)
        setDays(parsed.days)
        setMeasuredAt(Date.now())
      })
      // A failed measurement keeps the last table and says so; the chip's age keeps growing.
      .catch(e => setError(String(e?.message ?? e)))
      .finally(() => { setBusy(null); setNow(Date.now()) })
  }, [])

  const fetchRemotes = useCallback(() => {
    setBusy('fetch')
    setFetchNote(null)
    fetch('/api/fleet/repo-sync/fetch', {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ days }),
    })
      .then(r => (r.ok ? r.json() : Promise.reject(new Error(`HTTP ${r.status}`))))
      .then(j => {
        const failed = (j.results ?? []).filter((x: any) => x.result !== 'ok')
          .map((x: any) => `${x.name} (${x.result})`)
        setFetchNote(`fetched ${j.ok ?? 0}` + (failed.length ? ` · not fetched: ${failed.join(', ')}` : ''))
        measure(days)
      })
      .catch(e => { setFetchNote(`fetch failed: ${String(e?.message ?? e)}`); setBusy(null) })
  }, [days, measure])

  // Opening measures; nothing else does.
  useEffect(() => { if (open) measure(days) }, [open])  // eslint-disable-line react-hooks/exhaustive-deps

  // The chip's age ticks once a minute while a measurement exists — no request involved.
  useEffect(() => {
    if (measuredAt === null) return
    const t = setInterval(() => setNow(Date.now()), 60_000)
    return () => clearInterval(t)
  }, [measuredAt])

  useEffect(() => {
    if (!open) return
    const onKey = (e: KeyboardEvent) => {
      if (e.key !== 'Escape') return
      e.preventDefault()
      e.stopPropagation()
      setOpen(false)
    }
    const onDown = (e: PointerEvent) => {
      if (rootRef.current && !rootRef.current.contains(e.target as Node)) setOpen(false)
    }
    document.addEventListener('keydown', onKey, true)
    document.addEventListener('pointerdown', onDown)
    return () => {
      document.removeEventListener('keydown', onKey, true)
      document.removeEventListener('pointerdown', onDown)
    }
  }, [open])

  const chip = chipText(data && measuredAt !== null ? { problems: data.problem_count, at: measuredAt } : null, now)
  const ex = data?.excluded

  return (
    <span ref={rootRef} className="inline-flex items-center shrink-0" data-fleet-repo-sync={chip.count ?? 'unmeasured'}>
      <button type="button" onClick={() => setOpen(!open)} aria-expanded={open} title={chip.title}
              aria-label={chip.title}
              className={`inline-flex items-center gap-1 text-xs tabular-nums rounded px-1 border ${
                open ? 'border-sky-400/60 bg-sky-400/10 text-sky-300' : 'border-transparent text-fg-muted hover:text-fg-strong'}`}
              data-fleet-repo-sync-toggle={open ? 'open' : 'closed'}>
        <FolderGit2 size={13} strokeWidth={1.75} aria-hidden />
        {chip.count === null
          ? <span className="text-fg-muted">repos</span>
          : <span className={data && data.problem_count > 0 ? 'text-amber-400' : 'text-emerald-400'}>{chip.count}</span>}
        <span className="hidden lg:inline text-fg-muted">· {chip.age}</span>
      </button>

      {open && (
        <div className="absolute left-2 md:left-6 top-full mt-1 z-30 w-[min(64rem,calc(100vw-1rem))]
                        max-h-[75vh] overflow-y-auto rounded border border-surface-line bg-surface-raised
                        px-3 py-2 shadow-lg"
             role="dialog" aria-label="Repository sync" data-fleet-repo-sync-table={data?.projects.length ?? 0}>
          <div className="flex flex-wrap items-center gap-2 pb-1 border-b border-surface-line">
            <span className="text-xs font-semibold text-fg-loud">Repository sync</span>
            <span className="hidden sm:inline text-xs text-fg-muted">— committed and pushed? measured now, not cached</span>
            <label className="ml-auto text-xs text-fg-muted inline-flex items-center gap-1">
              active in last
              <select className="bg-surface-raised border border-surface-line rounded text-xs px-1"
                      value={days ?? 30} disabled={busy !== null}
                      onChange={e => { const d = Number(e.target.value); setDays(d); measure(d) }}
                      data-repo-sync-days>
                {DAY_CHOICES.map(d => <option key={d} value={d}>{d} days</option>)}
              </select>
            </label>
            <button type="button" onClick={() => measure(days)} disabled={busy !== null}
                    className="text-xs inline-flex items-center gap-1 text-fg-muted hover:text-fg-strong disabled:opacity-50"
                    title="Measure again (local refs only, no network)" data-repo-sync-refresh>
              <RefreshCw size={12} strokeWidth={1.75} className={busy === 'measure' ? 'animate-spin' : ''} aria-hidden />
              refresh
            </button>
            <button type="button" onClick={fetchRemotes} disabled={busy !== null}
                    className="text-xs inline-flex items-center gap-1 text-fg-muted hover:text-fg-strong disabled:opacity-50"
                    title="git fetch every listed project's remotes, then measure — the only network step"
                    data-repo-sync-fetch>
              <CloudDownload size={12} strokeWidth={1.75} className={busy === 'fetch' ? 'animate-pulse' : ''} aria-hidden />
              fetch remotes
            </button>
            <button type="button" onClick={() => setOpen(false)} aria-label="Close repository sync"
                    className="text-fg-muted hover:text-fg-strong" data-repo-sync-close>
              <X size={14} strokeWidth={1.75} aria-hidden />
            </button>
          </div>

          {error && (
            <div className="text-xs text-amber-400 py-1 flex items-center gap-1" data-repo-sync-error>
              <TriangleAlert size={12} aria-hidden /> measurement failed: {error}
              {data ? ' — the table below is the previous measurement' : ''}
            </div>
          )}
          {fetchNote && <div className="text-xs text-fg-muted py-1" data-repo-sync-fetch-note>{fetchNote}</div>}

          {!data && !error && <div className="text-xs text-fg-muted py-2">measuring…</div>}

          {data && (
            <>
              <div className="text-xs text-fg-muted py-1 tabular-nums" data-repo-sync-summary>
                {data.projects.length} project{data.projects.length === 1 ? '' : 's'} active in the last {data.days} days
                {' · '}<span className={data.problem_count ? 'text-amber-400' : 'text-emerald-400'}>
                  {data.problem_count} with something to do</span>
                {' · '}left out: {ex!.archived} archived, {ex!.e2e_run} e2e runs, {ex!.inactive} inactive
                {ex!.missing.length > 0 && <span className="text-amber-400">, {ex!.missing.length} missing ({ex!.missing.join(', ')})</span>}
                {ex!.not_git.length > 0 && <span>, {ex!.not_git.length} not git ({ex!.not_git.join(', ')})</span>}
                {' · '}{data.duration_ms} ms
              </div>
              <table className="w-full table-fixed">
                <colgroup>
                  <col className="w-[22%]" /><col className="w-[11%]" /><col className="w-[7%]" /><col className="w-[10%]" />
                  <col className="w-[8%]" /><col className="w-[6%]" /><col className="w-[28%]" /><col className="w-[8%]" />
                </colgroup>
                <thead>
                  <tr className="text-xs text-fg-muted text-left">
                    <th className="font-normal pb-1">project</th>
                    <th className="font-normal pb-1">branch</th>
                    <th className="font-normal pb-1" title="uncommitted entries, untracked included">dirty</th>
                    <th className="font-normal pb-1" title="↑ commits the remote lacks · ↓ commits this tree lacks">vs remote</th>
                    <th className="font-normal pb-1" title="local branches with commits on no remote">unpushed</th>
                    <th className="font-normal pb-1">wt</th>
                    <th className="font-normal pb-1" title="read from the tree's CI and hosting files">push may deploy</th>
                    <th className="font-normal pb-1" title="age of the last git fetch">fetched</th>
                  </tr>
                </thead>
                <tbody>
                  {data.projects.map(r => (
                    <Row key={r.name} row={r} open={!!expanded[r.name]}
                         onToggle={() => setExpanded(x => ({ ...x, [r.name]: !x[r.name] }))} />
                  ))}
                </tbody>
              </table>
            </>
          )}
        </div>
      )}
    </span>
  )
}
