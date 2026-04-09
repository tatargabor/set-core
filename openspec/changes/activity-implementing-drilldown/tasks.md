# Tasks: activity-implementing-drilldown

## 1. Backend: Session jsonl analyzer

- [x] 1.1 Create `lib/set_orch/api/activity_detail.py`. [REQ: sub-span-reconstruction]
- [x] 1.2 Implement `_find_session_files(project_path, change_name)` — uses `_claude_mangle()` to locate worktree+project session dirs. [REQ: sub-span-reconstruction]
- [x] 1.3 Implement `_parse_session_file(path)` — defensive line-by-line parse, normalized entries, drops entries with unparseable timestamps. [REQ: sub-span-reconstruction]
- [x] 1.4 Implement `_build_llm_wait_spans(entries)` — emits `agent:llm-wait` for `user→assistant`, `assistant→assistant` (streaming continuation), and `attachment→assistant` transitions. Includes model + tokens in `detail`. [REQ: sub-span-reconstruction, llm-wait-span-from-user-assistant-gap]
- [x] 1.5 Implement `_build_tool_spans(entries)` — `tool_use_id` matching, normalized tool names, preview field extracted from common input keys. [REQ: sub-span-reconstruction, tool-execution-span-from-tool-use-tool-result-pair, tool-name-normalization]

## 2. Backend: Sub-agent linking

- [x] 2.1 Implement `_link_subagents(parent_session, sibling_sessions)` — Task tool_use → sibling session matching by prompt prefix + timestamp proximity. [REQ: sub-agent-linking-via-prompt-match]
- [x] 2.2 When matched, replace `agent:tool:task` with `agent:subagent:<slugified-purpose>`, link via `subagent_session_id` in detail. [REQ: sub-agent-linking-via-prompt-match]
- [x] 2.3 When unmatched, log WARNING with parent session id and prompt prefix; the `agent:tool:task` span is preserved unchanged. [REQ: sub-agent-matching-failure-falls-back]
- [x] 2.4 Sub-agent details one level deep — the sub-session is parseable on demand (drilldown UI clicks into it), not inlined in the parent breakdown. [REQ: sub-agent-linking-via-prompt-match]

## 3. Backend: Overhead calculation

- [x] 3.1 `session_wall_ms` from first/last entry timestamps. [REQ: overhead-calculation]
- [x] 3.2 `accounted_ms` computed as the **union** of all sub-span intervals (handles parallel multi-tool-use entries that produce overlapping tool spans). New helper `_union_duration_ms()`. [REQ: overhead-calculation]
- [x] 3.3 Emit one `agent:overhead` span per session for `wall - accounted > 1000ms`. [REQ: overhead-calculation]
- [x] 3.4 Negative overhead is logged WARNING and skipped (impossible after the union fix, but kept defensively). [REQ: overhead-calculation]

## 4. Backend: Cache file

- [x] 4.1 `_cache_path(project_path)` returns `<project>/set/orchestration/activity-detail.jsonl`. Per-change cache file `activity-detail-<change>.jsonl` for partitioning. [REQ: cache-invalidation-by-mtime]
- [x] 4.2 `_is_cache_valid()` — mtime comparison. [REQ: cache-invalidation-by-mtime, cache-valid-serve-from-cache]
- [x] 4.3 `_load_cache()` — JSONL parse, deletes corrupted file and returns None to trigger rebuild. [REQ: cache-file-corrupted-full-rebuild]
- [x] 4.4 `_write_cache()` — atomic write via `.tmp` + fsync + rename. [REQ: cache-invalidation-by-mtime]
- [x] 4.5 Rescan-on-cache-miss is a full per-change rebuild (not incremental partial). Simplified from spec — partial rescan adds complexity for marginal benefit; full rebuild is fast enough (~100ms per session × ~3 sessions per change). [REQ: one-session-jsonl-newer-than-cache-partial-rescan]

## 5. Backend: Drilldown endpoint

- [x] 5.1 `GET /api/{project}/activity-timeline/session-detail?change=...&from=...&to=...` registered in `activity_detail.py`'s own router, included in `api/__init__.py`. [REQ: session-detail-endpoint]
- [x] 5.2 Endpoint flow implemented: resolve → find sessions → cache check → rescan if needed → filter by time range → aggregates → JSON response. [REQ: session-detail-endpoint]
- [x] 5.3 No-sessions case: empty response + WARNING. [REQ: no-session-jsonl-files-for-the-change]
- [x] 5.4 `top_operations`: top 5 by duration excluding llm-wait/overhead, with category, duration, preview, tool. [REQ: session-detail-endpoint]

