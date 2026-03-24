# Issue Management Console

## Problem

The set-manager service (see change: `issue-management-engine`) provides a backend for process supervision, issue detection, investigation, and fixing. But without a visual interface, operators must use CLI or raw API calls to:

- See which projects are running, start/stop sentinels and orchestrations
- Monitor issues across environments
- Read investigation diagnoses and raw error output
- Approve, dismiss, cancel, or skip fixes
- Chat with investigation agents about specific bugs
- Watch auto-fix countdowns and intervene if needed
- Manage mute patterns

This is impractical beyond development use. The system needs a management console integrated into set-web.

## Solution

Build a **Management Console** at `/manager` in set-web. The console provides:

1. **Projects Overview** — all environments with process status, start/stop controls
2. **Issue Management** — per-project and cross-project issue lists with full lifecycle controls
3. **Per-issue Console** — unified timeline (system events + chat) per bug
4. **Quick Actions** — context-aware buttons per issue state
5. **Groups & Mutes** — create groups, manage mute patterns

## Scope

### In scope

1. **Projects Overview page** (`/manager`) — cards per project with sentinel/orchestrator status and start/stop buttons
2. **Issues page** (`/manager/:project/issues`) — filterable issue list with urgency sections
3. **Issue Detail panel** — diagnosis, raw error, unified timeline console, state-aware action buttons
4. **Cross-project Issues** (`/manager/issues`) — all issues across all projects
5. **Group management** — multi-select → group, group detail view
6. **Mute pattern management** — CRUD for mute patterns
7. **Timeout countdown** — real-time countdown display for AWAITING_APPROVAL issues
8. **API client extensions** — TypeScript types and functions for all manager endpoints
9. **Real-time polling** — hooks for live updates (2s interval)

### Out of scope

- Backend service (separate change: `issue-management-engine`)
- Mobile layout (desktop-first)

### Depends on

- `issue-management-engine` — all API endpoints and data models

## Design

### Routing

```
/manager                              Projects overview (landing)
/manager/issues                       Cross-project issues
/manager/:project                     Project detail (redirects to issues)
/manager/:project/issues              Per-project issue list
/manager/:project/issues/:id          Issue detail
/manager/:project/mutes               Mute patterns
```

### Page 1: Projects Overview (`/manager`)

```
┌─────────────────────────────────────────────────────────────────┐
│  MANAGEMENT CONSOLE                                              │
│                                                                  │
│  ┌─────────────────────────────┐ ┌─────────────────────────────┐│
│  │ craftbrew-run12       [E2E] │ │ minishop-prod        [PROD] ││
│  │                             │ │                             ││
│  │ Orchestrator 🟢 2h34m       │ │ Orchestrator 🟢 14d         ││
│  │              [Stop][Restart]│ │              [Stop][Restart]││
│  │ Sentinel     🟢 3s ago      │ │ Sentinel     🟢 5s ago      ││
│  │              [Stop][Restart]│ │              [Stop][Restart]││
│  │                             │ │                             ││
│  │ Changes   4/12 merged       │ │ Issues   ⚠ 1 awaiting      ││
│  │ Issues    ⚠ 3 open         │ │            (2:31)           ││
│  │           1 fixing          │ │                             ││
│  │           2 new             │ │                             ││
│  │                             │ │                             ││
│  │ [View Issues]               │ │ [View Issues]               ││
│  └─────────────────────────────┘ └─────────────────────────────┘│
│                                                                  │
│  ┌─────────────────────────────┐                                │
│  │ acme-staging          [DEV] │                                │
│  │                             │                                │
│  │ Orchestrator ⚫ stopped      │                                │
│  │              [Start]        │                                │
│  │ Sentinel     ⚫ stopped      │                                │
│  │              [Start]        │                                │
│  └─────────────────────────────┘                                │
│                                                                  │
│  Manager service: 🟢 running │ uptime 3d │ tick: 5s             │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

**Data:** `GET /api/projects` + `GET /api/projects/{name}/status` + `GET /api/projects/{name}/issues/stats`

**Components:**
- `ProjectCard` — per-project card with process controls
- `ProcessControl` — green/red indicator + start/stop/restart buttons
- `ModeBadge` — E2E (blue), PROD (red), DEV (gray)
- `IssueCountBadge` — issue summary with nearest timeout

### Page 2: Issues List (`/manager/:project/issues` or `/manager/issues`)

```
┌─────────────────────────────────────────────────────────────────┐
│  ← Manager    ISSUES — craftbrew-run12       [Filter ▾] [Group] │
│                                                                  │
│  Filter: [All States ▾] [All Severity ▾] [All Sources ▾]       │
│                                                                  │
│  ┌─ NEEDS ATTENTION ────────────────────────────────────────┐   │
│  │                                                           │   │
│  │  ☐ ISS-003  unknown  AWAITING  Prisma client missing     │   │
│  │     gate │ ⏱ 2:31 remaining │ GRP-002                    │   │
│  │                                                           │   │
│  │  ☐ ISS-007  unknown  NEW      Route collision /api/users │   │
│  │     sentinel │ 2m ago                                     │   │
│  │                                                           │   │
│  └───────────────────────────────────────────────────────────┘   │
│                                                                  │
│  ┌─ IN PROGRESS ────────────────────────────────────────────┐   │
│  │                                                           │   │
│  │  ☐ ISS-001  high  FIXING     Auth token crash            │   │
│  │     sentinel │ fix-iss-001-auth-token                     │   │
│  │                                                           │   │
│  └───────────────────────────────────────────────────────────┘   │
│                                                                  │
│  ┌─ DONE (collapsed by default) ────────────────────── [▶] ┐   │
│  │  ISS-004  low  RESOLVED │ ISS-005  low  DISMISSED        │   │
│  └───────────────────────────────────────────────────────────┘   │
│                                                                  │
│  Selected: 0 │ [Group Selected] [Dismiss Selected]              │
│                                                                  │
│  GROUPS                                                          │
│  ┌───────────────────────────────────────────────────────────┐   │
│  │ GRP-002  AWAITING  "db-setup-sequence"  3 issues          │   │
│  └───────────────────────────────────────────────────────────┘   │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

