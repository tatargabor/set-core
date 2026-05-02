## Context

The set-core orchestration framework defines a hard architectural invariant: **every change is end-to-end** — it owns its build, its tests, AND its e2e specs together. This invariant predates the domain-parallel pipeline and is encoded explicitly in `_PLANNING_RULES_CORE` (`lib/set_orch/templates.py`):

- *line 407*: `NEVER create a standalone "e2e-consolidation", "playwright-e2e", or "e2e-tests" change`
- *line 435*: `Each change that adds user-facing functionality MUST include its own tests`

Both rules feed into the **flat** planner via `render_planning_prompt` (which interpolates `_PLANNING_RULES`). The flat planner produces e2e-bundled-with-feature changes correctly — confirmed by historical runs and the current `_PLANNING_RULES` text.

The 3-phase **domain-parallel** pipeline was added later as an optimization for large specs (≥30 reqs). It splits planning across three LLM calls:

| Phase | Prompt builder | Includes `_PLANNING_RULES`? |
|---|---|---|
| 1 (brief) | `render_brief_prompt` | NO |
| 2 (per-domain decompose) | `render_domain_decompose_prompt` | YES (`{_PLANNING_RULES}` interpolated) |
| 3 (merge & resolve) | `render_merge_prompt` | NO |

The Phase 1 prompt is free to declare any domain partitioning, including a `testing` domain. Once Phase 2 receives an explicit `domain_name="testing"` plus `domain_summary` describing test concerns, the per-domain agent is instruction-bound to plan changes within that domain — and a `testing` domain naturally produces `playwright-*` changes. The `_PLANNING_RULES` text in Phase 2 is overruled in practice by the Phase 1 brief's domain definition.

Phase 3's merger has the structural authority to refold standalone test changes back into feature changes, but its prompt currently instructs only "merge and resolve" mechanics (dependency graphs, phase numbers, conflict serialization) — not test-bundling.

The result: the flat planner correctly bundles e2e specs with their features; the domain-parallel pipeline does not. The fix is to **propagate the existing test-bundling invariant through all three phases of the domain-parallel pipeline**, rather than to weaken or replace it.

Constraints:
- Cannot regress the flat planner (which already works correctly).
- Cannot break in-flight plans on disk that may have been created under the old prompts.
- Must compose cleanly with `planner-decompose-determinism` (cache + force_strategy knob).
- Cannot rely solely on prompt instructions — LLM behavior is non-deterministic, so a code-level guard is required as a defense.
- The "one allowed test-related change" must remain `test-infrastructure-setup` (Playwright config, global-setup, fixtures) — this is genuinely cross-cutting and not a feature-test pairing.

Stakeholders: planner code, agents that author feature changes, operators reviewing plans, the verify-gate (which silently passes feature-only changes today because no e2e spec is dispatched with them).

## Goals / Non-Goals

**Goals:**
- Restore the "feature change owns its e2e tests" invariant in the domain-parallel pipeline, matching the flat planner's behavior.
- Make the invariant **explicit at every stage** of the 3-phase pipeline (Phase 1 forbids declaring `testing` as a domain; Phase 2 requires e2e specs in feature change scopes; Phase 3 refolds violators).
- Provide a code-level fail-fast guard so prompt-drift cannot silently re-introduce the regression.
- Preserve `test-infrastructure-setup` as the single legitimate cross-cutting test-related change.
- Keep the change additive — do not modify the flat planner's prompt or the digest pipeline.

