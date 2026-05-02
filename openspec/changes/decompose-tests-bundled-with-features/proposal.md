## Why

The flat decompose path (`render_planning_prompt` in `lib/set_orch/templates.py`) has — for a long time — explicit `_PLANNING_RULES_CORE` rules that **prevent** standalone test-only changes:

> *line 407:* `NEVER create a standalone "e2e-consolidation", "playwright-e2e", or "e2e-tests" change that only writes E2E tests. This anti-pattern overloads one agent with all cross-feature tests and wastes tokens. Each feature change MUST include its OWN E2E tests inline.`
>
> *line 435:* `Each change that adds user-facing functionality MUST include its own tests. Do NOT defer testing to a final "acceptance-tests" or "e2e" change — each change owns its tests.`

These rules are ALREADY present in the codebase. They worked correctly before the 3-phase domain-parallel decompose was introduced. **The regression is purely a prompt-coverage gap**: when domain-parallel was added, the rules were partially carried into Phase 2 only — Phase 1 (`render_brief_prompt`) and Phase 3 (`render_merge_prompt`) do not receive `_PLANNING_RULES`, so:

- **Phase 1** is free to enumerate `testing` as one of the `domain_priorities` — nothing in its prompt forbids that.
- **Phase 2** (`render_domain_decompose_prompt`) DOES include `{_PLANNING_RULES}`, but by the time Phase 2 runs, the brief has already declared `testing` a domain. The Phase 2 agent is then explicitly told "you are planning ONLY for the testing domain" and dutifully produces `playwright-*` changes for it. The "feature change owns its tests" rule never fires because no feature domain agent sees the test requirements — they were already routed to the testing domain.
- **Phase 3** (`render_merge_prompt`) merges what Phase 2 produced — it has no instruction to refold standalone test changes back into feature changes, and `_PLANNING_RULES` is not in its prompt.

Observed effect (recent micro-web E2E plan, 38 reqs): 4 domains including `testing`, which alone produced 5 changes (`test-infrastructure-setup`, `vitest-validation-unit-tests`, `playwright-smoke-and-palette`, `playwright-contact-wizard-and-blog-filter`, `playwright-mobile-drawer`). Each feature change carried no e2e spec in its scope.

The fix is to **propagate the existing test-bundling rules through all three phases of the domain-parallel pipeline**, plus a code-level fail-fast guard for prompt-drift defense. We are restoring the invariant that already exists in the flat path, not inventing new behavior.

## What Changes

The change has 4 layers, mirroring the principle "rules first, code-level guard last."

**Layer 1 — Phase 1 brief prompt (`render_brief_prompt` in `lib/set_orch/templates.py`):**

- Add an explicit "DOMAIN ENUMERATION RULES" block before the schema. Required content:
  - The `domain_priorities` array MUST list ONLY feature/code domains (e.g. `navigation`, `content`, `forms`, `auth`, `data`).
  - It MUST NOT list any of: `testing`, `tests`, `e2e`, `playwright`, `vitest`, `qa`, `validation`, or other test-only synonyms.
  - Test requirements (e2e specs, unit tests, integration tests) belong in the **feature** domain that owns the feature being tested.
  - The ONLY exception is `test-infrastructure-setup` (Playwright config, `tests/e2e/global-setup.ts`, fixtures, vitest config) — this MAY appear in `cross_cutting_changes` but MUST NOT spawn a `testing` domain.

**Layer 2 — Phase 2 per-domain decompose (`render_domain_decompose_prompt`):**

- Strengthen the existing `## Constraints` block with one new mandatory bullet:
  - "Each change in this domain that adds user-facing UI or HTTP routes MUST own at least one e2e spec file in its `spec_files` field. The change's `scope` text MUST mention the spec file path the implementing agent will create at `tests/e2e/<feature>.spec.ts`."
- This complements the existing `_PLANNING_RULES` (which is already in the Phase 2 prompt) and makes the per-change requirement explicit at the per-domain prompt level.

**Layer 3 — Phase 3 merge prompt (`render_merge_prompt`):**

