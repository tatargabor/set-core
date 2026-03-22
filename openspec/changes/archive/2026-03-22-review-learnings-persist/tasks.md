# Tasks: review-learnings-persist

## Core ABC + Storage

- [x] T1: Add `persist_review_learnings(patterns: list[dict], project_path: str) -> None` to `ProjectType` ABC in `profile_types.py` — default impl classifies via Sonnet, writes template patterns to `~/.config/set-core/review-learnings/{profile_name}.jsonl` (with flock), writes project patterns to `{project_path}/wt/orchestration/review-learnings.jsonl`
- [x] T2: Add `review_learnings_checklist(project_path: str) -> str` to `ProjectType` ABC in `profile_types.py` — reads 3 sources (baseline + template JSONL + project JSONL), merges with dedup, returns markdown (max 15 lines)
- [x] T3: Add `_learnings_template_path() -> Path` helper — returns `~/.config/set-core/review-learnings/{profile_name}.jsonl`, creates dir if needed
- [x] T4: Add `_classify_patterns(patterns: list[dict]) -> list[dict]` — single Sonnet call, classifies each pattern as `template` or `project`. Fallback: all `project` if Sonnet fails.

## Engine Integration

- [x] T5: Add `_extract_change_review_patterns(findings_path: str, change_name: str) -> list[dict]` in `merger.py` — reads JSONL, filters to given change's CRITICAL/HIGH issues, normalizes, returns pattern dicts
- [x] T6: Add `_persist_change_review_learnings()` in `merger.py` — calls T5 then `profile.persist_review_learnings()`. Called after successful merge, same location as `post_merge_hooks()`.
- [x] T7: Project-level JSONL auto-commit — after writing project patterns, `git add wt/orchestration/review-learnings.jsonl && git commit -m "chore: update review learnings [skip ci]"` on main

## Dispatcher Integration

- [x] T8: Call `profile.review_learnings_checklist(project_path)` in `_build_input_content()` in `dispatcher.py` — inject as `## Review Learnings Checklist` section after existing `## Lessons from Prior Changes`

## Web Module

- [x] T9: Create `modules/web/set_project_web/review_baseline.md` — static checklist: no `as any`, auth middleware on /api/*, no user-controlled regex, bcrypt not sha256, rate limiting on auth, CSRF protection, proper TypeScript NextAuth types, html lang attribute
- [x] T10: Override `_review_baseline_items()` in `WebProjectType` — reads baseline.md, parent class `review_learnings_checklist()` handles merge + tagging

## Migration

- [ ] T11: Create `scripts/migrate-review-learnings.py` — scan existing E2E run dirs (`~/.local/share/set-core/e2e-runs/*/orchestration/review-findings.jsonl`), extract patterns, batch Sonnet classify, write template patterns to `~/.config/set-core/review-learnings/web.jsonl`
- [ ] T12: Run migration on craftbrew-run7/run8/run9 findings, verify seeded JSONL content

## Template JSONL concurrency

- [x] T13: Implement `flock`-based atomic read-modify-write for `~/.config/set-core/review-learnings/*.jsonl` — prevents corruption when multiple projects persist simultaneously

## Promotion Skill

- [ ] T19: Create `.claude/skills/set/findings-promote/SKILL.md` — interactive skill that reads template JSONL, shows each pattern, asks promote/edit/skip, appends to `modules/<type>/review_baseline.md`
- [ ] T20: Add `reviewed: true` field to JSONL entries — skip already-reviewed items in promote flow unless `--all` flag

## LLM Call Logging

- [x] T21: Create `run_claude_logged()` wrapper in `subprocess_utils.py` — calls `run_claude()`, then emits `LLM_CALL` event via `event_bus.emit("LLM_CALL", change=change, data={"purpose", "model", "duration_ms", "output_size", "exit_code", "timed_out"})`
- [x] T22: Migrate `verifier.py` calls — review (line 1259/1264), smoke_fix (line 1530), spec_verify (line 2244) → `run_claude_logged()` with `change=change_name`
- [x] T23: Migrate `builder.py:156` → `run_claude_logged(purpose="build_fix")`
- [x] T24: Migrate `engine.py:1161` → `run_claude_logged(purpose="replan")`
- [x] T25: Migrate `planner.py` calls (lines 148, 1417, 1465, 1557, 1793, 1812) → `run_claude_logged(purpose="decompose_summary|decompose_domain|decompose_merge|decompose")`
- [x] T26: Migrate `digest.py:231` → `run_claude_logged(purpose="digest")`
- [x] T27: Migrate `auditor.py:217` → `run_claude_logged(purpose="audit")`
- [x] T28: New Sonnet classification call (T4) uses `run_claude_logged(purpose="classify", change=change_name)`

## Session Label

- [x] T32: `run_claude_logged()` prepends `[PURPOSE:{purpose}:{change}]` header line to the prompt — persisted in the session JSONL `queue-operation` entry where `_derive_session_label()` can parse it
- [x] T33: Update `_derive_session_label()` in `api.py` — parse `[PURPOSE:purpose:change]` format; add purpose-to-label mapping (review→"Review", smoke_fix→"Smoke Fix", classify→"Classify", etc.)
- [x] T34: Ensure `run_claude_logged()` passes purpose context so sessions are identifiable — no more generic "Task" labels

## set-web LLM Call Display

- [ ] T29: Add `LLM_CALL` events to changes tab timeline — show purpose, model, duration badge
- [ ] T30: Add LLM call log panel at bottom of changes tab — chronological list of all LLM calls for selected change + global calls in "System" section
- [ ] T31: Filter UI — toggle by purpose (review, classify, replan, etc.)

## Tests

- [x] T14: Unit test `_classify_patterns()` — mock Sonnet response, verify template/project split, verify fallback on API error
- [x] T15: Unit test `persist_review_learnings()` — writes to both JSONLs, deduplicates, increments count, caps at 50
- [x] T16: Unit test `review_learnings_checklist()` — formats output, respects 15-line cap, merges 3 sources with correct tags
- [x] T17: Unit test `_extract_change_review_patterns()` — filters correct change, normalizes, handles missing file
- [x] T18: Integration test: persist → checklist round-trip — persist patterns, call checklist, verify output contains persisted items with correct scope tags

## Acceptance Criteria

- AC1: First change of a fresh run gets a non-empty checklist (from baseline + prior run template learnings)
- AC2: After a change with CRITICAL review findings merges, Sonnet classifies them and the next dispatched change's input.md contains the relevant patterns
- AC3: Template patterns from craftbrew appear in non-craftbrew web project dispatches; project patterns do NOT
- AC4: Both JSONLs never exceed 50 entries (oldest pruned)
- AC5: Interrupted run preserves learnings accumulated up to that point
- AC6: Migration script successfully seeds template JSONL from existing run7/8/9 findings
- AC7: set-web UI shows Source (set-core/.local/project) and Scope (template/project) columns in findings view
- AC8: Concurrent project runs don't corrupt template JSONL (flock tested)
- AC9: Every `run_claude()` call in the codebase emits an `LLM_CALL` event to orchestration-events.jsonl
- AC10: set-web changes tab shows LLM calls (purpose, model, duration) in timeline and log panel
- AC11: Global LLM calls (replan, decompose, digest) visible in set-web system/run-level log
