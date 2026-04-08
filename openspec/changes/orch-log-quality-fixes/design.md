# Design: orch-log-quality-fixes

## Context

After minishop-run2 (6/6 merged), log review surfaced 7 issues. Two are silent quality regressions:
1. `spec_verify` gate is effectively a no-op (all 9 changes got PASS without verification)
2. Context window metric reports false 900% overflow (cumulative cache writes vs. peak)

The remaining 5 are warning spam.

This change addresses all 7 in one batch because they're all in the orchestration logging/metric layer, share testing context (single E2E run validates them), and have no behavioral risk beyond log output and one metric definition.

## Goals / Non-Goals

**Goals:**
- spec_verify gate produces meaningful PASS/FAIL distinction
- Context window metric reflects actual peak vs. true window size
- Remove warning spam without losing real signal
- Backward-compat: existing PASS behavior preserved when sentinel missing

**Non-Goals:**
- Restructure spec_verify into a hard gate (separate decision)
- Per-worktree token isolation (stays per-repo)
- Planner coverage gap handling (separate change)

## Decisions

### Decision 1: Sentinel detection — additive, not breaking

**Choice:** Missing `VERIFY_RESULT:` sentinel still resolves to PASS, but logs WARNING and emits ANOMALY tag.

**Why:** Many existing runs may have agents that don't write the sentinel. A breaking change (PASS → FAIL on missing sentinel) would cause cascading retries in legacy environments. Better: log loudly so the issue surfaces, fix the prompt so future runs include sentinel, then revisit hard-fail later.

**Alternative considered:** Hard FAIL on missing sentinel — rejected for compat risk.

### Decision 2: Context window — model name detection

**Choice:** `_context_window_for_model` defaults to 1M for `opus`, `sonnet`, and Claude 4.x family. Explicit `[200k]` suffix returns 200K.

**Why:** Claude Opus/Sonnet 4.x default to 1M context in 2026. The current default (200K) is a stale assumption. The model name in directives is just `opus` or `sonnet`, no version suffix.

**Risk:** If a user runs a non-1M model, the metric over-reports headroom. Mitigation: explicit suffix syntax (`opus[200k]`).

### Decision 3: `total_cache_create` → `max(iter.cache_create_tokens)`

**Choice:** Compute peak context as the max across iterations, not the cumulative sum.

**Why:** `total_cache_create` accumulates per iteration. A 30-iter session reports 30x the actual peak. The peak is the actually-loaded context for the largest single iteration, which is what matters for "did we hit the window limit?"

**Implementation note:** loop-state.json `iterations` is a list with `cache_create_tokens` per entry. `max()` over that list is the right number.

### Decision 4: `run_git` best_effort flag — explicit opt-in

**Choice:** Add `best_effort: bool = False` parameter. Callers explicitly opt in for "may fail in valid scenarios" calls.

**Why:** Default behavior unchanged (real git errors still WARNING). Explicit opt-in documents intent. Three call sites need updating: `merger.py:735`, `merger.py:2229`, `verifier.py:2474`, `loop_tasks.py:344`.

**Alternative considered:** Suppress all "fetch origin" warnings globally — rejected as too brittle.

### Decision 5: Design anomaly conditional — check for asset existence

**Choice:** Check `os.path.isfile()` for `docs/design-system.md`, `docs/design-snapshot.md`, `docs/design-brief.md`. If none exist, log INFO. If any exist but context is empty, ANOMALY.

**Why:** The current behavior treats "no design assets" as the same anomaly as "design assets exist but pipeline failed". The first is normal (foundation changes), the second is a real bug.

### Decision 6: Worktree project dir via git common-dir

**Choice:** Use `git rev-parse --git-common-dir` to derive parent repo path. The common-dir is `/path/to/repo/.git` for a worktree, and `/path/to/wt/.git/worktrees/wt-name` typically — actually, `--git-common-dir` returns the parent's `.git` for worktrees.

**Why:** This gives us the parent repo path consistently. The Claude project dir slug is derived from the parent repo path, not the worktree path.

**Verification:** Need to test that `git -C "$wt_path" rev-parse --git-common-dir` returns the parent repo's `.git` directory, then `dirname` gives the parent repo root.

## Risks / Trade-offs

- **[Risk] spec_verify still PASS-thru** → Mitigation: WARNING log makes it visible. Future change can promote to FAIL.
- **[Risk] 1M context assumption wrong for some users** → Mitigation: explicit suffix syntax. Users on 200K can configure.
- **[Risk] `git common-dir` may not work as expected** → Mitigation: fallback to current behavior if derivation fails, no behavior regression.
- **[Risk] `parse_test_plan` debug log hides legitimate "you forgot to create the journey plan" cases** → Mitigation: callers log INFO when fallback succeeds, so the chain is still visible.

## Open Questions

None — all decisions are localized and reversible.
