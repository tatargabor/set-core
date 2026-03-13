/** Typed fetch wrappers for all REST endpoints. */

const BASE = '/api'

async function fetchJSON<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${BASE}${path}`, init)
  if (!res.ok) {
    const text = await res.text()
    throw new Error(`${res.status}: ${text}`)
  }
  return res.json()
}

// --- Types ---

export interface ProjectInfo {
  name: string
  path: string
  status?: string
  last_updated?: string | null
}

export interface ChangeInfo {
  name: string
  status: string
  iteration?: number
  ralph_pid?: number
  worktree_path?: string
  branch?: string
  // Token fields — match state.py field names
  input_tokens?: number
  output_tokens?: number
  cache_read_tokens?: number
  cache_create_tokens?: number
  tokens_used?: number
  started_at?: string
  completed_at?: string
  // Gate results
  test_result?: string
  smoke_result?: string
  review_result?: string
  build_result?: string
  // Gate outputs (full text)
  build_output?: string
  test_output?: string
  smoke_output?: string
  review_output?: string
  // Gate timing
  gate_build_ms?: number
  gate_test_ms?: number
  gate_review_ms?: number
  gate_verify_ms?: number
  gate_total_ms?: number
  // Screenshot info
  smoke_screenshot_count?: number
  smoke_screenshot_dir?: string
  e2e_screenshot_count?: number
  e2e_screenshot_dir?: string
  // Misc
  model?: string
  session_count?: number
  logs?: string[]
  extras?: Record<string, unknown>
}

export interface GateResult {
  status: 'pass' | 'fail' | 'skip' | 'pending'
  duration_s?: number
  output?: string
}

export interface StateData {
  plan_version?: string | number
  status?: string
  orchestrator_pid?: number
  changes: ChangeInfo[]
  started_at?: string
  created_at?: string
  active_seconds?: number
  directives?: Record<string, unknown>
}

export interface WorktreeInfo {
  path: string
  branch: string
  head: string
  bare?: boolean
  iteration?: number
  max_iterations?: number
  logs?: string[]
  has_reflection?: boolean
  activity?: {
    skill?: string
    skill_args?: string
    broadcast?: string
    updated_at?: string
  }
}

export interface ActivityInfo {
  worktree: string
  skill?: string
  skill_args?: string
  broadcast?: string
  updated_at?: string
}

// --- Read endpoints ---

export function getProjects(): Promise<ProjectInfo[]> {
  return fetchJSON('/projects')
}

export function getState(project: string): Promise<StateData> {
  return fetchJSON(`/${project}/state`)
}

export function getChanges(project: string): Promise<ChangeInfo[]> {
  return fetchJSON(`/${project}/changes`)
}

export function getChange(project: string, name: string): Promise<ChangeInfo> {
  return fetchJSON(`/${project}/changes/${name}`)
}

export function getWorktrees(project: string): Promise<WorktreeInfo[]> {
  return fetchJSON(`/${project}/worktrees`)
}

export function getWorktreeLog(project: string, branch: string, filename: string): Promise<{ filename: string; lines: string[] }> {
  return fetchJSON(`/${project}/worktrees/${branch}/log/${filename}`)
}

export function getWorktreeReflection(project: string, branch: string): Promise<{ content: string }> {
  return fetchJSON(`/${project}/worktrees/${branch}/reflection`)
}

export function getChangeLogs(project: string, name: string): Promise<{ logs: string[]; iteration?: number; max_iterations?: number }> {
  return fetchJSON(`/${project}/changes/${name}/logs`)
}

export function getChangeLog(project: string, name: string, filename: string): Promise<{ filename: string; lines: string[] }> {
  return fetchJSON(`/${project}/changes/${name}/log/${filename}`)
}

export interface SessionInfo {
  id: string
  size: number
  mtime: string
  label?: string
  full_label?: string
}

export function getChangeSession(
  project: string, name: string, tail = 200, sessionId?: string
): Promise<{ lines: string[]; session_id: string | null; sessions: SessionInfo[] }> {
  const params = new URLSearchParams({ tail: String(tail) })
  if (sessionId) params.set('session_id', sessionId)
  return fetchJSON(`/${project}/changes/${name}/session?${params}`)
}

export function getActivity(project: string): Promise<ActivityInfo[]> {
  return fetchJSON(`/${project}/activity`)
}

export function getLog(project: string): Promise<{ lines: string[] }> {
  return fetchJSON(`/${project}/log`)
}

// --- Screenshots ---

export interface ScreenshotFile {
  path: string
  name: string
}

export function getScreenshots(project: string, name: string): Promise<{ smoke: ScreenshotFile[]; e2e: ScreenshotFile[] }> {
  return fetchJSON(`/${project}/changes/${name}/screenshots`)
}

// --- Plans ---

export interface PlanFile {
  filename: string
  size: number
  mtime: string
}

export function getPlans(project: string): Promise<{ plans: PlanFile[] }> {
  return fetchJSON(`/${project}/plans`)
}

export function getPlan(project: string, filename: string): Promise<unknown> {
  return fetchJSON(`/${project}/plans/${filename}`)
}

// --- Events ---

export function getEvents(project: string, type?: string, limit = 500): Promise<{ events: Record<string, unknown>[] }> {
  const params = new URLSearchParams({ limit: String(limit) })
  if (type) params.set('type', type)
  return fetchJSON(`/${project}/events?${params}`)
}

// --- Write endpoints ---

export function approve(project: string): Promise<{ ok: boolean }> {
  return fetchJSON(`/${project}/approve`, { method: 'POST' })
}

export function stopOrchestrator(project: string): Promise<{ ok: boolean }> {
  return fetchJSON(`/${project}/stop`, { method: 'POST' })
}

export function stopChange(project: string, name: string): Promise<{ ok: boolean }> {
  return fetchJSON(`/${project}/changes/${name}/stop`, { method: 'POST' })
}

export function skipChange(project: string, name: string): Promise<{ ok: boolean }> {
  return fetchJSON(`/${project}/changes/${name}/skip`, { method: 'POST' })
}
