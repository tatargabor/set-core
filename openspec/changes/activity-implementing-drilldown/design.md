# Design: activity-implementing-drilldown

## Context

The previous change (`fix-activity-timeline-claude-coverage`) made the Activity view honest about wall time — it now shows that `implementing` is ~75% of orchestration time. This change drills inside that 75% to show *where* the agent's time goes (LLM wait vs tool execution vs overhead) using existing Claude session JSONL files. No new instrumentation, no new LLM calls, pure heuristic parsing.

### Data source: Claude session JSONL

Each agent dispatch creates one or more session JSONL files at:
```
~/.claude/projects/-<mangled-worktree-path>/<session-uuid>.jsonl
```

A real foundation-setup session (18m, 295 entries, 100 tool calls) parses cleanly:

| Entry type | Count | Carries timestamp? |
|---|---|---|
| `user` | 104 | yes |
| `assistant` | 164 | yes |
| `attachment` | 25 | yes |
| `queue-operation` | 2 | yes |

Each `assistant` entry has:
- `timestamp` (ISO 8601, ms precision)
- `message.content`: array of blocks (`text`, `tool_use`, `thinking`)
- `message.usage`: token counts incl. cache hits
- `requestId`: ties multiple assistant messages from one API call together
- `parentUuid`: links to the previous turn

Each `user` entry that's a tool result has:
- `message.content`: array of `tool_result` blocks with `tool_use_id` references
- `toolUseResult`: structured tool output
- `sourceToolAssistantUUID`: link back to the assistant message that emitted the tool_use

### What we can compute (heuristics)

**LLM wait** = time gap between a `user` message and the next `assistant` message in the same session (same parentUuid chain). This is the round-trip latency to Claude API + thinking time.

**Tool execution** = time gap between an `assistant` block emitting `tool_use(id=X)` and the matching `user` block with `tool_result(tool_use_id=X)`. Attribution by tool name from the `tool_use.name` field.

**Sub-agents** = a `Task` tool spawns a separate session in the same Claude projects directory. The new session's first `user` message references the parent session via metadata in the prompt. Linked one level deep; deeper recursion gets a flat `agent:subagent:*` block.

**Overhead** = wall time of the session minus everything above. This is the residual: hook execution, ralph loop transitions, stream parsing, and any unaccounted time.

## Goals / Non-Goals

**Goals:**
- Make the agent's 60-100m per change inspectable at the operation level
- Show sub-agent invocations as their own visible chunks (not lumped into Bash/Task)
- Click-to-drill UI that doesn't slow down the main timeline
- Terminal aesthetic that matches the rest of the dashboard
- Default zoom that fills the viewport — no horizontal scrolling needed at first glance

**Non-Goals:**
- Per-call argument introspection (what specifically Bash ran). The Sessions tab already covers that.
- Hook timing attribution. Hooks don't have their own timestamps; they get bundled into overhead.
- Sub-agent recursion beyond one level.
- New event emissions. The orchestrator stays untouched.
- Real-time streaming. Refresh is fine.
- LLM-based summarization of what the agent did. Pure heuristic.

## Decisions

### 1. Cache file format and location

The detail cache lives at `<project>/set/orchestration/activity-detail.jsonl`. Each line is one sub-span with the same shape as main timeline spans, plus a `parent_span_id` field linking it to the parent `implementing` span:

```json
{"category":"agent:llm-wait","change":"foundation-setup","start":"2026-04-08T23:13:02.489Z","end":"2026-04-08T23:13:04.828Z","duration_ms":2339,"detail":{"session":"b3fe274f","tokens_in":120,"tokens_out":340,"model":"sonnet"},"parent_span_id":"impl:foundation-setup:1"}
```

**Why JSONL not JSON:** append-friendly, line-streamable, matches existing `orchestration-events.jsonl` convention.

**Why store in project dir not runtime dir:** the project dir is the canonical location for orchestration artifacts; the cache survives if runtime is wiped.

**Cache invalidation:** on read, compare cache mtime with the newest session jsonl mtime in any worktree dir. If any session is newer, rescan that worktree. Otherwise serve the cache. This is fast (one stat call per dir).

### 2. Endpoint shape: drilldown only, not always-on

Two endpoints, not one:
- `GET /api/{project}/activity-timeline` — unchanged, still fast
- `GET /api/{project}/activity-timeline/session-detail?change=X&from=T1&to=T2` — new, returns sub-spans for the requested window

**Why two endpoints instead of a `?detail=true` flag:** the main view is loaded on every refresh and must stay sub-200ms. The drilldown is a click action and tolerates 1-2s of parsing for an 8-change run. Separating them keeps both code paths simple and the perf budget explicit.

### 3. Sub-agent linking

Sub-agent sessions are siblings in the same `~/.claude/projects/<mangled>/` directory. We link them by:
1. Walking the parent session's `Task` tool_use blocks. Each carries the prompt sent to the sub-agent.
2. Scanning sibling sessions in the same dir for one whose first `user` content matches that prompt (substring match on the first 200 chars).
3. The matched sub-session's wall window (first → last entry) becomes a `agent:subagent:<purpose>` span on the parent timeline.

**Why prompt-substring matching:** Claude session JSONLs don't carry an explicit `parent_session_id`. The prompt is the only stable link.

