# Change: activity-implementing-drilldown

## Why

The Activity view now correctly attributes time to gates, LLM verifier calls, planning, and `implementing` (DISPATCH→MERGE_START sessions). On a 9h run, `implementing` is 75% of the wall time — one giant block per change. That's still a black box: there's no way to see *what* the agent spent its 60-100 minutes per change on.

A quick measurement against a real session jsonl shows the breakdown is meaningful:
- ~42% LLM wait (Claude API roundtrip)
- ~10% tool execution (Bash dominates, then Glob/Edit/Write)
- ~48% currently unaccounted ("agent overhead": hooks, sub-agents, ralph loop transitions, multi-session boundaries)

The data exists — every agent turn is logged in `~/.claude/projects/<mangled-wt>/<uuid>.jsonl` with millisecond timestamps and explicit tool_use/tool_result blocks. We just need to read it. Sub-agents (Task tool) spawn their own session jsonls in the same directory and can be linked via `parentUuid` / `isSidechain`.

The current Activity view also has UX gaps: the timeline isn't scaled to viewport width by default (you have to zoom out), and the visual style is generic dark Tailwind rather than the terminal aesthetic the rest of the dashboard uses.

## What Changes

### 1. Background analyzer + cached detail file (no LLM cost)

A pure-Python heuristic scans worktree session jsonls for each change, reconstructs typed sub-spans within the implementing window, and writes them to a cache file:

```
<project>/set/orchestration/activity-detail.jsonl
```

The analyzer runs:
- On-demand when the new drilldown endpoint is called (with mtime-based caching to avoid rescans)
- Optionally as a sidecar after orchestration milestones (deferred to follow-up)

No new LLM calls. Pure I/O and JSON parsing — machine time is acceptable.

### 2. New drilldown endpoint

```
GET /api/{project}/activity-timeline/session-detail?change=X&from=T1&to=T2
```

Returns sub-spans for the time window:
- `agent:llm-wait` — gap from `user` message → next `assistant` message (Claude API roundtrip)
- `agent:tool:bash` / `agent:tool:edit` / `agent:tool:read` / `agent:tool:write` / `agent:tool:glob` / `agent:tool:grep` / `agent:tool:webfetch` / `agent:tool:websearch` / `agent:tool:task` (sub-agent) / `agent:tool:skill` / `agent:tool:other`
- `agent:subagent:<purpose>` — when a Task tool spawns a sub-agent, link to its own session jsonl and recursively expand its sub-spans (one level deep, not unlimited recursion)
- `agent:overhead` — gaps not attributable to any of the above (hook execution, ralph loop transitions, stream parsing)

Response also includes: total LLM calls, total tool calls, top 5 longest individual operations, sub-agent count.

### 3. Click-to-expand UI in the Activity tab

Clicking an `implementing` span in the main Gantt opens an inline drilldown panel showing:
- Per-category bar chart (sorted by time)
- A nested mini-Gantt with the sub-spans (using the same renderer as the main view)
- Top 5 longest operations as a list (e.g., "Bash 'pnpm install' — 45s")
- Sub-agent count + clickable list to drill into each sub-agent's own breakdown

Same drilldown behavior for spans of any sufficiently-long category, but the primary use case is `implementing`.

### 4. Terminal-style design pass on the whole Activity view

- **Full-width default zoom**: `pxPerSecond` initial value computed so the entire timeline fits the available width on first load. Manual zoom buttons still work.
- **Terminal aesthetic**: monospace lane labels, ASCII-style box-drawing borders, single-character separators (`│`, `─`, `█`), high-contrast color palette (the existing categorical colors but on a true `#000` background, not `#0a0a0a`).
- **Sticky time axis**: time labels stick to the top during vertical scroll (not currently the case).
- **Hover lattice**: vertical hover line crosses all lanes when mousing over the timeline (for cross-lane time correlation).
- **Span density indicators**: small numeric badges showing operation count when zoomed out and individual blocks become too small to render.

## Capabilities

### New Capabilities
- `activity-timeline-detail` — backend session-jsonl analyzer + drilldown endpoint

### Modified Capabilities
- `activity-timeline-api` — adds the session-detail endpoint as a sub-route
- `activity-dashboard` — terminal-style redesign + drilldown UI

## Impact

- `lib/set_orch/api/activity_detail.py` — new module: session jsonl analyzer + sub-span builder + caching
- `lib/set_orch/api/activity.py` — new sub-route registration for session-detail endpoint
- `lib/set_orch/api/helpers.py` — minor: helper to find all session jsonls for a worktree (may already exist in `sessions.py`, reuse)
- `web/src/lib/api.ts` — new TypeScript types `ActivitySessionDetail`, `SubSpan`; new function `getSessionDetail()`
- `web/src/components/ActivityView.tsx` — terminal style pass; click handler on spans; auto-fit zoom on initial load; sticky time axis; hover lattice
- `web/src/components/ActivitySessionDetail.tsx` — new component: drilldown panel with mini-Gantt + top-N + sub-agent list
- `tests/unit/test_activity_detail.py` — new file: synthetic session jsonl → expected sub-spans

## Out of Scope

- New event emissions or engine modifications. This change is read-only on existing data.
- Cost/billing aggregation from the session jsonl `usage` blocks. Can be added later as a separate breakdown.
- Per-tool-call argument display (e.g., what command Bash ran). The drilldown shows aggregates and the top-5 longest operations only — full argument inspection belongs in the existing Sessions tab.
- Real-time WebSocket streaming of detail spans during a live run. Periodic refresh (with cache) is sufficient.
- Recursive sub-agent expansion beyond one level. A sub-agent that spawns another sub-agent shows the second level as a single `agent:subagent:*` block, not expanded further.
- Hook timing inference from `<system-reminder>` content. The current pass treats hook time as part of `agent:overhead`. A future change can add per-hook attribution.
- Full redesign of the Sessions tab. Only the Activity tab is restyled.