**Non-Goals:**
- Eliminating the 3-phase domain-parallel pipeline. It remains the right tool for large specs; we are fixing its test-handling, not removing it.
- Adding more standalone test-related change classes (e.g. a global "test-runner-setup" change). The infrastructure-setup is the only allowed exception.
- Changing the `_PLANNING_RULES_CORE` text itself — it is correct as written. We are propagating it more thoroughly.
- Migrating in-flight plans on disk. Existing `playwright-*` changes finish under their old plan; new plans use the bundled pipeline.
- Validating that agents actually write the e2e spec at implementation time (that's a gate-runner concern, separate from planner-time enforcement).
- Changing dashboard or forensic UI to reflect the new structure (a follow-up if operators ask).

## Decisions

### D1 — Modify ALL three phase prompts, not just Phase 1

We considered restricting the fix to Phase 1 only (forbid `testing` in `domain_priorities` and trust the LLM to redistribute test concerns into feature domains automatically). Rejected because:

- Phase 1 receives only `domain_summaries` from prior digest output. If those summaries already describe test work as a separate concern, the LLM may still emit a "tests" or "qa" domain under a different name, dodging a single-prompt-string guard.
- Phase 2 currently receives `_PLANNING_RULES` but its `domain_name` and `domain_summary` parameters can override the rule when they explicitly direct the agent to plan test changes. Strengthening Phase 2's `## Constraints` block makes the per-change e2e-ownership rule unambiguous regardless of how Phase 1 partitioned the work.
- Phase 3 is the natural cleanup boundary — it sees ALL Phase 2 outputs together and is the only place where test-only changes can be refolded into feature changes structurally.

The defense-in-depth approach (each phase enforces its own slice of the invariant) is more robust than relying on any single phase.

### D2 — Code-level fail-fast guard, not LLM self-correction

Phase 3's prompt could instruct the merger LLM to refold standalone test changes, and that's part of Layer 3. But we add an additional **code-level regex check** after `decompose_merge` returns:

```python
for ch in plan_data["changes"]:
    if re.match(r"^(playwright|e2e|vitest)-", ch["name"]) and ch["name"] != "test-infrastructure-setup":
        raise RuntimeError(f"decompose-test-bundling violation: ...")
```

Rationale:
- LLM prompts are non-deterministic. A future model upgrade could subtly change adherence rates.
- The fail-fast guard catches the regression deterministically and cheaply.
- Failure mode is acceptable: the orchestration aborts at plan time with a clear error, before any agent dispatch wastes tokens on a misshaped plan.
- Compared to soft fallback ("just rename the change in code"), fail-fast surfaces prompt-drift as a maintenance signal — the team gets paged and fixes the prompt rather than accumulating silent compensations.

Alternative considered: post-Phase-3 LLM-driven cleanup pass that auto-refolds violators. Rejected — adds another LLM call for an edge case that should be solvable at prompt level. If the guard fires often in practice, that's a Phase 3 prompt regression to fix, not a design flaw to paper over.

### D3 — Regex match list: `playwright|e2e|vitest`

The fail-fast guard matches change names starting with `playwright-`, `e2e-`, or `vitest-`. We considered broader patterns (any change name containing `test`, `spec`, `qa`) but rejected:

- `test-infrastructure-setup` is a legitimate name — keyword-based matching would false-positive.
- Names like `regression-test-suite` or `acceptance-test-runner` could be valid in non-trivial projects; those names are already discouraged by `_PLANNING_RULES` line 435 and don't need a code-level block.
- The three matched prefixes are exactly the prefixes that have appeared in the regression. Tight match → low false-positive rate.

If new patterns emerge in production, extend the regex list incrementally. Keep the constant in `_TEST_CHANGE_NAME_PREFIXES` near the planner's domain-parallel function so the source-of-truth is one place.

### D4 — Allow `test-infrastructure-setup` as the singleton exception

This change is genuinely cross-cutting:
- Playwright config (`playwright.config.ts`) shared across all e2e specs.
- `tests/e2e/global-setup.ts` (database init, BUILD_COMMIT marker).
- vitest config + shared test fixtures (`tests/__fixtures__/`).

It does NOT pair with one feature; pairing it with any specific feature would arbitrarily privilege that feature. The flat planner's `_PLANNING_RULES` line 405 already names it explicitly as the cross-cutting infrastructure change. We carry the same exception into the domain-parallel guard.

The exact match is `change["name"] == "test-infrastructure-setup"` (no prefix wildcard). Any rename in the future is a deliberate decision with prompt + guard updates together.

### D5 — In-flight plans are not migrated

Existing plans on disk with `playwright-*` change names finish under their original plan. The post-Phase-3 guard fires only on plans produced *after* this change ships. Rationale:

- Migrating in-flight plans means rewriting `openspec/changes/<name>/proposal.md` etc., refolding requirements across change directories, updating `orchestration-plan.json`. Out of scope and risky.
- Operators with half-completed `playwright-*` changes can either (a) let them complete naturally — the regression effect is "false-green feature gate" which is recoverable, or (b) `git checkout -- openspec/changes/<old-plan>` and re-run the digest with the new prompts.
- Release notes call out the migration policy explicitly.

### D6 — Phase 1 prompt: explicit forbidden-token list

The Phase 1 brief prompt's new "DOMAIN ENUMERATION RULES" block enumerates forbidden domain-name tokens:
`testing`, `tests`, `e2e`, `playwright`, `vitest`, `qa`, `validation`.

Rationale: explicit token-list is more robust than abstract instruction. An abstract rule like "do not separate testing concerns into a domain" leaves room for the LLM to invent synonyms (`quality`, `coverage`, `assertion`); a literal forbidden-list is an exhaustive trap.

Trade-off: the list may need extension if future LLM training data introduces new synonyms (`integration-test-domain`, `coverage-domain`). We accept periodic maintenance as the cost of explicit guarding.

### D7 — Validation procedure: 3 scaffolds

We validate on `micro-web`, `minishop`, `craftbrew` — the 3 scaffolds large enough to trip the domain-parallel threshold (`req_count >= 30`). `nano` is excluded because it stays under the threshold and uses the flat planner. Each scaffold runs once; we use the digest cache (from `planner-decompose-determinism`) so any subsequent debug iteration is free.

Acceptance criterion is structural, not LLM-quality: zero `^(playwright|e2e|vitest)-` change names except `test-infrastructure-setup`, AND every feature change's scope mentions a `tests/e2e/*.spec.ts` path. We do NOT assess "do the e2e specs the feature change writes actually catch bugs" — that's a different concern measured by gate-runner failure rates over time.

## Risks / Trade-offs

- [**Risk**] LLM in Phase 1 invents a domain name not in our forbidden-token list (e.g. `coverage`, `assurance`). → **Mitigation:** the post-Phase-3 regex guard matches change-name prefixes (`playwright-`, `e2e-`, `vitest-`), which are the actual leaf change names regardless of the umbrella domain name. So even if Phase 1 produces an unexpected domain name, the guard catches its standalone test changes.

- [**Risk**] LLM in Phase 1 still sneaks `playwright`-prefixed changes into `cross_cutting_changes` despite the forbidden-list. → **Mitigation:** the post-Phase-3 guard fires regardless of which array the change came from. `cross_cutting_changes` and per-domain `changes` both flow through the merger and end up in the unified plan, where the guard inspects them all.

- [**Risk**] Feature changes grow too large because they now must include their e2e spec authoring. → **Mitigation:** the existing `_PLANNING_RULES` already caps complexity (S < 8 tasks, M ≤ 15) and scope text length (800-1500 chars). A Playwright spec is typically 30-100 LOC and 1-3 tasks of work. Empirically the flat planner produces correctly-sized changes with bundled tests. Domain-parallel will inherit the same ceiling.

- [**Risk**] The fail-fast guard fires on a legitimate edge case we haven't anticipated. → **Mitigation:** the error message names the violating change and the rule. Operators can `git revert` the plan, edit prompts, retry. The guard is a development signal, not a permanent block.

- [**Risk**] An LLM model upgrade ships a regression that our prompts no longer constrain. → **Mitigation:** the post-Phase-3 guard is model-independent. It catches the specific failure class deterministically. Validation runs (3 scaffolds, free thanks to cache) catch it on the next CI run.

- [**Trade-off**] The Phase 1/2/3 prompts grow by ~30 lines combined. Token cost: negligible (the prompts already weigh several thousand tokens each). LLM attention cost: minor — explicit rules are cheaper to follow than abstract ones, even when they cost more input tokens.

- [**Trade-off**] We accept that the test-bundling invariant is enforced at planner-time only. Whether the agent at gate-time actually writes a comprehensive e2e spec is a gate-runner concern; the planner can only set the requirement in scope text. If an agent skimps on tests, that's caught by the existing `quality gate BLOCKS changes without test files` rule (`_PLANNING_RULES` line 437) — not by this change.

- [**Trade-off**] The "1 allowed test change" exception (`test-infrastructure-setup`) is a special-case in the guard. It's a single hard-coded constant; we accept that special-case in exchange for handling the genuinely cross-cutting infra concern cleanly.

## Migration Plan

1. Land code on a feature branch.
2. Run `/opsx:apply` on this change in set-core → modifies `templates.py` + `planner.py`.
3. Run validation procedure (Layer 5 in proposal): clear digest cache, run digest on `micro-web` / `minishop` / `craftbrew` scaffolds, capture plans, assert zero standalone `playwright-*`/`e2e-*`/`vitest-*` changes (other than `test-infrastructure-setup`).
4. If any scaffold's plan still contains a forbidden change name, the post-Phase-3 guard fires; investigate prompt regression and tighten the forbidden-list or constraint wording.
5. Restart `set-web` so the new prompts and guard are live in the running service.
6. Manually verify by re-running the previously-stopped `micro-web-run-20260502-0042` orchestration (or a fresh micro-web) — the new plan should have ≤ 10 changes (vs the previous 15) and every feature change should mention its `tests/e2e/<feature>.spec.ts`.
7. Update release notes describing the bundling change and the migration policy for in-flight `playwright-*` plans.

Rollback: revert the proposal commit. The flat planner is unchanged; the domain-parallel pipeline reverts to its previous (regressing) behavior. No data corruption — plans on disk are unaffected. The fail-fast guard simply stops firing.

## Open Questions

- **Q1**: Should the fail-fast guard be a WARNING (with auto-refold) instead of a hard error? **Decision:** hard error. Auto-refold is a code-level workaround for prompt failure — better to fix the prompt than to hide the failure. The error message is explicit and actionable.

- **Q2**: Should we add a `decompose_merge` retry-on-violation: if the post-merge guard fires, re-call the merger LLM with the violation cited, asking it to refold? **Decision:** out of scope for this change. Adds another LLM call and complicates the failure mode. If the guard fires more than rarely in production, revisit. For now, fail-fast is the simpler and more diagnostic choice.

- **Q3**: Should the validation step (Layer 5) be wired into a CI check that runs on every set-core PR? **Decision:** out of scope here. Wire as a separate small change once the bundling change has stabilized — the validation script is already documented in `tasks.md` and can be invoked manually.

- **Q4**: Does the new constraint affect `decompose-design-binding` or `decompose-hints` capabilities? **Decision:** no — those describe digest/spec/brief input handling, not the 3-phase decompose pipeline. They are orthogonal.
