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
  has_orchestration?: boolean
  last_updated?: string | null
  changes_merged?: number
  changes_total?: number
  total_tokens?: number
  active_seconds?: number
  issues_open?: number
  issues_total?: number
}

export interface ChangeInfo {
  name: string
  status: string
  phase?: number
  depends_on?: string[]
  complexity?: string
  change_type?: string
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
  // Spec coverage gate
  spec_coverage_result?: string
  // Context window metrics (optional — absent on old state files)
  context_tokens_start?: number
  context_tokens_end?: number
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

export interface AuditGap {
  id: string
  description: string
  spec_reference?: string
  severity: 'critical' | 'minor'
  suggested_scope?: string
}

export interface AuditResult {
  cycle: number
  audit_result: 'gaps_found' | 'clean' | 'parse_error'
  model?: string
  mode?: string
  duration_ms?: number
  gaps?: AuditGap[]
  summary?: string
  timestamp?: string
}

export interface PhaseInfo {
  status: string
  completed_at?: string
  tag?: string
  server_port?: number
  server_pid?: number
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
  phase_audit_results?: AuditResult[]
  current_phase?: number
  phases?: Record<string, PhaseInfo>
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
  outcome?: 'active' | 'success' | 'error' | 'unknown'
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

// Process management
export interface ProcessNode {
  pid: number
  command: string
  uptime_seconds: number
  cpu_percent: number
  memory_mb: number
  role?: string
  children: ProcessNode[]
}

export function getProcesses(project: string): Promise<{ processes: ProcessNode[] }> {
  return fetchJSON(`/${project}/processes`)
}

export function stopProcess(project: string, pid: number): Promise<{ ok: boolean }> {
  return fetchJSON(`/${project}/processes/${pid}/stop`, { method: 'POST' })
}

export function stopAllProcesses(project: string): Promise<{ ok: boolean; killed: number[]; total: number }> {
  return fetchJSON(`/${project}/processes/stop-all`, { method: 'POST' })
}

// --- Screenshots ---

export interface ScreenshotFile {
  path: string
  name: string
}

export function getScreenshots(project: string, name: string): Promise<{ smoke: ScreenshotFile[]; e2e: ScreenshotFile[] }> {
  return fetchJSON(`/${project}/changes/${name}/screenshots`)
}

// --- Digest ---

export interface DigestReq {
  id: string
  title: string
  source: string
  source_section?: string
  domain: string
  brief: string
  acceptance_criteria?: string[]
}

export interface DigestData {
  exists: boolean
  index?: {
    spec_base_dir: string
    source_hash: string
    file_count: number
    timestamp: string
    files?: string[]
    execution_hints?: {
      suggested_implementation_order?: string[]
      seed_data_requirements?: string[]
      verification_sections?: string[]
    }
  }
  requirements?: DigestReq[] | [{ requirements: DigestReq[] }]
  coverage?: { coverage?: Record<string, { change: string; status: string }>; uncovered?: string[] }
  coverage_merged?: { coverage?: Record<string, { change: string; status: string }>; uncovered?: string[] }
  dependencies?: { dependencies?: { from: string; to: string; type: string }[] }
  ambiguities?: { id: string; type: string; source?: string; section?: string; description: string; affects_requirements?: string[]; resolution?: string; resolution_note?: string }[]
  domains?: Record<string, string>
  triage?: string
  data_definitions?: string
}

export function getDigest(project: string): Promise<DigestData> {
  return fetchJSON(`/${project}/digest`)
}

// --- Coverage Report ---

export function getCoverageReport(project: string): Promise<{ exists: boolean; content?: string }> {
  return fetchJSON(`/${project}/coverage-report`)
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

// --- Requirements ---

export interface ReqInfo {
  id: string
  change: string
  primary: boolean
  plan_version: string
  status: string
}

export interface ReqGroup {
  group: string
  total: number
  done: number
  in_progress: number
  failed: number
  requirements: ReqInfo[]
}

export interface ReqChangeInfo {
  name: string
  complexity: string
  change_type: string
  depends_on: string[]
  requirements: string[]
  also_affects_reqs: string[]
  scope_summary: string
  plan_version: string
  roadmap_item: string
  status: string
}

export interface RequirementsData {
  requirements: ReqInfo[]
  changes: ReqChangeInfo[]
  groups: ReqGroup[]
  plan_versions: string[]
  total_reqs: number
  done_reqs: number
}

export function getRequirements(project: string): Promise<RequirementsData> {
  return fetchJSON(`/${project}/requirements`)
}

// --- Project Sessions ---

export function getProjectSessions(project: string, change?: string | null): Promise<{ sessions: SessionInfo[] }> {
  if (change) return fetchJSON(`/${project}/changes/${change}/sessions`)
  return fetchJSON(`/${project}/sessions`)
}

export function getProjectSession(project: string, sessionId: string, tail = 200, change?: string | null): Promise<{ lines: string[]; session_id: string }> {
  if (change) return fetchJSON(`/${project}/changes/${change}/session?session_id=${sessionId}&tail=${tail}`)
  return fetchJSON(`/${project}/sessions/${sessionId}?tail=${tail}`)
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

export function shutdownOrchestration(project: string): Promise<{ ok: boolean; message: string }> {
  return fetchJSON(`/${project}/shutdown`, { method: 'POST' })
}

export function startOrchestration(project: string): Promise<{ ok: boolean; pid: number; spec: string }> {
  return fetchJSON(`/${project}/start`, { method: 'POST' })
}

export function stopChange(project: string, name: string): Promise<{ ok: boolean }> {
  return fetchJSON(`/${project}/changes/${name}/stop`, { method: 'POST' })
}

export function skipChange(project: string, name: string): Promise<{ ok: boolean }> {
  return fetchJSON(`/${project}/changes/${name}/skip`, { method: 'POST' })
}

export function pauseChange(project: string, name: string): Promise<{ ok: boolean; message: string }> {
  return fetchJSON(`/${project}/changes/${name}/pause`, { method: 'POST' })
}

export function resumeChange(project: string, name: string): Promise<{ ok: boolean; message: string }> {
  return fetchJSON(`/${project}/changes/${name}/resume`, { method: 'POST' })
}

// --- Sentinel endpoints ---

export interface SentinelEvent {
  ts: string
  epoch: number
  type: string
  [key: string]: unknown
}

export interface SentinelFinding {
  id: string
  severity: string
  change: string
  summary: string
  detail?: string
  discovered_at: string
  status: string
  iteration?: number | null
  commit?: string
}

export interface SentinelAssessment {
  scope: string
  timestamp: string
  summary: string
  recommendation: string
}

export interface SentinelFindingsData {
  findings: SentinelFinding[]
  assessments: SentinelAssessment[]
}

export interface SentinelStatusData {
  active: boolean
  is_active: boolean
  member?: string
  started_at?: string
  last_event_at?: string
  orchestrator_pid?: number | null
  poll_interval_s?: number
}

export function getSentinelEvents(project: string, since?: number): Promise<SentinelEvent[]> {
  const params = since ? `?since=${since}` : ''
  return fetchJSON(`/${project}/sentinel/events${params}`)
}

export function getSentinelFindings(project: string): Promise<SentinelFindingsData> {
  return fetchJSON(`/${project}/sentinel/findings`)
}

export function getSentinelStatus(project: string): Promise<SentinelStatusData> {
  return fetchJSON(`/${project}/sentinel/status`)
}

export function sendSentinelMessage(project: string, message: string): Promise<{ status: string }> {
  return fetchJSON(`/${project}/sentinel/message`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ message }),
  })
}

// --- Battle Scoreboard ---

export interface ScoreboardEntry {
  player: string
  project: string
  score: number
  changes_done: number
  total_changes: number
  total_tokens: number
  achievements: string[]
  timestamp: string
}

// --- Learnings types ---

export interface ReviewFindingIssue {
  severity: string
  summary: string
  file?: string
  line?: string
  fix?: string
}

export interface ReviewFindingEntry {
  change: string
  timestamp: string
  attempt: number
  issue_count: number
  critical_count: number
  high_count: number
  issues: ReviewFindingIssue[]
}

export interface ReviewFindingsData {
  entries: ReviewFindingEntry[]
  summary: string
  recurring_patterns: { pattern: string; count: number }[]
}

export interface GateStatEntry {
  total: number
  pass: number
  fail: number
  skip: number
  pass_rate: number
  avg_ms: number
  total_ms: number
}

export interface GateStatsData {
  per_gate: Record<string, GateStatEntry>
  retry_summary: {
    total_retries: number
    total_gate_ms: number
    retry_pct: number
    most_retried_gate: string
    most_retried_change: string
  }
  per_change_type: Record<string, { avg_gate_ms: number; avg_retries: number; count: number }>
}

export interface ReflectionEntry {
  change: string
  branch: string
  content: string
}

export interface ReflectionsData {
  reflections: ReflectionEntry[]
  total: number
  with_reflection: number
}

export interface TimelineSession {
  n: number
  id?: string
  started: string
  ended: string
  state: string
  gates: Record<string, string>
  gate_ms: Record<string, number>
  merged: boolean
  duration_ms?: number
  model?: string
  label?: string
  input_tokens?: number
  output_tokens?: number
  cache_read_tokens?: number
  cache_create_tokens?: number
}

export interface ChangeTimelineData {
  sessions: TimelineSession[]
  duration_ms: number
  current_gate_results: Record<string, string | number>
}

export interface LearningsData {
  reflections: ReflectionsData
  review_findings: ReviewFindingsData
  gate_stats: GateStatsData
  sentinel_findings: SentinelFindingsData
}

// --- Learnings endpoints ---

export function getLearnings(project: string): Promise<LearningsData> {
  return fetchJSON(`/${project}/learnings`)
}

export function getReviewFindings(project: string): Promise<ReviewFindingsData> {
  return fetchJSON(`/${project}/review-findings`)
}

export function getGateStats(project: string): Promise<GateStatsData> {
  return fetchJSON(`/${project}/gate-stats`)
}

export function getReflections(project: string): Promise<ReflectionsData> {
  return fetchJSON(`/${project}/reflections`)
}

export function getChangeTimeline(project: string, name: string): Promise<ChangeTimelineData> {
  return fetchJSON(`/${project}/changes/${name}/timeline`)
}

// --- Scoreboard ---

export function getScoreboard(limit = 20): Promise<{ entries: ScoreboardEntry[] }> {
  return fetchJSON(`/scoreboard?limit=${limit}`)
}

// =====================================================
// Issue Management Console — Manager API types & functions
// =====================================================

// --- Manager Types ---

export type IssueState =
  | 'new' | 'investigating' | 'diagnosed'
  | 'awaiting_approval' | 'fixing' | 'verifying' | 'deploying'
  | 'resolved' | 'dismissed' | 'muted' | 'failed'
  | 'skipped' | 'cancelled'

export interface IssueDiagnosis {
  root_cause: string
  impact: 'low' | 'medium' | 'high' | 'critical'
  confidence: number
  fix_scope: 'single_file' | 'multi_file' | 'cross_module' | 'unknown'
  suggested_fix: string
  affected_files: string[]
  related_issues: string[]
  suggested_group: string | null
  group_reason: string | null
  tags: string[]
  raw_output: string
}

export interface Issue {
  id: string
  environment: string
  environment_path: string
  source: 'sentinel' | 'gate' | 'watchdog' | 'user'
  state: IssueState
  severity: 'unknown' | 'low' | 'medium' | 'high' | 'critical'
  group_id: string | null
  error_summary: string
  error_detail: string
  fingerprint: string
  affected_files: string[]
  affected_change: string | null
  detected_at: string
  source_finding_id: string | null
  occurrence_count: number
  diagnosis: IssueDiagnosis | null
  investigation_session: string | null
  change_name: string | null
  fix_agent_pid: number | null
  timeout_deadline: string | null
  timeout_started_at: string | null
  policy_matched: string | null
  auto_fix: boolean
  mute_pattern: string | null
  retry_count: number
  max_retries: number
  updated_at: string
  resolved_at: string | null
}

export interface IssueGroup {
  id: string
  name: string
  issue_ids: string[]
  primary_issue: string
  state: IssueState
  change_name: string | null
  created_at: string
  reason: string
  created_by: 'user' | 'agent'
}

export interface MutePattern {
  id: string
  pattern: string
  reason: string
  created_by: string
  created_at: string
  expires_at: string | null
  match_count: number
  last_matched_at: string | null
  source_issue_id: string | null
}

export interface IssueAuditEntry {
  ts: string
  issue_id?: string
  group_id?: string
  action: string
  [key: string]: unknown
}

export interface IssueStats {
  by_state: Partial<Record<IssueState, number>>
  by_severity: Record<string, number>
  total_open: number
  total_resolved: number
  nearest_timeout: string | null
}

export interface ManagerProjectStatus {
  name: string
  mode: string
  path: string
  sentinel: { pid: number | null; alive: boolean; started_at: string | null; spec: string | null; crash_count: number }
  orchestrator: { pid: number | null; alive: boolean; started_at: string | null }
  issue_stats?: IssueStats
}

export interface ManagerStatus {
  pid: number
  running: boolean
  tick_interval: number
  port: number
  projects: Record<string, ManagerProjectStatus>
  issues: Record<string, IssueStats>
}

export interface TimelineEntry {
  id: string
  timestamp: string
  type: 'system' | 'user' | 'agent'
  content: string
  action?: string
  icon?: string
  author?: string
}

// --- Manager API Functions ---

// Manager API functions — unified server, no proxy prefix

// Projects & processes
export function getManagerProjects(): Promise<ManagerProjectStatus[]> {
  return fetchJSON(`/projects`)
}
export function getManagerProjectStatus(name: string): Promise<ManagerProjectStatus> {
  return fetchJSON(`/projects/${name}/status`)
}
export function startSentinel(project: string, spec?: string): Promise<{ status: string; pid: number }> {
  const body = spec ? JSON.stringify({ spec }) : undefined
  const headers = spec ? { 'Content-Type': 'application/json' } : undefined
  return fetchJSON(`/${project}/sentinel/start`, { method: 'POST', body, headers })
}
export function stopSentinel(project: string): Promise<{ status: string }> {
  return fetchJSON(`/${project}/sentinel/stop`, { method: 'POST' })
}
export function restartSentinel(project: string, spec?: string): Promise<{ status: string; pid: number }> {
  const body = spec ? JSON.stringify({ spec }) : undefined
  const headers = spec ? { 'Content-Type': 'application/json' } : undefined
  return fetchJSON(`/${project}/sentinel/restart`, { method: 'POST', body, headers })
}

// Docs listing
export interface DocsEntry {
  path: string
  type: 'file' | 'dir'
}

export function getProjectDocs(project: string): Promise<{ docs: DocsEntry[] }> {
  return fetchJSON(`/${project}/docs`)
}

// Issues
export function getIssues(project: string, filters?: { state?: string; severity?: string }): Promise<Issue[]> {
  const params = new URLSearchParams()
  if (filters?.state) params.set('state', filters.state)
  if (filters?.severity) params.set('severity', filters.severity)
  const qs = params.toString()
  return fetchJSON(`/${project}/issues${qs ? '?' + qs : ''}`)
}
export function getIssue(project: string, id: string): Promise<Issue> {
  return fetchJSON(`/${project}/issues/${id}`)
}
export function createIssue(project: string, data: { error_summary: string; error_detail?: string }): Promise<Issue> {
  return fetchJSON(`/${project}/issues`, {
    method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(data),
  })
}
export function getAllIssues(): Promise<Issue[]> {
  return fetchJSON(`/issues`)
}
export function getIssueStats(project: string): Promise<IssueStats> {
  return fetchJSON(`/${project}/issues/stats`)
}
export function getAllIssueStats(): Promise<Record<string, IssueStats>> {
  return fetchJSON(`/issues/stats`)
}

// Issue actions
export function investigateIssue(project: string, id: string): Promise<{ status: string }> {
  return fetchJSON(`/${project}/issues/${id}/investigate`, { method: 'POST' })
}
export function fixIssue(project: string, id: string): Promise<{ status: string }> {
  return fetchJSON(`/${project}/issues/${id}/fix`, { method: 'POST' })
}
export function dismissIssue(project: string, id: string): Promise<{ status: string }> {
  return fetchJSON(`/${project}/issues/${id}/dismiss`, { method: 'POST' })
}
export function cancelIssue(project: string, id: string): Promise<{ status: string }> {
  return fetchJSON(`/${project}/issues/${id}/cancel`, { method: 'POST' })
}
export function skipIssue(project: string, id: string, reason?: string): Promise<{ status: string }> {
  return fetchJSON(`/${project}/issues/${id}/skip`, {
    method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ reason: reason || '' }),
  })
}
export function muteIssue(project: string, id: string, pattern?: string): Promise<{ status: string }> {
  return fetchJSON(`/${project}/issues/${id}/mute`, {
    method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ pattern }),
  })
}
export function extendIssueTimeout(project: string, id: string, seconds: number): Promise<{ status: string }> {
  return fetchJSON(`/${project}/issues/${id}/extend-timeout`, {
    method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ seconds }),
  })
}
export function sendIssueMessage(project: string, id: string, message: string): Promise<{ status: string }> {
  return fetchJSON(`/${project}/issues/${id}/message`, {
    method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ message }),
  })
}

