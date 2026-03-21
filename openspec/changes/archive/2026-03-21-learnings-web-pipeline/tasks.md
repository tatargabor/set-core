# Tasks: learnings-web-pipeline

## 1. Backend — Feedback Loop Fixes

- [x] 1.1 In `build_claude_prompt()` (loop_prompt.py:23): call `get_previous_iteration_summary(wt_path)` (already defined at line 202) and when non-empty, inject the result as a "Previous iteration learned:\n{content}" section after `prev_text` and before the reflection instruction [REQ: reflection-injected-into-subsequent-iteration-prompt]
- [x] 1.2 ALREADY IMPLEMENTED in bash loop engine (lib/loop/engine.sh:396-464): reflection.md is read, filtered for trivial content, deduped via semantic recall, and saved via `set-memory remember --type Learning --tags "change:...,source:agent,reflection"`. No Python reimplementation needed. [REQ: reflection-saved-to-persistent-memory]
- [x] 1.3 Add `change_name` and `findings_path` parameters to `_build_unified_retry_context()` (verifier.py:411). When `findings_path` is provided and the JSONL file exists, read entries matching `change_name`, extract the latest attempt's issues, and append a "### Prior Review Findings" section listing each finding with severity, file, and summary. Update all callers (lines 1942, 1978, and review retry at ~line 2160) to pass the new parameters where available [REQ: review-findings-jsonl-included-in-retry-context]
- [x] 1.4 Create `_persist_run_learnings(state_file)` helper in engine.py: import `orch_remember` from `orch_memory`, load state, call `orch_gate_stats(state)` and when result is non-empty format a summary string and call `orch_remember(summary, mem_type="Context", tags="source:orchestrator,type:gate-stats")`. Call this helper from each terminal state site alongside `_generate_review_findings_summary_safe()` (lines 345, 875, 894, 918, 946, 960) [REQ: gate-stats-persisted-to-memory-at-run-end]
- [x] 1.5 In the same `_persist_run_learnings()` helper: read `review-findings.jsonl` from `wt/orchestration/` dir (path: `os.path.join(os.path.dirname(state_file), "wt", "orchestration", "review-findings.jsonl")`), extract recurring patterns (summaries appearing in 2+ changes), and when found call `orch_remember(patterns, mem_type="Learning", tags="source:orchestrator,type:review-patterns")` [REQ: review-patterns-persisted-to-memory-at-run-end]
- [x] 1.6 In merger.py `_try_merge()` or equivalent merge conflict handler: when `_compute_conflict_fingerprint()` returns a new fingerprint not seen in this run, call `orch_remember()` with the conflicting file list and change name, type "Learning", tags "source:orchestrator,type:merge-conflict". Track seen fingerprints in a module-level set to avoid duplicates within a run [REQ: merge-conflict-info-persisted-to-memory]

## 2. Backend — API Endpoints