Cross-project variant: same layout + environment column + environment filter.

**Components:**
- `IssueList` — sections by urgency (needs attention, in progress, done)
- `IssueRow` — state badge, severity, timer, source, group indicator
- `IssueFilter` — dropdowns for state, severity, source
- `GroupList` / `GroupRow`
- `BulkActions` — multi-select action bar
- `TimeoutCountdown` — live countdown component

### Page 3: Issue Detail (slide-out panel)

Opens as a slide-out from the right (50-60% width), keeping the issue list visible behind.

**State-aware action buttons:**

```
State              Buttons
─────────────────  ──────────────────────────────────────────────
NEW                [Investigate] [Dismiss] [Mute] [Skip]
INVESTIGATING      [Cancel] [Dismiss]
DIAGNOSED          [Fix Now] [Investigate More] [Dismiss] [Mute] [Skip]
AWAITING_APPROVAL  [Fix Now] [Extend Timeout] [Cancel] [Dismiss]
FIXING             [Cancel]
VERIFYING          [Cancel]
DEPLOYING          (no actions — in progress)
RESOLVED           (view only)
DISMISSED          [Reopen]
MUTED              [Unmute]
FAILED             [Retry] [Investigate More] [Dismiss]
SKIPPED            [Reopen]
CANCELLED          [Reopen] [Dismiss]
```