**Failure mode:** if matching fails, the sub-agent time stays bundled in `agent:tool:task` (the parent's view of the Task tool execution). Logs at WARNING level so we can see how often it happens.

### 4. Click-to-drill UI

Clicking a span in the main Gantt:
1. Sets local React state `expandedSpan = span`
2. Fetches `/activity-timeline/session-detail?change=...&from=...&to=...`
3. Renders an inline `<ActivitySessionDetail>` panel BELOW the main Gantt (not as a modal — keeps the main timeline visible for context)

The panel has three sections:
- **Mini-Gantt**: same renderer as the main view, scoped to the sub-spans. Categories on the Y axis, time on the X axis.
- **Top-5 list**: longest individual operations as one-line entries (`Bash 0:45  pnpm install ...truncated`)
- **Sub-agent list**: clickable rows (`Task: explore-codebase  4:23`) — clicking drills into that sub-agent's own breakdown (one level only)

Click outside the panel or click the same span again → collapses.

### 5. Terminal style overhaul

Replaces Tailwind-default dark grays with explicit terminal colors:
- Background: `#000` (true black) instead of `#0a0a0a`
- Lane separators: ` │ ` ASCII vertical bars between time axis and category labels
- Span borders: 1px solid in same hue as fill, slightly brighter
- Lane label font: `font-mono` (already), tighter line-height, uppercase optional
- Time axis: `─` style horizontal rule, ticks rendered as `│` characters at minor marks
- Hover indicator: full-height vertical line at cursor X — shows the same time across all lanes
- Span tooltip: terminal box border style (`┌──┐ │ └──┘`), no rounded corners

### 6. Auto-fit zoom on initial load

`pxPerSecond` initial value is computed in `ActivityView` from `containerWidth / (maxTime - minTime) * 1000`. The container width is captured via `useRef` + `ResizeObserver`. On data-load and on container resize, `pxPerSecond` is reset to fit. Manual zoom buttons override this and disable auto-fit until next data refresh.

**Edge case:** if data is very short (< 1m), clamp `pxPerSecond` to a max of 5px/s so the timeline isn't a single huge block.

## Risks

**R1: JSONL format drift.** Claude session JSONL is an internal format. Field names like `tool_use_id`, `parentUuid`, `requestId`, `toolUseResult` could change or rename. Mitigation: defensive parser — if a field is missing, log WARNING with session id and skip the entry. Tests cover the current format and lock it.

**R2: Sub-agent matching false positives.** Two sub-agents with very similar prompts could match the wrong session. Mitigation: also compare the parent session's tool_use timestamp with the sub-session's first-entry timestamp — they should be within ~1 second. If not, no match.

**R3: Large sessions cause slow drilldown.** A 5MB session jsonl with 5000 entries can take a few seconds to parse fully. Mitigation: stream parser using `ijson` or line-by-line `json.loads` (already what we'd do); cache the result aggressively. If parse > 5s, return partial result with a `truncated: true` flag.

**R4: Overhead category absorbs everything we don't understand.** If the heuristic misses a kind of operation, it shows up in `agent:overhead` and looks larger than reality. Mitigation: log every entry-type counter so we can see what's in `overhead`. Tests assert that for a known session, `overhead` is < 25% (the rest is captured).

**R5: Click-to-drill UX with very small spans.** Tiny spans on a fully-zoomed-out timeline are <2px wide and not clickable. Mitigation: a hidden invisible overlay enlarges the click target to 8px. Tooltip still shows the real boundaries.

## Alternatives Considered

### A1: Always-on detail (Option A from the previous discussion)

Run the analyzer on every `/activity-timeline` request and inline the sub-spans into the main response. Rejected because:
- Adds 1-2s to every refresh, including the auto-30s polling during running orchestrations
- Forces all users to pay the cost even if they don't care about drilldown
- Mixes semantically distinct data (high-level timeline vs operation detail) into one response

### A2: LLM-based summarization

Send the session jsonl to a small LLM (haiku) and ask "what was the agent doing in chunks of 5 minutes?" Rejected because:
- The user explicitly said "no extra LLM calls"
- LLM time is 10-30s vs heuristic time of 100-500ms
- Heuristic is exact (timestamps + tool names) while LLM is approximate

### A3: Recursive sub-agent expansion

Show sub-agents of sub-agents fully expanded in the same drilldown. Rejected because:
- Visual complexity grows with depth
- Click-to-drill into a sub-agent already gives the user an explicit way to descend manually
- Sub-agents in this codebase rarely go more than 2 levels deep

### A4: Hook attribution from `<system-reminder>` blocks

Parse the `<system-reminder>` content in user messages to identify which hook fired and how long it took. Rejected because:
- Hooks don't have their own timestamps in the session jsonl
- The only signal is "the user message contained hook output", not "the hook took X ms"
- Attempting to back-calculate hook time would mostly give noise

Hooks remain bundled in `agent:overhead` for now. Can be addressed in a future change if hook events get explicit logging.

## Rollout

1. Implement `lib/set_orch/api/activity_detail.py` with the heuristic parser
2. Unit test against the real foundation-setup session jsonl (locked snapshot)
3. Wire the new sub-route in `activity.py`
4. Frontend: terminal style pass first (visible immediately, low risk)
5. Frontend: auto-fit zoom (visible immediately, low risk)
6. Frontend: click handler + drilldown panel (new component)
7. Manual verify: click an implementing span on a real run, confirm the breakdown matches expectations