// Groups
export function getIssueGroups(project: string): Promise<IssueGroup[]> {
  return fetchJSON(`/${project}/issues/groups`)
}
export function createIssueGroup(project: string, ids: string[], name: string, reason: string): Promise<IssueGroup> {
  return fetchJSON(`/${project}/issues/groups`, {
    method: 'POST', headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ issue_ids: ids, name, reason }),
  })
}
export function fixGroup(project: string, groupId: string): Promise<{ status: string }> {
  return fetchJSON(`/${project}/issues/groups/${groupId}/fix`, { method: 'POST' })
}

// Mutes
export function getMutePatterns(project: string): Promise<MutePattern[]> {
  return fetchJSON(`/${project}/issues/mutes`)
}
export function addMutePattern(project: string, pattern: string, reason: string, expires_at?: string): Promise<MutePattern> {
  return fetchJSON(`/${project}/issues/mutes`, {
    method: 'POST', headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ pattern, reason, expires_at }),
  })
}
export function deleteMutePattern(project: string, id: string): Promise<{ status: string }> {
  return fetchJSON(`/${project}/issues/mutes/${id}`, { method: 'DELETE' })
}

// Audit
export function getIssueAudit(project: string, opts?: { since?: number; limit?: number; issue_id?: string }): Promise<IssueAuditEntry[]> {
  const params = new URLSearchParams()
  if (opts?.since) params.set('since', String(opts.since))
  if (opts?.limit) params.set('limit', String(opts.limit))
  if (opts?.issue_id) params.set('issue_id', opts.issue_id)
  const qs = params.toString()
  return fetchJSON(`/${project}/issues/audit${qs ? '?' + qs : ''}`)
}

