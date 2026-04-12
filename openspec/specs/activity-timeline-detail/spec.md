## ADDED Requirements

<!--
IN SCOPE:
- Backend heuristic parser that converts Claude session JSONL files into typed sub-spans (LLM wait, per-tool execution, sub-agent invocation, overhead)
- Drilldown API endpoint returning sub-spans for a requested change + time window
- Sub-agent linking via prompt-substring matching and timestamp proximity
- File-mtime-based cache invalidation (no rescans when nothing changed)
- Frontend click-to-drill panel showing mini-Gantt + top-N longest operations + sub-agent list
- Terminal-style visual overhaul of the Activity tab
- Auto-fit zoom on initial load and on container resize

OUT OF SCOPE:
- New event emissions or engine modifications
- Per-tool-call argument display (the actual Bash command string beyond the top-N preview)
- Hook timing attribution from <system-reminder> content
- LLM-based session summarization (no extra LLM calls)
- Recursive sub-agent expansion beyond one level
- Real-time WebSocket streaming of detail spans
- Cost/billing aggregation from session usage blocks
- Restyling tabs other than Activity
-->

### Requirement: Session detail endpoint

The system SHALL expose `GET /api/{project}/activity-timeline/session-detail?change={name}&from={ts}&to={ts}` that returns typed sub-spans reconstructed from the change's worktree session JSONL files for the requested time window.

#### Scenario: Basic drilldown request

- **WHEN** a client requests `GET /api/{project}/activity-timeline/session-detail?change=add-auth&from=2026-04-08T01:08:00Z&to=2026-04-08T01:31:00Z`
- **THEN** the response SHALL include `sub_spans` (array), `total_llm_calls` (int), `total_tool_calls` (int), `top_operations` (array of up to 5 longest individual ops), `subagent_count` (int), and `cache_hit` (bool)
- **AND** every sub-span SHALL have `category`, `start`, `end`, `duration_ms`, `change`, and a `detail` dict with at minimum `session` (the source session UUID)

#### Scenario: Cache hit when no session jsonl has changed

- **WHEN** the cache file `<project>/set/orchestration/activity-detail.jsonl` exists
- **AND** every relevant session jsonl in the worktree has an mtime older than the cache mtime
- **THEN** the endpoint SHALL serve sub-spans from the cache without rescanning
- **AND** the response SHALL include `cache_hit: true`

#### Scenario: Cache miss triggers rescan

- **WHEN** any session jsonl has been modified after the cache was written (or the cache does not exist)
- **THEN** the endpoint SHALL rescan the affected worktree's session jsonls
- **AND** rewrite the cache file with the fresh sub-spans
- **AND** the response SHALL include `cache_hit: false`

#### Scenario: Time range filtering

- **WHEN** a client passes `from=T1` and `to=T2`
- **THEN** only sub-spans overlapping `[T1, T2]` SHALL be returned
- **AND** sub-spans partially outside the range SHALL be clipped to the boundaries (same semantics as the main timeline endpoint)

#### Scenario: No session jsonl files for the change

- **WHEN** the change has no worktree directory or no session jsonl files
- **THEN** the response SHALL return `{"sub_spans": [], "total_llm_calls": 0, "total_tool_calls": 0, "top_operations": [], "subagent_count": 0, "cache_hit": false}`
- **AND** a WARNING SHALL be logged with the change name

### Requirement: Sub-span reconstruction from session JSONL

The system SHALL reconstruct typed sub-spans from Claude session JSONL files by walking entries in chronological order and classifying time gaps.

#### Scenario: LLM wait span from user → assistant gap

- **WHEN** a `user` entry at T1 is immediately followed by an `assistant` entry at T2 in the same session
- **THEN** an `agent:llm-wait` sub-span SHALL be produced with `start=T1`, `end=T2`, `duration_ms=T2-T1`
- **AND** the `detail` dict SHALL include `model` (from `assistant.message.model`) and `tokens_in`/`tokens_out` if present in `assistant.message.usage`

#### Scenario: Tool execution span from tool_use → tool_result pair

- **WHEN** an `assistant` entry contains a `tool_use` block with `id=X` and `name=Bash` at T1
- **AND** a subsequent `user` entry contains a `tool_result` block with `tool_use_id=X` at T2
- **THEN** an `agent:tool:bash` sub-span SHALL be produced with `start=T1`, `end=T2`, `duration_ms=T2-T1`

#### Scenario: Tool name normalization

- **WHEN** a `tool_use` block has `name="Bash"` (or `"Edit"`, `"Read"`, `"Write"`, `"Glob"`, `"Grep"`, `"WebFetch"`, `"WebSearch"`, `"Task"`, `"Skill"`)
- **THEN** the resulting category SHALL be `agent:tool:<lowercased name>` (e.g., `agent:tool:bash`, `agent:tool:webfetch`)
- **AND** unknown tool names SHALL be mapped to `agent:tool:other` with the actual name preserved in the `detail.tool` field

#### Scenario: Sub-agent linking via prompt match