```
┌─────────────────────────────────────────────────────────────────┐
│  ← Issues    ISS-003 │ unknown │ AWAITING_APPROVAL              │
│  "Prisma client not generated before migration"                  │
│  craftbrew-run12 │ gate │ GRP-002 │ seen 3 times                 │
│                                                                  │
│  ┌─ ACTIONS ─────────────────────────────────────────────────┐  │
│  │                                                            │  │
│  │  [▶ Fix Now]  [⏰ Extend]  [✕ Cancel]  [✕ Dismiss]       │  │
│  │                                                            │  │
│  │  ⏱ Auto-fix in 2:31  ████████░░░░░░  62%                 │  │
│  │                                                            │  │
│  └────────────────────────────────────────────────────────────┘  │
│                                                                  │
│  ┌─ TABS ─────────────────────────────────────────────────────┐ │
│  │  [Timeline]  [Diagnosis]  [Error]  [Related]               │ │
│  └─────────────────────────────────────────────────────────────┘ │
│                                                                  │
│  ═══ TIMELINE TAB (default) ═══                                  │
│  Unified timeline: system events + user chat + agent responses.  │
│  No separate tabs for "action log" and "console" — it's all     │
│  one chronological stream.                                       │
│                                                                  │
│  ┌────────────────────────────────────────────────────────────┐  │
│  │                                                            │  │
│  │      ── 14:01 · registered · gate build failed ──         │  │
│  │                                                            │  │
│  │      ── 14:01 · investigating · agent spawned ──          │  │
│  │                                                            │  │
│  │  🤖 Agent                                     14:03       │  │
│  │  ┌──────────────────────────────────────┐                  │  │
│  │  │ Investigation complete.              │                  │  │
│  │  │ Root cause: Prisma generate runs     │                  │  │
│  │  │ after migration instead of before.   │                  │  │
│  │  │ Confidence: 0.88                     │                  │  │
│  │  └──────────────────────────────────────┘                  │  │
│  │                                                            │  │
│  │      ── 14:03 · diagnosed · auto-fix in 5:00 ──          │  │
│  │                                                            │  │
│  │                                You  14:05                  │  │
│  │          ┌──────────────────────────────────────┐          │  │
│  │          │ Nézted a teszt coverage-et is?       │          │  │
│  │          └──────────────────────────────────────┘          │  │
│  │                                                            │  │
│  │  🤖 Agent                                     14:05       │  │
│  │  ┌──────────────────────────────────────┐                  │  │
│  │  │ Van 3 unit teszt de burst scenario-t │                  │  │
│  │  │ nem fedik. Érdemes a fix mellé.      │                  │  │
│  │  └──────────────────────────────────────┘                  │  │
│  │                                                            │  │
│  │      ── 14:06 · ⏱ auto-fix in 2:31 ──                    │  │
│  │                                                            │  │
│  │  > [________________________________________] [Send]       │  │
│  │                                                            │  │
│  └────────────────────────────────────────────────────────────┘  │
│                                                                  │
│  ═══ DIAGNOSIS TAB ═══                                           │
│  ┌────────────────────────────────────────────────────────────┐  │
│  │ Root Cause                                                 │  │
│  │ Prisma client generation runs after migration instead of   │  │
│  │ before. setup-db.sh calls `prisma migrate` before          │  │
│  │ `prisma generate`.                                         │  │
│  │                                                            │  │
│  │ Impact: medium │ Confidence: 0.88 │ Scope: single_file    │  │
│  │                                                            │  │
│  │ Suggested Fix                                              │  │
│  │ Swap order in setup-db.sh: generate first, then migrate.   │  │
│  │                                                            │  │
│  │ Affected Files                                             │  │
│  │ • scripts/setup-db.sh:12                                   │  │
│  │ • .github/workflows/ci.yml:45                              │  │
│  │                                                            │  │
│  │ Tags: prisma, build-order, ci                              │  │
│  └────────────────────────────────────────────────────────────┘  │
│                                                                  │
│  ═══ ERROR TAB ═══                                               │
│  ┌────────────────────────────────────────────────────────────┐  │
│  │ Raw error output:                                          │  │
│  │                                                            │  │
│  │ $ pnpm build                                               │  │
│  │ > prisma generate                                          │  │
│  │ Error: Cannot find module '@prisma/client'                 │  │
│  │   at Object.<anonymous> (src/db/client.ts:1:1)            │  │
│  │   at Module._compile (internal/modules/cjs/loader:1241)   │  │
│  │ ...                                                        │  │
│  │                                                            │  │
│  │ Occurrences: 3 │ First: 14:01 │ Last: 14:23               │  │
│  └────────────────────────────────────────────────────────────┘  │
│                                                                  │
│  ═══ RELATED TAB ═══                                             │
│  ┌────────────────────────────────────────────────────────────┐  │
│  │ Group: GRP-002 "db-setup-sequence"                        │  │
│  │                                                            │  │
│  │ ISS-003  AWAITING  Prisma client not generated  ← this   │  │
│  │ ISS-007  NEW       DB schema out of sync                  │  │
│  │ ISS-011  NEW       Migration checksum mismatch            │  │
│  │                                                            │  │
│  │ [Fix Group Together]  [Remove from Group]                 │  │
│  └────────────────────────────────────────────────────────────┘  │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

### Page 4: Mute Patterns (`/manager/:project/mutes`)

```
┌─────────────────────────────────────────────────────────────────┐
│  MUTE PATTERNS — craftbrew-run12                  [+ Add Mute]  │
│                                                                  │
│  MUTE-001  prisma.*P2002.*unique constraint                     │
│  Known issue, handled by retry logic                             │
│  Suppressed: 12x │ Last: 2h ago │ Expires: 30 days              │
│  Source: ISS-004                              [Edit] [Delete]    │
│                                                                  │
│  MUTE-002  ECONNREFUSED.*localhost:5432                          │
│  DB cold start race condition                                    │
│  Suppressed: 3x │ Last: 1d ago │ No expiry                      │
│  Source: manual                               [Edit] [Delete]    │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