- Add a "TEST CHANGE FOLDING" rule to the existing `## Rules` block:
  - "If any incoming change name matches `^(playwright|e2e|vitest)-` AND it is not exactly `test-infrastructure-setup`, the merger MUST refold its `requirements`, `spec_files`, and `also_affects_reqs` into the corresponding feature change (the change whose code is under test). The merger MUST NOT emit standalone test-only changes."
- This gives Phase 3 the authority to clean up Phase 2 prompt-drift even if Layer 1/2 partially fail.

**Layer 4 — Post-Phase-3 fail-fast guard (`lib/set_orch/planner.py`, in `_try_domain_parallel_decompose` after the `decompose_merge` LLM call returns):**

- Inspect the parsed plan. For each change, check `re.match(r"^(playwright|e2e|vitest)-", change["name"])`. If any match AND the name is not exactly `test-infrastructure-setup`, raise a `RuntimeError("decompose-test-bundling violation: change '{name}' is a standalone test change. Tests must bundle with their feature change. See openspec/changes/decompose-tests-bundled-with-features/.")`.
- The guard fires once after Phase 3 returns, before plan persistence. It surfaces prompt-drift as a loud failure rather than a silent regression.

**Layer 5 — Validation (in `tasks.md`):**

- Run `set-orch-core digest run` on `tests/e2e/scaffolds/{micro-web,minishop,craftbrew}` (cache-cleared once at start) and assert plan-level invariants:
  - Zero changes match `^(playwright|e2e|vitest)-` other than `test-infrastructure-setup`.
  - Every change with `change_type=feature` AND a non-empty UI scope mentions a `tests/e2e/<…>.spec.ts` path in its scope text.
- Validation runs use the digest cache (from `planner-decompose-determinism`) so re-runs are free.

## Capabilities

### New Capabilities

- `decompose-test-bundling`: defines the contract that prevents the 3-phase domain-parallel decompose from producing standalone `playwright-*`/`vitest-*`/`e2e-*` changes (other than the singleton `test-infrastructure-setup`), and the post-merge fail-fast guard that enforces this at code level.

### Modified Capabilities

- *(none — the existing planner / templates specs do not enumerate prompt-template wording at the requirement level. The new capability adds the bundling contract that didn't exist as a formal requirement before this change.)*

## Impact

- **Code**:
  - `lib/set_orch/templates.py` — Phase 1 (`render_brief_prompt`), Phase 2 (`render_domain_decompose_prompt` constraints), Phase 3 (`render_merge_prompt` rules) wording updates. ~30 lines of prompt text added across the three functions.
  - `lib/set_orch/planner.py` — post-Phase-3 fail-fast guard in `_try_domain_parallel_decompose` (~10 lines).
- **No code change** in the flat decompose path (`render_planning_prompt`), in the digest module, in any gate executor, in the dispatcher, or in any consumer-deployed file.
- **Behavior**: any spec that today produces a `testing` domain will instead distribute its e2e/vitest authoring across feature changes. Plan-level change count drops by ~3-5 standalone test changes for typical mid-size specs. Each feature change grows in scope (now also writes its e2e spec) but stays well within agent context (Playwright spec files are typically 30-100 LOC).
- **Determinism**: combines cleanly with `planner-decompose-determinism` (digest cache) — same spec produces the same bundled plan every run.
- **Backwards compat**: in-flight plans on disk with `playwright-*` change names are NOT migrated. They finish under their original plan. The fail-fast guard fires only on *new* plans produced after this change ships. We document this in release notes; an operator with a half-completed `playwright-*` change can either let it complete or `git checkout -- openspec/changes/<name>` and re-plan.
- **Validation cost**: re-running digest on 3 scaffolds × ~30s each is a one-time budget hit. The cache from `planner-decompose-determinism` makes subsequent runs free.
- **Risk surface**: prompt-driven LLM behavior is non-deterministic; the post-Phase-3 regex guard is the safety net that turns prompt-drift into a loud failure rather than a silent regression. We accept that an extreme prompt-drift could still produce unexpected change names — but the guard catches the specific failure class we have observed.
- **No impact** on flat-decompose runs, on small specs that already use the flat planner (req_count < 30 or `force_strategy: flat`), or on consumer-project orchestration that does not use the Phase 1/2/3 pipeline.