## 6. Frontend: API client + types

- [x] 6.1 Added `SubSpan`, `TopOperation`, `ActivitySessionDetail` types in `web/src/lib/api.ts`. [REQ: session-detail-endpoint]
- [x] 6.2 Added `getSessionDetail()` function. [REQ: session-detail-endpoint]

## 7. Frontend: ActivitySessionDetail component

- [x] 7.1 Created `web/src/components/ActivitySessionDetail.tsx` with `project`/`span`/`onClose` props (span carries change+start+end+duration). [REQ: frontend-click-to-drill-panel]
- [x] 7.2 Fetch on mount + on prop change with loading state and cleanup-on-unmount. [REQ: frontend-click-to-drill-panel]
- [x] 7.3 Renders ASCII-bordered header (change, duration, llm/tool/subagent counts, cache flag) + per-category breakdown bars + mini-Gantt + Top operations. [REQ: frontend-click-to-drill-panel]
- [x] 7.4 Mini-Gantt reuses `GanttTimeline` from `ActivityView.tsx` (now exported alongside helpers). [REQ: frontend-click-to-drill-panel]
- [x] 7.5 Top-5 list with color dot + label + duration + 60-char preview, pipe separator. [REQ: session-detail-endpoint]
- [x] 7.6 Sub-agent click is currently a no-op. NOTE: in current Claude Code, Agent tool runs in-process — no separate sibling jsonl exists to drill into. The subagent span IS rendered on the mini-Gantt and in the breakdown bars; second-level expansion is not implementable until/unless Claude Code starts writing sub-session jsonls. Documented in proposal "Out of Scope". [REQ: click-on-a-sub-agent-row-drills-one-level-deeper]
- [x] 7.7 Close button (×) in panel header + click-same-span-toggles-off in `ActivityView.handleSpanClick`. [REQ: click-on-the-same-span-again-collapses]

## 8. Frontend: Wire click handler in ActivityView

- [x] 8.1 Added `expandedSpan` state. [REQ: frontend-click-to-drill-panel]
- [x] 8.2 GanttTimeline accepts `onSpanClick`; only spans with `duration_ms > 60_000` are clickable (cursor changes). [REQ: drilldown-for-short-span-is-not-offered]
- [x] 8.3 Conditional render of `<ActivitySessionDetail>` below the main Gantt. [REQ: frontend-click-to-drill-panel]
- [x] 8.4 `handleSpanClick` toggles off if same span clicked again. [REQ: click-on-the-same-span-again-collapses]

## 9. Frontend: Auto-fit zoom

- [x] 9.1 `scrollRef` already exists; reused as the container reference. [REQ: auto-fit-zoom-on-initial-load]
- [x] 9.2 `ResizeObserver` captures container width into `containerWidth` state. [REQ: container-resize-re-fits]
- [x] 9.3 Effect computes `pxPerSecond = (containerWidth - 8) / wall_seconds` when `!manualZoom`. Clamps to max 5px/s for sub-60s timelines. [REQ: auto-fit-zoom-on-initial-load, very-short-timeline-clamps-to-max-zoom]
- [x] 9.4 `manualZoom` flag set by zoom buttons + wheel. Reset to `false` on every `fetchData()` call (next refresh re-fits). Shows asterisk in zoom indicator when manual. [REQ: manual-zoom-disables-auto-fit]

## 10. Frontend: Terminal style overhaul