## Technical Design

### TypeScript types

```typescript
interface Issue {
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

  diagnosis: Diagnosis | null
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

type IssueState =
  | 'new' | 'investigating' | 'diagnosed'
  | 'awaiting_approval' | 'fixing' | 'verifying' | 'deploying'
  | 'resolved' | 'dismissed' | 'muted' | 'failed'
  | 'skipped' | 'cancelled'

interface Diagnosis {
  root_cause: string
  impact: 'low' | 'medium' | 'high' | 'critical'
  confidence: number
  fix_scope: 'single_file' | 'multi_file' | 'cross_module'
  suggested_fix: string
  affected_files: string[]
  related_issues: string[]
  suggested_group: string | null
  group_reason: string | null
  tags: string[]
  raw_output: string
}

interface IssueGroup {
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

interface MutePattern {
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

interface AuditEntry {
  ts: string
  issue_id: string
  action: string
  detail: Record<string, unknown>
}

interface IssueStats {
  by_state: Partial<Record<IssueState, number>>
  by_severity: Record<string, number>
  total_open: number
  total_resolved: number
  nearest_timeout: string | null
}

interface ProjectStatus {
  name: string
  mode: 'e2e' | 'production' | 'development'
  sentinel: { pid: number | null; alive: boolean; started_at: string | null; crash_count: number }
  orchestrator: { pid: number | null; alive: boolean }
  issue_stats: IssueStats
}

// Timeline entry — the unified timeline model
interface TimelineEntry {
  id: string
  timestamp: string
  type: 'system' | 'user' | 'agent'
  content: string
  // System entries
  action?: string       // "registered", "diagnosed", "timeout_reminder", etc.
  icon?: string         // "●", "⏱", "✓", "✗"
  // Chat entries
  author?: string
}
```

### API client functions

```typescript
// Projects & processes
export function getProjects(): Promise<ProjectStatus[]>
export function getProjectStatus(name: string): Promise<ProjectStatus>
export function startSentinel(project: string): Promise<void>
export function stopSentinel(project: string): Promise<void>
export function restartSentinel(project: string): Promise<void>
export function startOrchestration(project: string): Promise<void>
export function stopOrchestration(project: string): Promise<void>

// Issues
export function getIssues(project: string, filters?: IssueFilters): Promise<Issue[]>
export function getIssue(project: string, id: string): Promise<Issue>
export function createIssue(project: string, data: CreateIssueData): Promise<Issue>
export function getAllIssues(filters?: IssueFilters): Promise<Issue[]>
export function getIssueStats(project: string): Promise<IssueStats>
export function getAllIssueStats(): Promise<Record<string, IssueStats>>

// Issue actions
export function investigateIssue(project: string, id: string): Promise<void>
export function fixIssue(project: string, id: string): Promise<void>
export function dismissIssue(project: string, id: string): Promise<void>
export function cancelIssue(project: string, id: string): Promise<void>
export function skipIssue(project: string, id: string): Promise<void>
export function muteIssue(project: string, id: string, pattern?: string): Promise<void>
export function extendTimeout(project: string, id: string, minutes: number): Promise<void>
export function sendIssueMessage(project: string, id: string, message: string): Promise<void>

// Groups
export function getIssueGroups(project: string): Promise<IssueGroup[]>
export function createIssueGroup(project: string, ids: string[], name: string, reason: string): Promise<IssueGroup>
export function fixGroup(project: string, groupId: string): Promise<void>

// Mutes
export function getMutePatterns(project: string): Promise<MutePattern[]>
export function addMutePattern(project: string, pattern: string, reason: string): Promise<MutePattern>
export function deleteMutePattern(project: string, id: string): Promise<void>

// Audit
export function getIssueAudit(project: string, since?: number, limit?: number): Promise<AuditEntry[]>

// Manager
export function getManagerStatus(): Promise<{ uptime: number; tick_interval: number }>
```

