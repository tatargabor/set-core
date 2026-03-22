## review-learnings

Cross-run review findings persistence with two-layer storage (template vs project), LLM-based classification, and dispatch-time checklist injection.

### Requirements

#### RL-PERSIST — Persist review learnings after each change merge
- After a change merges successfully, extract CRITICAL/HIGH patterns from `review-findings.jsonl`
- Normalize patterns: strip severity tags, first 60 chars
- Classify via Sonnet into `template` or `project` scope (single batch call)
- Template patterns → `~/.config/set-core/review-learnings/<profile-name>.jsonl` (with flock)
- Project patterns → `<project>/wt/orchestration/review-learnings.jsonl` (committed to main)
- Deduplicate against existing entries by normalized pattern text
- Increment `count` and update `last_seen` for existing patterns
- JSONL entry: `{"pattern", "severity", "scope", "count", "last_seen", "source_changes": [], "fix_hint"}`
- Cap at 50 entries per JSONL; when exceeded, remove oldest by `last_seen`

#### RL-CLASSIFY — LLM classification of findings scope
- Single Sonnet call per merge, batch all patterns
- Prompt includes profile name (e.g., "web") for context
- Input: array of `{"pattern", "fix_hint"}` objects
- Output: array of `{"pattern", "scope": "template|project"}`
- Fallback on API error/timeout: classify all as `project` (safe — no template pollution)
- No regex or keyword matching — pure LLM classification

#### RL-CHECKLIST — Profile method returns compact checklist from 3 sources
- `ProjectType.review_learnings_checklist(project_path)` returns markdown (max 15 lines)
- Combines: static baseline (`[baseline]`) + template JSONL (`[template, seen Nx]`) + project JSONL (`[project, seen Nx]`)
- Priority: project > template > baseline (most specific first)
- Deduplicate by normalized pattern text across all 3 sources
- Returns empty string if no learnings and no baseline exist

#### RL-BASELINE — Static web security baseline
- `modules/web/set_project_web/review_baseline.md` contains hand-curated checklist
- Items: auth middleware, type safety (no `as any`), input validation, rate limiting, password hashing, CSRF, html lang
- Read by `WebProjectType.review_learnings_checklist()` as lowest priority source
- Other project types ship their own baseline or return empty

#### RL-INJECT — Dispatch-time checklist injection
- `dispatcher.py` calls `profile.review_learnings_checklist(project_path)` in `_build_input_content()`
- Injected as `## Review Learnings Checklist` section in input.md
- Placed after existing `## Lessons from Prior Changes` (cross-change within-run)
- Both sections coexist: within-run learnings + cross-run persistent checklist

#### RL-SCOPE — Two-layer storage isolation
- Template JSONL: `~/.config/set-core/review-learnings/<profile-name>.jsonl` — shared across projects
- Project JSONL: `<project>/wt/orchestration/review-learnings.jsonl` — committed to main
- Profile name derived from `profile.info.name`; NullProfile uses "core"
- Web template patterns never appear in non-web dispatches
- Template JSONL uses `fcntl.flock(LOCK_EX)` for concurrent access from multiple projects

#### RL-MIGRATE — Seed template learnings from existing runs
- Migration script: `scripts/migrate-review-learnings.py`
- Scans `~/.local/share/set-core/e2e-runs/*/orchestration/review-findings.jsonl`
- Extracts CRITICAL/HIGH, batch classifies via Sonnet, writes template patterns to `.config` JSONL
- Project patterns discarded during migration (only template seeded)
- Aggregates counts across multiple runs for same pattern

#### RL-PROMOTE — Interactive skill to promote template learnings to baseline
- Skill: `/set:findings promote` (or `set:review-promote`)
- Reads `~/.config/set-core/review-learnings/<profile-name>.jsonl`
- Shows each pattern with count, severity, source changes, fix hint
- For each: asks "Promote to baseline? (y/n/edit/skip)"
  - `y` → append to `modules/<type>/review_baseline.md` as-is
  - `edit` → let user edit the wording before appending
  - `n` → skip, mark as "reviewed" in JSONL (don't re-ask next time)
  - `skip` → skip without marking (will re-ask next time)
- After all reviewed: show summary of promoted items
- Commit changes to `review_baseline.md` if any promoted

#### RL-LLM-LOG — Unified LLM call event logging
- New event type `LLM_CALL` emitted for EVERY `run_claude()` invocation across the codebase
- Event data: `{"purpose", "model", "duration_ms", "output_size", "exit_code", "timed_out"}`
- `purpose` values: `review`, `smoke_fix`, `spec_verify`, `classify`, `replan`, `decompose`, `decompose_summary`, `decompose_domain`, `decompose_merge`, `digest`, `audit`, `build_fix`
- `change` field populated when the call is change-scoped (review, smoke_fix, spec_verify, classify); empty for global calls (replan, decompose, digest, audit, build_fix)
- Persists to `orchestration-events.jsonl` — survives sessions, visible across runs
- Wrapper function `run_claude_logged(prompt, *, purpose, change="", **kwargs)` that calls `run_claude()` then emits `LLM_CALL` event
- All existing `run_claude()` call sites migrated to `run_claude_logged()`

#### RL-SESSION-LABEL — Meaningful session labels for LLM calls
- `run_claude_logged()` passes `--session-name` (or equivalent) to encode purpose into the Claude session
- Session name format: `{change_name}:{purpose}` (e.g., `auth-user-accounts:review`, `auth-user-accounts:smoke_fix`, `:replan`, `:decompose`)
- `_derive_session_label()` in `api.py` updated to parse this format → shows purpose instead of "Task"
- For calls without change context, prefix is empty (`:replan` → label "Replan")
- Fallback: if session name not available, existing heuristic applies

#### RL-LLM-UI — LLM call visibility in set-web
- Changes tab timeline includes `LLM_CALL` events with purpose, model, duration
- Changes tab log (bottom panel) shows chronological LLM calls for the selected change
- Global LLM calls (replan, decompose, digest) appear in a "System" section or run-level log
- Each entry shows: timestamp, purpose, model, duration_ms, exit_code
- Filterable by purpose (e.g., show only review calls, or only classification calls)

#### RL-UI — set-web findings display
- Review findings summary shows Source column: `set-core` (baseline) / `.local` (template dynamic) / `project`
- Shows Scope column: `template` / `project`
- Pattern, Count, Last Seen columns as existing