- [x] 2.1 Add `GET /api/{project}/review-findings` endpoint in api.py: resolve findings file at `_resolve_project(project) / "wt" / "orchestration" / "review-findings.jsonl"` (with fallback to `_resolve_project(project) / "orchestration" / "review-findings.jsonl"`), parse JSONL entries, extract recurring patterns (normalize summary[:50], count ≥2), read summary MD if exists, return `{ entries, summary, recurring_patterns }` [REQ: review-findings-api-endpoint]
- [x] 2.2 Add `GET /api/{project}/gate-stats` endpoint in api.py: resolve state file via `_resolve_project()` + read state JSON directly (same pattern as existing endpoints), iterate `state["changes"]`, for each gate (build, test, review, smoke — these are the Change dataclass fields: `build_result`, `test_result`, `review_result`, `smoke_result` with timing `gate_build_ms`, `gate_test_ms`, `gate_review_ms`, `gate_verify_ms`) aggregate total/pass/fail/skip/pass_rate/avg_ms, compute retry_summary from `verify_retry_count`/`redispatch_count`, group by `change_type` field for per_change_type breakdown. Note: e2e results are stored in extras as `e2e_result`/`e2e_output` only when e2e gate runs — check extras dict as fallback [REQ: gate-stats-aggregation-endpoint]
- [x] 2.3 Add `GET /api/{project}/reflections` endpoint in api.py: reuse existing worktree listing logic (same as `/api/{project}/worktrees`), for each worktree with `has_reflection`, read `.claude/reflection.md`, map branch to change name by stripping `set/` prefix, return `{ reflections: [{change, branch, content}], total, with_reflection }` [REQ: reflections-aggregation-endpoint]
- [x] 2.4 Add `GET /api/{project}/changes/{name}/timeline` endpoint in api.py: read `orchestration-state-events.jsonl` (path pattern from existing events endpoint at line 1548: try `project_path / "orchestration-state-events.jsonl"` then `project_path / "wt" / "orchestration" / "orchestration-state-events.jsonl"`), also glob for archived files `orchestration-state-events-*.jsonl` in same directory and read those too (last 3 kept by rotation policy). Filter all entries for `type=="STATE_CHANGE"` and `change==name`, sort by `ts`, compute `duration_ms` from first to last. For gate results per attempt: look up the change in state JSON and extract `build_result`, `test_result`, `review_result`, `smoke_result` and `verify_retry_count` to construct current gate snapshot (note: only current attempt results are in state, not per-attempt history — document this limitation) [REQ: per-change-timeline-api-from-events]
- [x] 2.5 Add `GET /api/{project}/learnings` unified endpoint in api.py: internally call the review-findings, gate-stats, reflections logic (as helper functions, not HTTP calls) and include sentinel findings from existing `_sentinel_dir(pp) / "findings.json"`, return `{ reflections, review_findings, gate_stats, sentinel_findings }` [REQ: unified-learnings-endpoint]
- [x] 2.6 Extend `orch_gate_stats()` in orch_memory.py to include `per_gate` breakdown: for each gate name, track pass/fail/skip counts and timing from Change dataclass fields (`build_result`, `test_result`, `review_result`, `smoke_result` with timing `gate_build_ms`, `gate_test_ms`, `gate_review_ms`, `gate_verify_ms`) and extras dict fallback for `e2e_result`/`e2e_output`. Also add `per_change_type` grouping by `change.get("change_type", "unknown")`. Pass rate = pass_count / (pass_count + fail_count), skipped gates excluded from rate [REQ: gate-stats-aggregation-endpoint]

## 3. Frontend — API Client

- [x] 3.1 Add TypeScript types for learnings data: `LearningsData`, `ReviewFindingsData`, `GateStatsData`, `ReflectionsData`, `ChangeTimelineData` in api.ts [REQ: learnings-tab-in-dashboard]
- [x] 3.2 Add fetch functions: `getLearnings()`, `getReviewFindings()`, `getGateStats()`, `getReflections()`, `getChangeTimeline()` in api.ts [REQ: learnings-tab-in-dashboard]

## 4. Frontend — LearningsPanel Component

- [x] 4.1 Create `LearningsPanel.tsx` with section selector (All / Reflections / Review / Gates / Sentinel) and data fetching via `getLearnings()` [REQ: learnings-tab-in-dashboard]
- [x] 4.2 Implement Agent Reflections section: expandable rows with change name, iteration info, truncated preview collapsed, full markdown content expanded [REQ: agent-reflections-section]
- [x] 4.3 Implement Review Findings section: recurring patterns banner at top, expandable finding rows with severity badge (color-coded CRITICAL/HIGH/MEDIUM), change name, file/line/fix on expand [REQ: review-findings-section]
- [x] 4.4 Implement Gate Performance section: table with gate name, pass rate (percentage + fraction), avg duration, retry count; summary line with total retry cost [REQ: gate-performance-section]
- [x] 4.5 Implement Gate Performance per-change breakdown: expandable row showing each change with pass/fail icons per gate and retry count [REQ: gate-performance-section]
- [x] 4.6 Implement Sentinel Findings section: severity badge, change name, summary, status — using existing sentinel findings data format [REQ: sentinel-findings-section]