- **WHEN** a parent session contains a `Task` tool_use at T1 with prompt P
- **AND** a sibling session in the same `~/.claude/projects/<mangled>/` directory has its first `user` entry at T2 (within 5 seconds of T1) with content matching the first 200 chars of P
- **THEN** the parent's `agent:tool:task` span SHALL be replaced with an `agent:subagent:<purpose>` span
- **AND** the `detail` dict SHALL include `subagent_session_id` (the matched session UUID)
- **AND** the matched sub-session's wall window SHALL be used as the sub-span's start/end (not the parent's tool_use → tool_result times)

#### Scenario: Sub-agent matching failure falls back

- **WHEN** a `Task` tool_use exists but no sibling session matches by prompt or timestamp
- **THEN** the sub-span SHALL remain `agent:tool:task` (no `agent:subagent:*` upgrade)
- **AND** a WARNING SHALL be logged with the parent session UUID and the unmatched task prompt prefix

#### Scenario: Overhead calculation

- **WHEN** the sub-span builder finishes a session
- **THEN** it SHALL compute `overhead = session_wall_time - sum(llm_wait_spans) - sum(tool_spans) - sum(subagent_spans)`
- **AND** if `overhead > 0`, emit one `agent:overhead` sub-span per session covering the unaccounted time
- **AND** if `overhead < 0` (impossible normally), log WARNING with the session id and skip the overhead span

### Requirement: Cache invalidation by mtime

The system SHALL maintain a sub-span cache file at `<project>/set/orchestration/activity-detail.jsonl` and invalidate it based on session jsonl modification times.

#### Scenario: Cache valid → serve from cache

- **WHEN** the cache file exists with mtime M
- **AND** every session jsonl across all relevant worktrees has mtime ≤ M
- **THEN** the endpoint SHALL parse the cache file and serve its sub-spans without re-reading session jsonls

#### Scenario: One session jsonl newer than cache → partial rescan

- **WHEN** session jsonl S has mtime > cache mtime
- **THEN** the endpoint SHALL rescan only S (and its worktree dir for new sibling sessions)
- **AND** merge the resulting sub-spans into the cache, replacing entries from S
- **AND** rewrite the cache file with the updated set

#### Scenario: Cache file corrupted → full rebuild

- **WHEN** the cache file exists but JSONL parsing fails on any line
- **THEN** the endpoint SHALL log WARNING, delete the corrupted cache, and perform a full rebuild from all session jsonls

### Requirement: Frontend click-to-drill panel

The Activity tab SHALL render an inline drilldown panel when a user clicks an `implementing` span (or any span with `duration_ms > 60_000`).

#### Scenario: Click on implementing span opens drilldown

- **GIVEN** the Activity tab is open with a populated timeline
- **WHEN** the user clicks an `implementing` span for change X
- **THEN** the component SHALL fetch `/activity-timeline/session-detail?change=X&from=...&to=...`
- **AND** render a panel BELOW the main Gantt containing: per-category breakdown bars, a mini-Gantt showing the sub-spans, a top-5 longest operations list, and a sub-agent list (if `subagent_count > 0`)

#### Scenario: Click on the same span again collapses

- **GIVEN** a drilldown panel is currently open for span S
- **WHEN** the user clicks span S again (or the panel close button)
- **THEN** the panel SHALL be hidden
- **AND** the main Gantt SHALL be unchanged

#### Scenario: Click on a different span replaces the panel

- **GIVEN** a drilldown panel is open for span S1
- **WHEN** the user clicks a different span S2
- **THEN** the panel SHALL fetch and render data for S2
- **AND** the previous data SHALL be replaced

#### Scenario: Click on a sub-agent row drills one level deeper

- **GIVEN** the drilldown panel for span S shows a sub-agent list
- **WHEN** the user clicks a sub-agent row
- **THEN** the panel content SHALL be replaced with the sub-agent's own breakdown (one level only — no further drilling)
- **AND** a "back" button SHALL allow returning to the parent breakdown

#### Scenario: Drilldown for short span is not offered

- **WHEN** the user clicks a span with `duration_ms ≤ 60_000` (e.g., a quick gate)
- **THEN** no drilldown SHALL be opened (the existing tooltip is sufficient)

### Requirement: Terminal-style visual design

The Activity tab SHALL use a terminal aesthetic consistent with the rest of the dashboard.

#### Scenario: True-black background

- **WHEN** the Activity tab renders
- **THEN** the background SHALL be `#000000` (not Tailwind `neutral-950`)
- **AND** lane backgrounds SHALL alternate between `#000000` and `#0a0a0a` for stripe contrast

#### Scenario: ASCII separator characters in headers

- **WHEN** the Activity tab renders the breakdown section header
- **THEN** the title row SHALL use ASCII characters (`─`, `│`, `┌`, `┐`, `└`, `┘`) for visual structure rather than rounded Tailwind borders

#### Scenario: Hover lattice across all lanes

- **WHEN** the user hovers the Gantt at horizontal position X
- **THEN** a 1px vertical line SHALL be drawn at X spanning the full height of the Gantt
- **AND** the line SHALL move with the cursor and disappear on mouseleave

### Requirement: Auto-fit zoom on initial load

The Activity tab SHALL compute the initial `pxPerSecond` zoom level so that the entire timeline fits the available container width on first render.

#### Scenario: Initial load fits container width

- **WHEN** the Activity tab loads timeline data with wall time W and container width C
- **THEN** `pxPerSecond` SHALL be set to `C / W * 1000` so the timeline renders without horizontal scrolling
- **AND** the user SHALL still be able to zoom in/out manually after initial load

#### Scenario: Container resize re-fits

- **WHEN** the browser window resizes (and thus the container width changes)
- **AND** the user has not manually zoomed since the last data load
- **THEN** `pxPerSecond` SHALL be recomputed to fit the new width

#### Scenario: Manual zoom disables auto-fit

- **WHEN** the user clicks the +/- zoom buttons or scrolls with Ctrl
- **THEN** auto-fit SHALL be disabled until the next data refresh
- **AND** subsequent container resizes SHALL NOT change the manual zoom level

#### Scenario: Very short timeline clamps to max zoom

- **WHEN** the timeline wall time is < 60 seconds
- **THEN** `pxPerSecond` SHALL be clamped to a maximum of 5px/s
- **AND** the timeline SHALL NOT stretch to fill the entire container if doing so would make individual spans larger than 50px each