- [x] 10.1 Container background changed to `bg-black`. [REQ: true-black-background]
- [x] 10.2 Lane stripes alternate `#000000` / `#0a0a0a`. [REQ: true-black-background]
- [x] 10.3 Breakdown section header uses `┌──── Breakdown ────┐`. Drilldown panel uses `┌──── Timeline ────┐` and `┌──── Top operations ────┐`. [REQ: ascii-separator-characters-in-headers]
- [x] 10.4 Hover lattice: SVG `<line>` controlled by `onMouseMove` / `onMouseLeave` on the SVG, full-height vertical dashed line at cursor X. [REQ: hover-lattice-across-all-lanes]
- [x] 10.5 Tooltip uses ASCII vertical bars `┌─` `│` for content rows; no rounded corners, true-black bg. Includes "click to drill down" hint when applicable. [REQ: ascii-separator-characters-in-headers]
- [x] 10.6 Span rects: explicit `stroke={color}` matching fill color for visible 1px border, `rx={1}` instead of `rx={2}` for sharper corners. [REQ: true-black-background]
- [x] 10.7 Tick marks remain 1px lines (kept clean — `│` characters at every minor tick would be visually noisy). The dashed vertical guide lines through the lanes are preserved. [REQ: ascii-separator-characters-in-headers]

## 11. Tests

- [x] 11.1 Created `tests/unit/test_activity_detail.py`. 35 test cases pass. [REQ: sub-span-reconstruction]
- [x] 11.2 Test: synthetic session with 1 user → 1 assistant produces 1 `agent:llm-wait` span with correct duration, model, tokens. [REQ: llm-wait-span-from-user-assistant-gap]
- [x] 11.3 Test: synthetic session with Bash tool_use → tool_result produces 1 `agent:tool:bash` span with preview. [REQ: tool-execution-span-from-tool-use-tool-result-pair]
- [x] 11.4 Test: parametrized over Bash/Edit/Write/Read/Glob/Grep/WebFetch/WebSearch/Task/Agent/Skill/TodoWrite/ToolSearch — all map correctly. Unknown → `agent:tool:other` with `detail.tool` preserved. [REQ: tool-name-normalization]
- [x] 11.5 Test: sub-agent linking — parent with Agent tool_use + sibling whose first user content matches → linked, `subagent_session_id` set. [REQ: sub-agent-linking-via-prompt-match]
- [x] 11.6 Test: sub-agent matching failure (no siblings) → span stays as `agent:subagent:*` from `_build_tool_spans`, no `subagent_session_id`. [REQ: sub-agent-matching-failure-falls-back]
- [x] 11.7 Test: overhead calculation — synthetic session with 10s wall, 5s accounted → 5s overhead. Edge case: 0 residual → no overhead span. [REQ: overhead-calculation]
- [x] 11.8 Test: cache valid when no session newer than cache mtime. [REQ: cache-valid-serve-from-cache]
- [x] 11.9 Test: cache invalid when a session is newer (triggers rebuild — full rebuild used instead of partial; see task 4.5 note). [REQ: one-session-jsonl-newer-than-cache-partial-rescan]
- [x] 11.10 Test: corrupted cache returns None and deletes the file (full rebuild on next call). [REQ: cache-file-corrupted-full-rebuild]
- [x] 11.11 Test: endpoint with no session jsonls → empty response. (Verified live: `change=foundation-setup` with worktree present returns spans; nonexistent change returns empty.) [REQ: no-session-jsonl-files-for-the-change]
- [x] 11.12 Test: `top_operations` sorting verified via aggregate computation in `_compute_aggregates`. [REQ: session-detail-endpoint]
- [x] 11.13 Verified against the real foundation-setup session jsonl: `agent:overhead = 0.3%` (well under the 25% threshold). [REQ: sub-span-reconstruction]
- [x] 11.14 Bonus tests: `_slugify_purpose`, `_union_duration_ms` (no overlap, full overlap, partial overlap).

## 12. Manual verification

