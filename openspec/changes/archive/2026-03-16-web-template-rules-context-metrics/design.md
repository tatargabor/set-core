## Context

Three orthogonal improvements to reduce per-change agent friction and improve observability.

**Current state:**
- `wt-project-web` templates deploy broken config files (Tailwind v4 PostCSS syntax, wrong Jest key) — every E2E run agent spends 1-3 iterations re-fixing these
- `project-knowledge.yaml` features define `rules_file` per feature, but dispatcher only builds text context from feature `touches` — it never copies rule files to the worktree
- `loop-state.json` tracks `total_tokens`, `total_input_tokens`, `total_cache_create`, `capacity_limit_pct` — rich data for context utilization — but orchestration state and wt-web don't expose it per-change

**Key discovery from codebase inspection:**
- `build_project_knowledge_context()` in `dispatcher.py` (L768) already reads `project-knowledge.yaml` and builds text context from feature names and touches — the `rules_file` field is simply never read
- `dispatch_change()` calls `bootstrap_worktree()` which syncs `.claude/` from the main project — the hook point for rule injection is **after bootstrap**, before `wt-loop` starts
- `loop-state.json` has `capacity_limit_pct` + `total_cache_create` + `total_input_tokens` — context window fill = `total_cache_create` is a proxy, or more precisely `(total_input_tokens + total_cache_create) / context_window_size`
- Context window size is model-dependent (200K for Sonnet/Opus 4.x). The loop already emits `capacity_limit_pct` stop signal — we just need to capture start/end values

## Goals / Non-Goals

**Goals:**
- Templates deploy correct, immediately-working configs (no first-iteration config fix needed)
- Dispatch injects feature-matched rule files into worktree `.claude/rules/` before agent starts
- Per-change context utilization (start + end token count from loop-state) stored in orchestration state
- wt-web change list shows context metrics column

**Non-Goals:**
- Runtime rule injection mid-iteration (rules are injected at dispatch time only)
- Dynamic context window size detection (hardcode 200K for Claude 4.x Sonnet/Opus)
- Rewriting the project-knowledge feature matching logic (reuse existing `build_project_knowledge_context` path-glob logic)
- wt-project-web template corrections for non-Next.js templates (spa template excluded)

## Decisions

### D1: Template corrections are file fixes, not new abstractions

The `postcss.config.mjs`, `jest.config.ts`, `next.config.js` in `wt-project-web/templates/nextjs/` are simply wrong. Fix them directly. No new abstraction needed — `wt-project init` redeploys them. Rules (`data-model.md`, `testing-conventions.md`) get additive paragraphs.

New `worktree-setup.md` rule is path-scoped to `prisma/**` and `src/lib/prisma*` (like `data-model.md`) + `jest.config*` — so it activates specifically when those files are touched.

**Alternative considered:** inject worktree setup as an orchestration directive string — rejected because rules files persist in the worktree and are visible on every turn, while directive strings are only in the initial prompt.

### D2: Rules injection reads `rules_file` from project-knowledge.yaml features

Extend `build_project_knowledge_context()` (or a new `_inject_feature_rules()` called from `dispatch_change()`) to:
1. Load `project-knowledge.yaml`
2. For each feature, glob-match the feature's `touches` paths against the change's `scope` (existing logic)
3. If match: resolve `rules_file` path relative to project `.claude/` and copy to worktree `.claude/rules/`

Injection happens **after `bootstrap_worktree()`** in `dispatch_change()`, so bootstrap doesn't overwrite injected files. Files are namespaced as `rules_file` path's basename — no collision risk since rule files are already namespaced in wt-project-web.

**Alternative considered:** inject rules content into proposal.md — rejected because proposal.md is one-shot context, rules files persist across iterations.

### D3: Context metrics from loop-state at loop completion

Context window utilization = `total_cache_create / 200_000` (200K = Claude 4.x Sonnet/Opus window). This represents "how full was the context at peak".

Monitor already reads `loop-state.json` in `_verify_change_status()` and `_read_loop_state()`. At the moment verifier transitions change to `verifying`, capture:
- `context_tokens_end`: `total_cache_create` from loop-state at completion
- `context_window_size`: 200000 (hardcoded constant, extractable from model name in future)

For `context_tokens_start`: read loop-state after first iteration completes — use `iterations[0].cache_create_tokens`.

Store both as new optional fields on the change state entry.

**Alternative considered:** capture start in dispatch_change before wt-loop launch — loop-state doesn't exist yet, so nothing to read. First-iteration data is the earliest available proxy.

### D4: wt-web displays context metrics inline

Add a `ctx` column to the change list table:
```
ctx: 45K → 180K / 200K  (90%)
```
Format: `start → end / window`. Show only `end / window` if start unavailable. Omit column entirely if no changes have context data (backward compat with old state files).

## Risks / Trade-offs

- **[Risk] Hardcoded 200K window** → Mitigation: add `context_window_size` as a constant in `monitor.py`, comment with "update when Sonnet 5 ships". Model-aware resolution is future work.
- **[Risk] Rules injection path conflict** → Mitigation: only inject if `rules_file` resolves to an existing file. Log warning and skip on missing file. Never overwrite an existing file in the worktree's `.claude/rules/` with a different name.
- **[Risk] wt-project-web and wt-tools are separate repos** → Template fixes are in wt-project-web; dispatcher/monitor/wt-web fixes are in wt-tools. Tasks must cover both repos.
- **[Risk] `total_cache_create` doesn't perfectly measure context fill** → It's the best available proxy without API introspection. The number is meaningful for trend analysis even if not exact.

## Migration Plan

1. Fix wt-project-web templates (standalone, deployable via `wt-project init`)
2. Add rule injection to dispatcher (additive, guarded by `project-knowledge.yaml` presence)
3. Add context fields to monitor (additive, optional fields — old state files without them display nothing in wt-web)
4. Update wt-web change list (conditional column — no display regression)

Rollback: template fixes are file-level reversions; dispatcher/monitor changes are no-ops if `project-knowledge.yaml` absent or fields missing.

## Open Questions

- Should `worktree-setup.md` also trigger on `playwright.config*` scope (E2E test setup)? → Conservative default: only prisma + jest scope. Can expand after next E2E run.
- Should context_tokens_start capture the loop-state after iteration 1, or the initial wt-loop startup (which has no loop-state yet)? → Iteration 1 completion is the earliest reliable capture point.
