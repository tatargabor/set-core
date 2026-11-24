/**
 * The repository-sync view's data (openspec change fleet-repo-sync).
 *
 * The answer of `GET /api/fleet/repo-sync`, parsed defensively: a field the server could not
 * read arrives as `null`, and it stays `null` here — rendered as a gap, never as a zero.
 */

export type DeployValue = 'yes' | 'no' | 'unknown'

export interface DeployHint {
  value: DeployValue
  source: string | null
  reason: string
  job?: string | null
  environment?: string | null
}

export interface UnpushedBranch {
  branch: string
  commits: number
  last_commit_age_s: number | null
  current: boolean
}

export interface Worktree {
  path: string
  branch: string | null
  detached: boolean
  missing: boolean
  uncommitted: number | null
  last_commit_age_s: number | null
  merged: boolean | null
}

export interface RepoRow {
  name: string
  path: string
  active_by: string[]
  branch: string | null
  detached: boolean
  uncommitted: number | null
  untracked: number | null
  upstream: string | null
  no_upstream: boolean
  ahead: number | null
  behind: number | null
  diverged: boolean
  unpushed_branches: UnpushedBranch[] | null
  stash: number | null
  remote_host: string | null
  fetch_age_s: number | null
  worktrees: Worktree[] | null
  push_may_deploy: DeployHint
  errors: Record<string, string>
  problems: string[]
  last_commit_age_s: number | null
  last_session_age_s: number | null
}

export interface Excluded {
  archived: number
  hidden: number
  e2e_run: number
  inactive: number
  missing: string[]
  not_git: string[]
}

export interface RepoSync {
  generated_at: number
  days: number
  duration_ms: number
  projects: RepoRow[]
  problem_count: number
  excluded: Excluded
  /** Registered projects the owner hid from this table; the hidden view lists them. */
  hidden: string[]
}

const num = (v: unknown): number | null => (typeof v === 'number' && Number.isFinite(v) ? v : null)
const str = (v: unknown): string | null => (typeof v === 'string' ? v : null)
const arr = <T>(v: unknown, f: (x: any) => T | null): T[] | null =>
  Array.isArray(v) ? v.map(f).filter((x): x is T => x !== null) : null

function parseHint(v: any): DeployHint {
  const value: DeployValue = v?.value === 'yes' || v?.value === 'no' ? v.value : 'unknown'
  return { value, source: str(v?.source), reason: str(v?.reason) ?? 'not read',
           job: str(v?.job), environment: str(v?.environment) }
}

function parseRow(v: any): RepoRow | null {
  if (!v || typeof v.name !== 'string') return null
  return {
    name: v.name,
    path: str(v.path) ?? '',
    active_by: Array.isArray(v.active_by) ? v.active_by.filter((x: unknown) => typeof x === 'string') : [],
    branch: str(v.branch),
    detached: v.detached === true,
    uncommitted: num(v.uncommitted),
    untracked: num(v.untracked),
    upstream: str(v.upstream),
    no_upstream: v.no_upstream === true,
    ahead: num(v.ahead),
    behind: num(v.behind),
    diverged: v.diverged === true,
    unpushed_branches: arr(v.unpushed_branches, b => (b && typeof b.branch === 'string'
      ? { branch: b.branch, commits: num(b.commits) ?? 0, last_commit_age_s: num(b.last_commit_age_s),
          current: b.current === true }
      : null)),
    stash: num(v.stash),
    remote_host: str(v.remote_host),
    fetch_age_s: num(v.fetch_age_s),
    worktrees: arr(v.worktrees, w => (w && typeof w.path === 'string'
      ? { path: w.path, branch: str(w.branch), detached: w.detached === true, missing: w.missing === true,
          uncommitted: num(w.uncommitted), last_commit_age_s: num(w.last_commit_age_s),
          merged: typeof w.merged === 'boolean' ? w.merged : null }
      : null)),
    push_may_deploy: parseHint(v.push_may_deploy),
    errors: v.errors && typeof v.errors === 'object' ? v.errors : {},
    problems: Array.isArray(v.problems) ? v.problems.filter((x: unknown) => typeof x === 'string') : [],
    last_commit_age_s: num(v.last_commit_age_s),
    last_session_age_s: num(v.last_session_age_s),
  }
}

/** `null` when the answer is not the expected shape — the caller says so instead of rendering. */
export function parseRepoSync(d: any): RepoSync | null {
  if (!d || !Array.isArray(d.projects) || typeof d.days !== 'number') return null
  const ex = d.excluded ?? {}
  return {
    generated_at: num(d.generated_at) ?? 0,
    days: d.days,
    duration_ms: num(d.duration_ms) ?? 0,
    projects: d.projects.map(parseRow).filter((r: RepoRow | null): r is RepoRow => r !== null),
    problem_count: num(d.problem_count) ?? 0,
    excluded: {
      archived: num(ex.archived) ?? 0, hidden: num(ex.hidden) ?? 0, e2e_run: num(ex.e2e_run) ?? 0, inactive: num(ex.inactive) ?? 0,
      missing: Array.isArray(ex.missing) ? ex.missing : [], not_git: Array.isArray(ex.not_git) ? ex.not_git : [],
    },
    hidden: Array.isArray(d.hidden) ? d.hidden.filter((x: unknown) => typeof x === 'string') : [],
  }
}

/** A duration in the shortest honest form, with days — commit ages run to weeks. */
export function longAge(seconds: number | null | undefined): string {
  if (seconds === null || seconds === undefined) return '—'
  if (seconds < 90) return `${Math.round(seconds)}s`
  if (seconds < 5400) return `${Math.round(seconds / 60)}m`
  if (seconds < 172800) return `${Math.round(seconds / 3600)}h`
  return `${Math.round(seconds / 86400)}d`
}

export const PROBLEM_LABEL: Record<string, string> = {
  unreadable: 'unreadable',
  uncommitted: 'uncommitted',
  diverged: 'diverged',
  ahead: 'not pushed',
  behind: 'behind remote',
  'no-upstream': 'no upstream',
  'unpushed-branch': 'unpushed branch',
  'push-may-deploy': 'push may deploy',
}

export function problemLabel(p: string): string {
  return PROBLEM_LABEL[p] ?? p
}

/**
 * The chip's text. Before the first measurement it makes no claim at all; after one, the
 * count and how old that count is — a calm that is an hour old must read as an hour old.
 */
export function chipText(measured: { problems: number; at: number } | null, now: number): {
  count: string | null; age: string; title: string
} {
  if (!measured) {
    return { count: null, age: 'not measured',
             title: 'Repository sync — not measured yet. Open to measure every recently active project.' }
  }
  const a = longAge(Math.max(0, (now - measured.at) / 1000))
  return {
    count: String(measured.problems),
    age: `${a} ago`,
    title: `${measured.problems} project${measured.problems === 1 ? '' : 's'} with something not committed, `
      + `not pushed or not readable — measured ${a} ago. Open to measure again.`,
  }
}

/** What the "ahead / behind" cell says; `null` fields stay a gap. */
export function syncCell(r: RepoRow): string {
  if (r.no_upstream) return 'no upstream'
  if (r.ahead === null || r.behind === null) return r.branch ? '—' : 'detached'
  if (!r.ahead && !r.behind) return 'in sync'
  return [r.ahead ? `↑${r.ahead}` : '', r.behind ? `↓${r.behind}` : ''].filter(Boolean).join(' ')
}