### Hooks

```typescript
// Polls project list + status every 5s
function useProjectOverview(): {
  projects: ProjectStatus[]
  loading: boolean
}

// Polls issue list + groups every 2s
function useIssueData(project: string): {
  issues: Issue[]
  groups: IssueGroup[]
  stats: IssueStats
  loading: boolean
}

// Polls single issue + builds unified timeline from audit + chat
function useIssueDetail(project: string, issueId: string): {
  issue: Issue
  timeline: TimelineEntry[]
  loading: boolean
}

// WebSocket to investigation agent (reuses chat.py infra)
function useIssueChat(project: string, issueId: string): {
  messages: ChatMessage[]
  send: (message: string) => void
  connected: boolean
}
```

### Timeline construction

The unified timeline merges two sources:

```typescript
function buildTimeline(audit: AuditEntry[], chatMessages: ChatMessage[]): TimelineEntry[] {
  const systemEntries: TimelineEntry[] = audit.map(a => ({
    id: `audit-${a.ts}`,
    timestamp: a.ts,
    type: 'system' as const,
    content: formatAuditAction(a),
    action: a.action,
    icon: AUDIT_ICONS[a.action] || '●',
  }))

  const chatEntries: TimelineEntry[] = chatMessages.map(m => ({
    id: `chat-${m.id}`,
    timestamp: m.timestamp,
    type: m.role === 'user' ? 'user' as const : 'agent' as const,
    content: m.content,
    author: m.role === 'user' ? 'You' : 'Agent',
  }))

  return [...systemEntries, ...chatEntries]
    .sort((a, b) => a.timestamp.localeCompare(b.timestamp))
}

const AUDIT_ICONS: Record<string, string> = {
  registered: '●',
  investigating: '🔍',
  diagnosed: '◆',
  awaiting_approval: '⏱',
  timeout_auto_approved: '⏱',
  timeout_reminder: '⏱',
  fixing: '🔧',
  verifying: '✓',
  deploying: '🚀',
  resolved: '✓',
  failed: '✗',
  cancelled: '⊘',
  skipped: '→',
  dismissed: '✕',
  muted: '🔇',
  auto_retry: '↻',
  duplicate_suppressed: '≡',
}
```

### Visual styling

System messages: centered, muted gray, small font, icon + action text.
User messages: right-aligned, blue bubble.
Agent messages: left-aligned, gray bubble, robot icon.

```typescript
const STATE_STYLES: Record<IssueState, { color: string; icon: string }> = {
  new:                { color: 'blue-400',    icon: '●' },
  investigating:      { color: 'yellow-400',  icon: '🔍' },
  diagnosed:          { color: 'orange-400',  icon: '◆' },
  awaiting_approval:  { color: 'amber-400',   icon: '⏱' },
  fixing:             { color: 'purple-400',  icon: '🔧' },
  verifying:          { color: 'indigo-400',  icon: '✓' },
  deploying:          { color: 'cyan-400',    icon: '🚀' },
  resolved:           { color: 'green-400',   icon: '✓' },
  dismissed:          { color: 'gray-500',    icon: '✕' },
  muted:              { color: 'gray-600',    icon: '🔇' },
  failed:             { color: 'red-400',     icon: '✗' },
  skipped:            { color: 'gray-400',    icon: '→' },
  cancelled:          { color: 'gray-500',    icon: '⊘' },
}

const SEVERITY_STYLES = {
  unknown:  { color: 'gray-400',   label: '?' },
  low:      { color: 'blue-300',   label: 'Low' },
  medium:   { color: 'yellow-400', label: 'Medium' },
  high:     { color: 'orange-400', label: 'High' },
  critical: { color: 'red-400',    label: 'Critical' },
}

const MODE_STYLES = {
  e2e:         { color: 'blue-500',   label: 'E2E' },
  production:  { color: 'red-500',    label: 'PROD' },
  development: { color: 'gray-500',   label: 'DEV' },
}
```