## 5. Frontend — Dashboard Integration

- [x] 5.1 Add 'learnings' to PanelTab union type (line 22), to the URL-backed tab validation array in useState (line 39: `['changes','phases',...,'battle','learnings']`), and to the tabs array (line 138-150) in Dashboard.tsx — always visible, not conditionally hidden [REQ: learnings-tab-in-dashboard]
- [x] 5.2 Render LearningsPanel when activeTab === 'learnings' in Dashboard.tsx [REQ: learnings-tab-in-dashboard]

## 6. Frontend — Change Timeline Detail

- [x] 6.1 Create `ChangeTimelineDetail.tsx`: horizontal flow diagram showing state transitions as nodes with timestamps, gate results at verify nodes, failed transitions highlighted in red [REQ: per-change-timeline-detail-view]
- [x] 6.2 Add summary line to timeline view: total duration, retry count, gate run count [REQ: per-change-timeline-detail-view]
- [x] 6.3 Integrate timeline detail into Changes tab: when a change is selected, show timeline sub-view option alongside existing gate detail [REQ: per-change-timeline-detail-view]

## 7. Frontend — Worktrees Reflection Preview

- [x] 7.1 In Worktrees.tsx: for worktrees with `has_reflection: true`, fetch and display truncated first line of reflection content below branch info [REQ: reflection-preview-in-worktrees]

## Acceptance Criteria (from spec scenarios)

- [x] AC-1: WHEN `build_claude_prompt()` is called AND `get_previous_iteration_summary(wt_path)` returns non-empty THEN prompt includes "Previous iteration learned:" section [REQ: reflection-injected-into-subsequent-iteration-prompt, scenario: previous-reflection-exists]
- [x] AC-2: WHEN iteration completes with meaningful reflection THEN orch_remember() saves it with change name tag [REQ: reflection-saved-to-persistent-memory, scenario: meaningful-reflection]
- [x] AC-3: WHEN reflection is trivial (<50 chars or "No notable issues") THEN orch_remember() is NOT called [REQ: reflection-saved-to-persistent-memory, scenario: trivial-reflection]
- [x] AC-4: WHEN `_build_unified_retry_context()` called with `change_name` and `findings_path` AND JSONL has matching entries THEN retry prompt includes "### Prior Review Findings" section [REQ: review-findings-jsonl-included-in-retry-context, scenario: prior-review-findings-exist-for-change]
- [x] AC-5: WHEN run ends with gate data THEN gate stats summary saved to memory [REQ: gate-stats-persisted-to-memory-at-run-end, scenario: run-completes-with-gate-data]
- [x] AC-6: WHEN run ends with recurring review patterns THEN patterns saved to memory [REQ: review-patterns-persisted-to-memory-at-run-end, scenario: recurring-patterns-found]
- [x] AC-7: WHEN merge conflict detected with new fingerprint THEN conflict info saved to memory [REQ: merge-conflict-info-persisted-to-memory, scenario: merge-conflict-detected]
- [x] AC-8: WHEN requesting /api/{project}/learnings THEN response contains reflections, review_findings, gate_stats, sentinel_findings sections [REQ: unified-learnings-endpoint, scenario: all-sources-available]
- [x] AC-9: WHEN requesting /api/{project}/changes/{name}/timeline THEN response contains sorted transitions from orchestration-state-events.jsonl [REQ: per-change-timeline-api-from-events, scenario: events-exist-for-change]
- [x] AC-10: WHEN Learnings tab selected THEN LearningsPanel renders with all four sections [REQ: learnings-tab-in-dashboard, scenario: tab-content]
- [x] AC-11: WHEN user expands a reflection row THEN full markdown content shown [REQ: agent-reflections-section, scenario: expanded-reflection]
- [x] AC-12: WHEN user navigates to detailed timeline for a change THEN horizontal flow with state transitions, timestamps, gate results at verify nodes is shown [REQ: per-change-timeline-detail-view, scenario: timeline-rendering]