// Manager service
export function getManagerStatus(): Promise<ManagerStatus> {
  return fetchJSON('/service/status')
}

export function restartManager(): Promise<{ status: string }> {
  // Use set-orch-core endpoint (always works, doesn't depend on manager code version)
  return fetchJSON('/api/manager-restart', { method: 'POST' })
}

export function startManager(): Promise<{ status: string; pid?: number }> {
  return fetchJSON('/api/manager-start', { method: 'POST' })
}

export function getSentinelLog(project: string, tail = 200): Promise<{ lines: string[] }> {
  return fetchJSON(`/${project}/sentinel/log?tail=${tail}`)
}

// =====================================================

export async function signScore(project: string, score: number, changesDone: number, totalTokens: number): Promise<string> {
  const data = await fetchJSON<{ signature: string }>(
    `/scoreboard/sign?project=${encodeURIComponent(project)}&score=${score}&changes_done=${changesDone}&total_tokens=${totalTokens}`
  )
  return data.signature
}

export function submitScore(entry: {
  player: string
  project: string
  score: number
  changes_done: number
  total_changes: number
  total_tokens: number
  achievements: string[]
  signature: string
}): Promise<{ status: string; rank?: number }> {
  return fetchJSON('/scoreboard/submit', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(entry),
  })
}