### Component tree

```
web/src/
├── pages/
│   ├── Manager.tsx                 # /manager — projects overview
│   ├── ManagerIssues.tsx           # /manager/:project/issues or /manager/issues
│   └── ManagerMutes.tsx            # /manager/:project/mutes
├── components/
│   ├── manager/
│   │   ├── ProjectCard.tsx         # project status card with controls
│   │   ├── ProcessControl.tsx      # start/stop/restart + status indicator
│   │   ├── ModeBadge.tsx           # E2E/PROD/DEV badge
│   │   └── ManagerStatus.tsx       # service health bar
│   ├── issues/
│   │   ├── IssueList.tsx           # filterable list with urgency sections
│   │   ├── IssueRow.tsx            # single row: state, severity, timer
│   │   ├── IssueDetail.tsx         # slide-out panel container
│   │   ├── IssueActions.tsx        # state-aware action buttons
│   │   ├── IssueTimeline.tsx       # unified timeline (system + chat)
│   │   ├── TimelineEntry.tsx       # single entry (system/user/agent variants)
│   │   ├── IssueDiagnosis.tsx      # diagnosis display
│   │   ├── IssueError.tsx          # raw error + occurrence count
│   │   ├── IssueRelated.tsx        # group view
│   │   ├── IssueFilter.tsx         # filter dropdowns
│   │   ├── GroupList.tsx           # group summary list
│   │   ├── BulkActions.tsx         # multi-select actions
│   │   ├── TimeoutCountdown.tsx    # live countdown + progress bar
│   │   ├── MuteManager.tsx         # mute pattern CRUD
│   │   ├── SeverityBadge.tsx       # colored severity indicator
│   │   └── IssueCountBadge.tsx     # summary badge for project cards
│   └── shared/
│       └── ChatInput.tsx           # reusable message input
├── hooks/
│   ├── useProjectOverview.ts
│   ├── useIssueData.ts
│   ├── useIssueDetail.ts
│   └── useIssueChat.ts
└── lib/
    └── api.ts                      # extended with all manager endpoints
```

### Chat architecture

Per-issue chat reuses existing `chat.py` WebSocket, scoped by issue:

```
Browser → WS /ws/{project}/issue-chat?issue_id=ISS-003
        → Server resolves issue.investigation_session
        → claude -p --resume {session_id}
        → Streaming response back to browser
```

If no investigation session exists, spawns new one with investigation template.

**State transitions are triggered ONLY via action buttons, never from chat text.** Chat is for conversation with the agent — asking questions, providing context. The buttons are the control interface.

### Graceful degradation

When set-manager is not running or issues are not enabled for a project:

```
┌─────────────────────────────────────────────────────────────┐
│  Issue management is not available.                          │
│                                                              │
│  The set-manager service is not running.                     │
│  Start it with: set-manager start                            │
│                                                              │
│  Or enable issues for this project in manager config.        │
└─────────────────────────────────────────────────────────────┘
```

## Dependencies

- `issue-management-engine` — all backend API endpoints
- Existing: React, Tailwind CSS 4.2, Vite
- Existing: `chat.py` WebSocket infrastructure
- Existing: `useSentinelData`, `useProject` hooks as patterns

## Risks

1. **Polling overhead** — Mitigated by 2s for list, 5s for overview, detail only when panel open.
2. **Chat session lifecycle** — Mitigated by fallback to new session with context replay.
3. **Slide-out panel space** — Timeline + chat needs room. If too cramped, can switch to full page.
4. **Manager not running** — Graceful degradation with clear instructions.
5. **Many states × buttons** — State-aware button map is defined explicitly to prevent confusion.

## Success Criteria

1. Projects overview shows all environments with live process status and start/stop controls
2. Issue list is filterable and grouped by urgency with live countdown timers
3. Issue detail slide-out shows unified timeline with system events and chat interleaved
4. Action buttons are state-aware (only valid actions shown per state)
5. Chat connects to investigation agent and supports multi-turn conversation
6. Groups can be created via multi-select and fixed together
7. Mute patterns manageable from UI
8. Cross-project issues view works
9. Graceful degradation when manager is not running
10. All state changes reflected in UI within 2 seconds
