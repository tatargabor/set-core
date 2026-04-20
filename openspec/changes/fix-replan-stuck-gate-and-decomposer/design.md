## Context

An E2E run of the orchestrator against a medium-complexity web project surfaced nine defects that, when compounded, burned multi-hour runtime on zero progress. The failure mode is a cascade:

1. **Replan entanglement.** The first plan archived 3 of 7 changes (3 merged, 3 skipped, 1 never archived). A replan then generated a completely new 6-change plan. The orphan cleanup logic refused to remove "dirty" worktrees left over from the prior run's merges (files touched by merge, not yet committed), so 3 old worktrees + 3 old branches remained active alongside the new plan. The `openspec/changes/` dir still held old-plan dirs. Any poll that tried to reconcile saw a three-way inconsistency: `state.json` had 6 changes, `git worktree list` had 4 (different) worktrees, `openspec/changes/` had 4 yet-different dirs.

2. **Stuck re-gate loop.** When the first new-plan change hit its verify gate for real (first time in set-core's history with a real review + spec_verify run), the review gate failed with 1 CRITICAL + 3 HIGH findings. The agent entered a fix loop, burned the budget, exited with `loop_status=stuck` but WITH new commits. At this point two handlers fired contradictorily: the engine logged `routing to re-gate (skip stall timeout)` and the verifier logged `marking stalled for watchdog`. The verifier won — the change sat stalled until the 300-second watchdog recovered it, the agent ran again briefly, exited stuck, and the loop repeated 23 times.

3. **Supervisor trigger storm.** During the replan startup window (4 minutes of log silence while the planner ran), the supervisor's `log_silence` detector fired every 15 seconds, all 15 times returning `skipped: retry_budget_exhausted`. Pure noise in the event log.

4. **Wrong gate set.** The first-run `foundation-setup` change contained UI (copied from a v0 design export) but the gate registry selected gates by `change_type=infrastructure` and never ran `design-fidelity`/`e2e`/`i18n_check` on it. The UI quality problem wasn't detected until much later.

5. **Coarse changes.** `foundation-setup` alone had ~15 capabilities in one change. The retry-budget math breaks when a single change has that much surface area — there's no way to isolate which requirement is failing.

This design doc explains the technical choices that bind these fixes together while keeping the engine understandable.

## Goals

- Make replan a true state-reset boundary: post-replan, the engine is in a consistent state where `state.json`, git worktrees, and `openspec/changes/` all agree on the plan.
- Eliminate the stuck re-gate loop by designating a single handler and giving it a termination condition.
- Tame the supervisor's tight polling noise without losing real anomaly detection.
- Base gate selection on observable change content, not author-declared labels.
- Keep decomposed changes small enough that retry budgets are meaningful.

## Non-Goals

- **Not** redesigning the verify-gate retry model (5 retries for `review`, 4 for others). The budget levels are load-bearing for existing downstream logic and changing them would touch many capabilities.
- **Not** adding a whole new "investigation agent" path. The investigation machinery lives at `lib/set_orch/issues/` (`investigator.py`, `fixer.py`, `manager.py`, `policy.py`, `registry.py`, `models.py`) — it already generates `fix-iss-*` proposals (e.g., `fix-iss-004` in the reference run). This change wires additional trigger points into that existing module; it does not create a new module. The new public helper is added to the existing `issues/` package, not a greenfield `investigation_runner.py`.
- **Not** moving to a pub/sub or event-sourced orchestrator. All work stays in the `orchestration-state.json` + `orchestration-events.jsonl` world.
- **Not** adding a new project type or profile. All changes extend the existing `CoreProfile` / `WebProjectType` pair.

## Decisions

### D1: Single-writer for `last_gate_fingerprint`

The new fields `stuck_loop_count`, `token_runaway_baseline`, and `last_gate_fingerprint` are read by multiple components (stuck-loop circuit breaker, token-runaway circuit breaker). Without a clear owner, two components can race on writes after a verify pipeline run.

**Decision:** the verifier is the sole writer of `last_gate_fingerprint`. It writes the fingerprint as the last step of `run_verify_pipeline()` in the same state transaction that emits the `VERIFY_GATE` event. Readers (stuck-loop counter in the dispatcher, token-runaway check in the engine) only read.

**Alternatives considered:**
- Writer per reader (each computes its own fingerprint): allows drift if the fingerprint algorithm changes; rejected.
- Event-sourced reconstruction: expensive on every poll; rejected.

### D2: Reconciliation after plan validation, not before

`auto_replan_cycle()` runs `collect_replan_context() → Claude → validate_plan() → reconcile → init_new_state()`. Reconciliation destroys state, so it must run AFTER plan validation — otherwise a bad plan would have already wiped the prior state.

**Decision:** reconcile only after validation succeeds. If validation fails, the orchestrator retains the old plan's state and can retry the replan with a fresh prompt (existing behavior).

**Trade-off:** reconciliation is not atomic with plan persistence. A crash between `reconcile` and `init_new_state()` leaves the engine with orphaned git state and no plan. Mitigation (to be implemented as part of this change, not pre-existing): the Python engine's `cmd_plan()` will wrap both steps in a single state lock and write `orchestration-plan.json.partial` first; a crash mid-reconcile leaves this partial file which the next startup detects and rolls back. Recovery = restore previous `orchestration-plan.json` from `.bak` (existing back-compat behavior) and replay reconciliation idempotently.

### D3: Content-aware gate selection is additive only

A content-scan-driven gate selector that also *removes* gates would be dangerous: a buggy classifier could silently skip `review` on a security-sensitive change. We keep the subtraction power in `gate_hints` alone (explicit opt-out).

**Decision:** content scan can only ADD gates. `gate_hints` remains the sole way to skip gates explicitly. Re-detection after first commit is one-shot per change (guarded by `gate_recheck_done`); this avoids gate-set churn on every poll.

**Alternative:** always re-run detection on every commit. Rejected — would make gate-run timing non-deterministic and produce hard-to-reproduce gate failures.

### D4: Stuck-loop counter compares fingerprints, not raw gate results

Two consecutive `review` failures with different findings ARE progress (the agent is fixing stuff, even if incompletely). The counter must distinguish "same findings again" from "new findings each time."

**Decision:** the fingerprint is `(stop_gate, sorted(finding_ids))` where `finding_id` is the reviewer's stable hash of each finding. Same fingerprint twice in a row = no progress. Different fingerprint = progress, reset counter.

**Trade-off:** if the reviewer returns slightly different wording for the same underlying issue (non-deterministic LLM output), the fingerprints differ and the counter resets. Mitigation: the reviewer already produces stable IDs; if stability breaks, the counter becomes strictly more permissive (fails to fire), not more aggressive.

### D5: Supervisor back-off is per-tuple, not per-trigger

Log-silence triggers are orchestration-scoped (no change context). Integration-failed triggers are change-scoped. Both exhaust budgets under different conditions. A single global back-off would suppress legitimate change-scoped triggers while the log-silence one is in its cap.

**Decision:** back-off is keyed by `(trigger, change, reason_hash)`. The empty string is used for `change` when the trigger is orchestration-scoped — this is explicit in the key format contract (see `supervisor-transition-triggers` spec).

**Alternatives considered:**
- Per-trigger only (`trigger` as the key): would suppress change-scoped triggers globally when any orchestration-scoped one is in back-off. Rejected.
- Per-trigger + per-change (no `reason_hash`): two distinct reasons for the same trigger on the same change would share back-off state, suppressing legitimate second-cause triggers. Rejected.

**Trade-off on `reason_hash`:** collisions (two different reason strings hashing to the same 12-char SHA1 prefix) could silently suppress an unrelated trigger. Mitigation: log the full reason string alongside the hash at DEBUG level so debugging a missed trigger can reconstruct which reason owned the slot. The collision probability with SHA1[:12] is ~10⁻¹⁸ per pair; acceptable.

### D6: Decomposer auto-split happens pre-persistence

If auto-split ran after the plan was already persisted and state was initialised, the engine would see the pre-split name briefly and might try to dispatch it. Worse, if the split names differ from the original, the divergent-plan reconciliation path would treat the original as stale on the next poll and destroy it.

**Decision:** auto-split is a step inside `planner.validate_plan()`. If any change exceeds a cap, the planner rewrites the plan in-memory, validates again, and only then returns. No pre-split name ever reaches disk.

**Alternative:** emit the oversize change unchanged and flag it with a warning. Rejected — leaves the retry-budget math broken for exactly the cases the fix targets.

### D8: Size formula replaces hard caps

Hard caps on requirement count / scenario count / file count are easy to enforce but correlate poorly with actual implementation effort. A change with 4 requirements and 9 admin pages is harder than a change with 10 requirements and 3 server modules. The field data from the reference run bears this out: `stories-and-content` (5 reqs, 4 files) was the smallest by effort; `admin-operations` (8 reqs, 11 files) was ~4x larger than anything else.

**Decision:** drop hard caps. Use a profile-weighted `estimated_loc` formula (see `decomposition-agent` spec delta for the full definition). Default threshold 1500 LOC. Over-threshold changes split into siblings.

**Alternatives considered:**
- Keep hard caps, add a LOC cap alongside: rejected — two competing thresholds is a config smell; engineers will tune only one.
- Per-profile caps tuned empirically: deferred — let `loc_weights()` carry the profile-specific tuning instead; the threshold stays a single knob.

**Trade-off:** the formula is a heuristic. A scope that describes file paths but actually implements much less (or more) will be miscategorised. Mitigation: recalibrate the weights periodically against real merged changes' LOC. The weights are in code (`ProjectType.loc_weights()`), not hard-coded, so recalibration is a one-line change.

### D9: Linked sibling split over independent small changes

When a change exceeds the size threshold, two split strategies were considered:
1. **Independent small changes** — split into separate changes with no `depends_on`, all in the same phase, possibly running in parallel.
2. **Linked siblings** — split into N changes chained via `depends_on`, running sequentially.

**Decision:** linked siblings. Reasons:
- The 2nd+ sibling typically builds on scaffolding (admin shell, shared components, shared state) that the 1st creates; parallel execution would produce merge conflicts.
- Sequential execution allows the retry budget to reset per sibling, effectively giving a chain of smaller changes the budget they need.
- The `depends_on` chain is already respected by the dispatcher; no new mechanism needed.

**Alternative rejected:** parallel siblings with shared-file locks. Rejected — the lock model is complex and merge conflicts on `package.json`, `tailwind.config.ts`, `prisma/schema.prisma` would still occur.

### D10: Scoped re-gate as safety-first additive tier

Retrying every gate fully on every retry is expensive (`review` alone is ~243s on opus). Skipping gates on retry is dangerous (regression hiding). The middle ground is a **per-gate retry policy** declared by the project-type profile.

**Decision:** three-tier policy (`always` / `cached` / `scoped`). The default is `always` (safe). Profiles opt individual gates into cheaper modes. Cache invalidation triggers (diff-touches-scope, cache-use cap, new-API-surface) prevent silent regression hiding.

**Key safety choice:** the 3rd consecutive cache reuse FORCES full re-run. This bounds the drift window to 2 cached retries → if a regression slips past the cache twice, the 3rd retry catches it. This is a tunable constant (`max_consecutive_cache_uses`), default 2.

**Alternatives considered:**
- Diff-based gate selection (skip gates entirely if their scope isn't touched): rejected — a build cascade can break a gate's output even if the gate's "own" files aren't touched.
- LLM-based relevance classifier ("is this gate still valid?"): rejected — adds an LLM call to every retry, exactly what we're trying to reduce.
- Confidence-weighted cache (decay cache value over retries): rejected — more complex than a hard cap, not materially safer.

**Trade-off:** a gate whose scope is subtly coupled to a file outside its `cache_scope_globs` could be cached through a regression. Mitigation: the cap forces re-run every 3 retries; findings from the forced re-run would catch the drift (at the cost of 1 expensive run per 3 retries).

### D7: i18n_check is hard-fail (not warn)

The previous warn-fail mode had no mechanism to force the agent to fix i18n. Downstream users (consumers) hit i18n gaps in production that should have been blocked at verify time.

**Decision:** i18n_check returns `pass | fail | skipped`. The "warn-fail" state is removed entirely from the gate vocabulary.

**Migration:** existing changes in `modules/web/` and consumer configs that referenced `warn-fail` need updating. Impact audit is narrow — `grep -r "warn-fail"` in set-core + consumer scaffolds should show <20 hits.

## Risks / Trade-offs

- **[Risk]** Force-cleaning dirty worktrees during divergent replan could lose uncommitted user work. **Mitigation:** the `git stash push -u` rescue path preserves uncommitted work in the stash ref log; the `wip/<name>-<epoch>` branch fallback handles stash-failure cases. Both are logged at INFO with recovery paths.

- **[Risk]** Content-aware gate selection might add gates that a profile isn't prepared to run (e.g., a core-only project picking up `design-fidelity` with no design spec). **Mitigation:** `classify_content()` returns empty set when the active profile is `CoreProfile`; additive-only means the gate set can never be *worse* than the prior static mapping.

- **[Risk]** Stuck-loop counter default `max_stuck_loops=3` might be too aggressive for genuinely hard bugs that need 4-5 iterations. **Mitigation:** configurable via directive; escalation goes to fix-iss auto-creation, not to hard failure of the surrounding plan.

- **[Risk]** Token-runaway threshold (20M) is arbitrary. **Mitigation:** configurable directive; initial value chosen as 3× the largest observed healthy change.

- **[Risk]** Parallel `spec_verify` + `review` could overload the model API and trigger rate-limiting on smaller API plans. **Mitigation:** the parallel group is opt-in via `WebProjectType.parallel_gate_groups()`; profiles can return `[]` to stay serial.

- **[Risk]** The `fix_iss_child` field adds a chain of changes that the dashboard/reporter must render. **Mitigation:** field is optional (`str | None`); existing UI paths default to no-link rendering if the field is None. Dashboard work tracked in tasks.md.

## Migration Plan

1. **State schema migration.** New fields (`stuck_loop_count`, `token_runaway_baseline`, `last_gate_fingerprint`, `fix_iss_child`, `gate_recheck_done`) are all nullable/default-zero and backwards-compatible. No explicit migration step needed.
2. **Supervisor status schema migration.** `trigger_backoffs` defaults to `{}` on load if missing. No migration.
3. **Deploy order.**
   a. Module refactor first: create `lib/set_orch/gate_registry.py` by moving `GateConfig` + selector logic out of `gate_profiles.py`. `gate_profiles.py` keeps its public shims (re-exports) for back-compat during transition. This MUST land before any task in section 7 — those tasks assume `gate_registry.py` exists.
   b. Land content-aware gate selection (`per-change-gate-skip`, `web-gates`, `decomposition-agent.touched_file_globs`) — these are additive and don't break existing runs.
   c. Land stuck-loop handler and token-runaway breaker together (they share `last_gate_fingerprint`).
   d. Land replan reconciliation + force-clean last — changes existing behavior for orphan_cleanup, largest blast radius.
4. **Rollback plan.** Every new behavior is guarded by a directive with safe defaults. To roll back any single feature, set the directive to a no-op value:
   - `max_stuck_loops=999` → effectively disables stuck escalation
   - `per_change_token_runaway_threshold=0` → disables token breaker
   - `parallel_gate_groups=[]` in profile override → serial gates
   - `force_dirty_on_replan=false` → falls back to old skip-dirty behavior
   - `divergent_plan_dir_cleanup=dry-run` → reconciliation logs which branches/dirs it WOULD delete but takes no action. This covers task 6.7, whose branch-delete and `openspec/changes/` dir-remove operations are irreversible. Default value is `enabled`; operators can switch to `dry-run` for one deploy cycle to verify the detection logic before letting it destroy state.
   - Before any dir removal, the reconciler SHALL write a manifest to `orchestration-cleanup-<epoch>.log` listing the branches and dirs it removed, so `git reflog`-based branch recovery can be supplemented by dir-list recovery.

## Open Questions

- **Q1:** Should `fix_iss_child` chains have a depth cap? A fix-iss that itself hits stuck-loop would create a grandchild fix-iss. Proposed cap: 2 levels of fix-iss; a grandchild that re-escalates aborts the plan.
- **Q2:** The decomposer's granularity budget uses hard caps (6/20/12). Should these be configurable per project-type profile? Simple web projects may be fine with 6; complex platforms may want 10.
- **Q3:** Does the content classifier need a "uncertain" tag for files it can't classify (e.g., generated code)? Currently the answer is "fall through to gate_hints and change_type defaults"; flagging uncertainty might be useful for observability but adds complexity.
- **Q4:** Should `loc_weights()` include a LOC budget for docs/README sections mentioned in the scope? Currently docs paths default to 150 — probably too high for pure-prose. Defer until we see a decomposer output that under-counts docs-heavy changes.

These can be resolved during implementation — none block the tasks list.

## Appendix A — Decomposer calibration against the reference plan

This appendix documents how the `estimated_loc` formula + 1500 LOC threshold split the six generic change scopes from the reference plan. The calibration is how the formula's weights and threshold were chosen; it is NOT committed code — it is context for future tuning.

### Reference plan metrics

Six changes from a generic medium-complexity web project (coffee subscription + admin + promotions + stories + email):

| change | impl files | admin pages | models Δ | tests | est. LOC | phase | complexity label |
|---|---|---|---|---|---|---|---|
| A (promotions) | 4 (1 ui + 3 server) | 3 | 0 | 1 | 2000 | 1 | M |
| B (subscription) | 5 (2 ui + 3 server) | 0 | 1 mod | 1 | 1270 | 1 | M |
| C (reviews+wishlist) | 5 (2 comp + 1 mod + 2 ui) | 1 | 2 | 1 | 1640 | 1 | M |
| D (stories) | 2 (ui) | 1 | 0 | 1 | 900 | 1 | S |
| E (admin-ops) | 1 (return form) | 9 | 3 | 1 | 3760 | 2 | M |
| F (email+seo) | 11 (1 sender + 8 templates + 2 seo) | 0 | 1 | 1 | 1750 | 2 | M |

### Threshold calibration

- Target change size: 1000–1200 LOC (fits one `opus` agent session of ~40 min comfortably, leaves room for fix-loop without timeout).
- Threshold set at **1500 LOC** (target + 25% headroom). Under this stays single; over triggers split.

Result: B and D pass through; A, C, E, F split.

### Split outcomes

| original | splits | phase | est. LOC per sibling |
|---|---|---|---|
| A (2000) | A-server-1 (server + cart UI) → A-admin-2 (3 admin pages) | 1 | 900, 1100 |
| C (1640) | C-customer-1 (reviews UI + wishlist + restock dialog + schema) → C-admin-2 (moderation admin) | 1 | 1050, 600 |
| E (3760) | E-orders-1 → E-dashboard-2 → E-returns-3 | 2 | ~1300, ~1200, ~1300 |
| F (1750) | F-delivery-1 (sender + templates + wiring) → F-seo-2 (sitemap + robots + metadata + lang switcher) | 2 | 1200, 550 |

**Six original changes → eleven sibling-split changes.** Average sibling LOC: ~1030. The only outlier is F-seo-2 at 550 LOC — below target but kept as a separate sibling because its concerns (SEO metadata, robots, lang switcher) are cross-cutting and don't cohere with email templates.

### Why 1500 and not 1200?

At threshold 1200:
- B (1270) would split unnecessarily (single cohesive feature).
- C (1640) would split the same way at threshold 1500.
- A (2000) same.

Lower threshold generates over-splitting of naturally-cohesive mid-size changes. The 1500 value is the knee where B stays whole but A, C, E, F still split.

### Why path-based weights?

Admin pages in the reference codebase typically pack a DataTable + filter + CRUD form + action handlers, averaging 300–400 LOC each. Consumer pages (public UI) typically pack a fetch + render + minimal logic, averaging 150–250 LOC. Server modules vary but cluster around 200 LOC when they own a single concern. These heuristics are codified in `WebProjectType.loc_weights()` as the concrete defaults.

### Retry-time payoff

With 11 smaller siblings (vs 6 big ones) the expected retry behavior changes materially:
- Review gate findings per retry cycle: estimated 3–5 findings on a 1000-LOC sibling vs 15–25 findings on a 3760-LOC change. Fewer findings → shorter retry prompts → faster convergence.
- Retry-budget math becomes meaningful: 5 review retries × ~1 finding-category each = agent can realistically fix each retry cycle instead of drowning in a 20-item mixed-domain finding list.

Combined with D10 (cached/scoped retry policy), the expected retry wall-time per cycle drops from ~468s (sequential spec_verify + review on the full 3760-LOC change) to:
- ~60s on cache hit (review-delta only on siblings where findings are localized)
- ~100s on scoped e2e (only affected test files)
- Full re-run every 3rd retry as safety valve.
