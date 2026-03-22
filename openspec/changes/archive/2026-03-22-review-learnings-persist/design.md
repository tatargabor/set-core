# Design: review-learnings-persist

## Architecture Decisions

### D1: Per-merge persistence, not per-run

**Decision**: Call `_persist_change_review_learnings()` in the engine's post-merge hook (after each successful change merge), not at run end.

**Rationale**: Runs get interrupted, crashed, or restarted. If we only persist at run end, a 6-change run that crashes after 4 merges loses all learnings. Per-merge ensures incremental accumulation.

**Hook point**: `engine.py` — after `_try_merge()` succeeds and status is set to `merged`, call persist. This is the same location where `post_merge_hooks()` is already called.

### D2: Two-layer storage — template vs project

**Decision**: Findings are classified into two scopes and stored separately:

1. **Template-level** — generic framework/security patterns (e.g., "no auth middleware", "XSS via dangerouslySetInnerHTML", "missing html lang attribute"). Stored in `~/.config/set-core/review-learnings/<profile-name>.jsonl`. Shared across ALL projects of the same type on this machine. Periodically promoted to `modules/web/review_baseline.md` by set-core developers.

2. **Project-level** — business logic and domain-specific patterns (e.g., "Budapest postal code use string prefix not regex", "seed admin email must be unique per test run"). Stored in `<project>/wt/orchestration/review-learnings.jsonl` and committed to main branch after each merge.

**Rationale**: Template patterns apply to all web projects universally. Project patterns are meaningless outside their project. Mixing them pollutes the checklist.

### D3: LLM classification (Sonnet), not regex

**Decision**: Use a single Sonnet call to classify extracted patterns into `template` or `project` scope. No regex or keyword matching.

**Prompt**:
```
Classify each review finding as "template" (generic framework/security pattern
applicable to any {project_type} project) or "project" (business logic,
domain-specific, or app-specific pattern).

Project type: {profile_name}

Findings:
{json array of patterns}

Return JSON array: [{"pattern": "...", "scope": "template|project"}]
```

**Rationale**: Regex/keyword clusters (`REVIEW_PATTERN_CLUSTERS`) are brittle and need constant expansion. Sonnet is fast (~2s), cheap (~$0.003), and handles edge cases that regex cannot (e.g., distinguishing "missing auth on API route" (template) from "admin user seed password must be hashed" (project)). One call per merge, batch all patterns.

**Fallback**: If Sonnet call fails (timeout, API error), default all patterns to `project` scope (safe — no template pollution).

### D4: Static baseline + dynamic template + dynamic project = checklist

**Decision**: The checklist combines three sources:
1. **Static baseline** — hand-curated, ships with profile (e.g., `modules/web/set_project_web/review_baseline.md`) → `[baseline]` tag
2. **Dynamic template** — from `~/.config/set-core/review-learnings/web.jsonl` → `[template, seen Nx]` tag
3. **Dynamic project** — from `<project>/wt/orchestration/review-learnings.jsonl` → `[project, seen Nx]` tag

**Merge order**: project (highest priority, most specific) → template → baseline. Deduplicate by normalized pattern. Cap at 15 lines total.

### D5: JSONL entry format (shared for both layers)

```json
{
  "pattern": "normalized summary text",
  "severity": "CRITICAL",
  "scope": "template|project",
  "count": 3,
  "last_seen": "2026-03-22T10:00:00Z",
  "source_changes": ["auth-user-accounts", "cart-checkout"],
  "fix_hint": "Add auth middleware check"
}
```

### D6: Template JSONL concurrency — flock

**Decision**: Template JSONL at `~/.config/` can be written by multiple projects running simultaneously. Use `fcntl.flock(LOCK_EX)` for atomic read-modify-write.

```python
with open(path, "r+") as f:
    fcntl.flock(f, fcntl.LOCK_EX)
    existing = [json.loads(l) for l in f if l.strip()]
    # merge new patterns, dedup, cap
    f.seek(0); f.truncate()
    for entry in merged:
        f.write(json.dumps(entry) + "\n")
    # flock auto-releases on close
```

Project JSONL has no concurrency issue — merge queue is sequential.

### D7: Project JSONL auto-commit to main

**Decision**: After persisting project-level learnings, auto-commit to main:
```
git add wt/orchestration/review-learnings.jsonl
git commit -m "chore: update review learnings [skip ci]"
```

This happens inside `_try_merge()` after the change branch is merged, while still on main. The learnings file travels with the project repo.

### D8: Decay and cap

**Decision**: Cap at 50 entries per JSONL (both template and project). When adding beyond 50, remove oldest by `last_seen`.

**Rationale**: Prevents unbounded growth. Old patterns that no longer appear are likely fixed in templates or rules.

### D9: set-web UI — findings display

**Decision**: The review findings summary (visible in set-web) shows source provenance:

| Column | Values | Description |
|--------|--------|-------------|
| Source | `set-core` / `.local` / `project` | Where the finding originates |
| Scope | `template` / `project` | Classification |
| Pattern | text | Normalized finding |
| Count | N | Times seen |
| Last Seen | date | Most recent occurrence |

**Source meanings**:
- `set-core` — from `modules/web/review_baseline.md` (shipped with set-core)
- `.local` — from `~/.config/set-core/review-learnings/web.jsonl` (accumulated on this machine)
- `project` — from `<project>/wt/orchestration/review-learnings.jsonl` (project repo)

### D10: Promotion flow (set-core development)

Template learnings in `.local` are periodically reviewed by set-core developers and promoted:

```
~/.config/set-core/review-learnings/web.jsonl  (accumulated from runs)
    │
    └── set-core dev reviews, picks generic patterns
        │
        └── adds to modules/web/set_project_web/review_baseline.md
            │
            └── commit + release
                │
                └── set-project init → deploys to consumer projects
```

This is a manual, deliberate process — not automated. Not every template pattern deserves baseline status.

## Data Flow

```
Change merge (engine.py)
    │
    ├── read review-findings.jsonl for this change
    ├── extract CRITICAL/HIGH patterns
    ├── normalize
    │
    ├── Sonnet classify: template vs project (1 batch call)
    │   fallback: all → project if Sonnet fails
    │
    ├── template patterns:
    │   └── flock → ~/.config/set-core/review-learnings/web.jsonl
    │       (dedup, increment count, cap at 50)
    │
    ├── project patterns:
    │   └── <project>/wt/orchestration/review-learnings.jsonl
    │       (append, dedup, cap at 50)
    │   └── git add + commit "chore: update review learnings [skip ci]"
    │
    └── (existing) profile.post_merge_hooks()

Next dispatch (dispatcher.py)
    │
    ├── (existing) _build_review_learnings() → cross-change within-run
    ├── (new) profile.review_learnings_checklist(project_path)
    │       │
    │       ├── read modules/web/.../review_baseline.md        → [baseline]
    │       ├── read ~/.config/.../web.jsonl                   → [template, seen Nx]
    │       ├── read <project>/.../review-learnings.jsonl      → [project, seen Nx]
    │       └── merge, dedup, sort by priority, cap at 15 lines
    │
    └── inject both into input.md
```

### D13: Unified LLM call logging via `run_claude_logged()` wrapper

**Decision**: Create a thin wrapper `run_claude_logged()` in `subprocess_utils.py` that:
1. Calls `run_claude()` with all passed arguments
2. Emits `LLM_CALL` event to `event_bus` with purpose, model, duration, etc.
3. Returns the same `ClaudeResult`

**Rationale**: Currently 13+ `run_claude()` call sites across 7 files. None emit events. The set-web UI can't show what LLM calls happened, when, or for which change. Adding event emission per-call-site is error-prone and diverges over time. A wrapper ensures all calls are logged uniformly.

**Migration**: All existing `run_claude()` calls are replaced with `run_claude_logged()`. The `purpose` parameter is mandatory — it identifies the call's role. The `change` parameter is optional — populated when the call is change-scoped.

**Event data**:
```json
{
  "purpose": "review",
  "model": "sonnet",
  "duration_ms": 42000,
  "output_size": 3500,
  "exit_code": 0,
  "timed_out": false
}
```

**set-web integration**: The changes tab timeline already reads from `orchestration-events.jsonl`. Adding `LLM_CALL` to the event stream means the UI picks it up automatically. A new "LLM Calls" panel at the bottom of the changes tab shows a chronological log filterable by purpose.

## Migration Plan: Seed from Existing Runs

### D11: Backfill template learnings from past E2E runs

Existing runs (craftbrew-run7, run8, run9) have `review-findings.jsonl` files with real findings. A one-time migration script processes these to seed the template JSONL.

**Script**: `scripts/migrate-review-learnings.py`

```
Usage: python scripts/migrate-review-learnings.py [--runs-dir ~/.local/share/set-core/e2e-runs]

Flow:
  1. Scan all */orchestration/review-findings.jsonl under runs-dir
  2. Extract CRITICAL/HIGH patterns from all entries
  3. Batch classify via Sonnet (template vs project)
  4. Template patterns → ~/.config/set-core/review-learnings/web.jsonl
     (dedup, aggregate counts across runs)
  5. Print summary: N template patterns, M project patterns, K deduplicated
```

**Why migration matters**: Without seeding, the first run after implementation starts with an empty template JSONL. The craftbrew runs have 20+ real findings that are immediately useful. Migration gives us a "warm start."

**What about project patterns from migration?** These are NOT written to any project's repo — they're discarded during migration. Only template patterns get seeded. Project patterns only accumulate during live runs going forward.

### D12: Ongoing promotion workflow

After the migration script runs, set-core developers review `~/.config/set-core/review-learnings/web.jsonl` and promote the strongest patterns to `modules/web/review_baseline.md`. This is the same flow as D10 but with initial data.

```
craftbrew-run7/review-findings.jsonl ─┐
craftbrew-run8/review-findings.jsonl ─┤ migrate script
craftbrew-run9/review-findings.jsonl ─┘     │
                                            ▼
                            ~/.config/.../web.jsonl (seeded)
                                            │
                                    dev reviews & picks
                                            │
                                            ▼
                        modules/web/.../review_baseline.md
```

## Files Modified

| File | Change |
|------|--------|
| `lib/set_orch/profile_types.py` | +`persist_review_learnings(patterns, project_path)`, +`review_learnings_checklist(project_path)`, +`_classify_patterns(patterns)`, +`_learnings_storage_path()` |
| `lib/set_orch/engine.py` | +`_extract_change_review_patterns()`, +`_persist_change_review_learnings()` after merge |
| `lib/set_orch/dispatcher.py` | Inject `profile.review_learnings_checklist(project_path)` into input.md |
| `modules/web/set_project_web/project_type.py` | Override `review_learnings_checklist()` with baseline merge |
| `modules/web/set_project_web/review_baseline.md` | Static web security checklist |
| `tests/unit/test_review_learnings.py` | Unit tests for classify, persist, checklist |