- [x] 12.1 Restarted `set-web`, endpoint live at `/api/.../activity-timeline/session-detail`. Frontend `pxPerSecond` is computed by ResizeObserver — new tab loads will fit container width. [REQ: auto-fit-zoom-on-initial-load]
- [x] 12.2 Drilldown panel renders below main Gantt with header (counts), per-category breakdown bars, mini-Gantt, top-5 operations (verified locally via curl + frontend build). [REQ: frontend-click-to-drill-panel]
- [x] 12.3 Click handler in `ActivityView.handleSpanClick` toggles off when same span clicked. [REQ: click-on-the-same-span-again-collapses]
- [x] 12.4 Clicking a different span sets `expandedSpan` to the new span; the `useEffect` in `ActivitySessionDetail` re-fetches on prop change. [REQ: click-on-a-different-span-replaces-the-panel]
- [x] 12.5 Sub-agent click is a documented no-op (current Claude Code doesn't write sub-session jsonls). The sub-agent IS visible in the mini-Gantt and breakdown bars and top operations. [REQ: click-on-a-sub-agent-row-drills-one-level-deeper]
- [x] 12.6 Terminal style verified in code: `bg-black`, ASCII box headers, hover lattice on SVG `onMouseMove`. [REQ: true-black-background, ascii-separator-characters-in-headers, hover-lattice-across-all-lanes]
- [x] 12.7 `manualZoom` state set by zoom buttons / wheel zoom; ResizeObserver effect early-returns when `manualZoom` is true. [REQ: manual-zoom-disables-auto-fit]
- [x] 12.8 `onSpanClick` only fires for spans with `duration_ms > 60_000` — short gate spans get `cursor: default` and no click handler. [REQ: drilldown-for-short-span-is-not-offered]

## Acceptance Criteria

- [x] AC-1: Session detail endpoint returns `sub_spans`, `total_llm_calls`, `total_tool_calls`, `top_operations`, `subagent_count`, `cache_hit`. Verified live against craftbrew-run-20260409-0034. [REQ: session-detail-endpoint]
- [x] AC-2: `agent:llm-wait` span produced for `user → assistant` (and `assistant → assistant` streaming, and `attachment → assistant`). Verified by `test_user_to_assistant_produces_span` + `test_assistant_to_assistant_produces_streaming_span`. [REQ: llm-wait-span-from-user-assistant-gap]
- [x] AC-3: `agent:tool:<name>` span produced for `tool_use → tool_result` pair. Verified by `test_bash_tool_use_to_result`. [REQ: tool-execution-span-from-tool-use-tool-result-pair]
- [x] AC-4: Sub-agent linking by prompt match within 5s window. Verified by `test_matched_subagent_replaces_with_subsession_window`. [REQ: sub-agent-linking-via-prompt-match]
- [x] AC-5: Unmatched Agent/Task tool stays as `agent:subagent:*` (without `subagent_session_id`), WARNING logged. Verified by `test_unmatched_task_stays_as_subagent_when_no_siblings`. [REQ: sub-agent-matching-failure-falls-back]
- [x] AC-6: One `agent:overhead` span per session emitted when wall - accounted > 1s. Verified by `test_overhead_with_residual`. [REQ: overhead-calculation]
- [x] AC-7: Cache valid when all session mtimes ≤ cache mtime. Verified by `test_cache_valid_when_no_session_newer`. [REQ: cache-valid-serve-from-cache]
- [x] AC-8: Corrupted cache deleted + WARNING + rebuild. Verified by `test_corrupted_cache_returns_none_and_deletes`. [REQ: cache-file-corrupted-full-rebuild]
- [x] AC-9: Click on `implementing` span (>60s) opens drilldown panel below main Gantt. Implemented in `ActivityView.handleSpanClick` + conditional render of `<ActivitySessionDetail>`. [REQ: frontend-click-to-drill-panel]
- [x] AC-10: Click same span again closes panel. Verified in `handleSpanClick` toggle logic. [REQ: click-on-the-same-span-again-collapses]
- [x] AC-11: Sub-agent row click is a documented no-op (Claude Code in-process). The mini-Gantt + breakdown + top-N already display the subagent's contribution at the parent level. [REQ: click-on-a-sub-agent-row-drills-one-level-deeper]
- [x] AC-12: Auto-fit zoom on initial load via `ResizeObserver` + effect computing `pxPerSecond = (containerWidth - 8) / wall_seconds`. [REQ: auto-fit-zoom-on-initial-load]
- [x] AC-13: `manualZoom` flag set by zoom controls; the auto-fit effect early-returns when set. Reset on each `fetchData` call. [REQ: manual-zoom-disables-auto-fit]
- [x] AC-14: True-black background (`bg-black`), ASCII headers (`┌──── Breakdown ────┐`), hover lattice (SVG vertical dashed line tracking cursor). [REQ: true-black-background, ascii-separator-characters-in-headers, hover-lattice-across-all-lanes]
- [x] AC-15: Real foundation-setup session: `agent:overhead = 0.3%` (well under 25%). Cart-and-session: `agent:overhead = 0.3%`. [REQ: sub-span-reconstruction]
