## ADDED Requirements

### Requirement: Profile declares per-gate retry policy
`ProjectType` SHALL expose `gate_retry_policy() -> dict[str, RetryPolicy]` where `RetryPolicy ∈ {"always", "cached", "scoped"}`. The mapping keys are gate names (e.g., `build`, `e2e`, `review`). Unknown gates default to `"always"`.

Policy semantics:
- `"always"`: the gate executes fully on every verify-pipeline run, including retries. This is the safe default.
- `"cached"`: on retry, the gate's previous verdict (pass/fail + findings) is reused UNLESS cache invalidation fires (see below). If reused, a `GATE_CACHED` event is emitted with the source verdict's SHA.
- `"scoped"`: on retry, the gate runs but only on a subset of its scope determined by the retry diff's touched files. If the diff does not overlap the gate's scope at all, the gate is treated as `cached` for that retry.

`CoreProfile.gate_retry_policy()` SHALL return `{}` (every gate defaults to `"always"`) — conservative default for unknown project types.

#### Scenario: Core profile default is always
- **WHEN** a change under `CoreProfile` enters a retry
- **THEN** every gate in the active set SHALL execute fully

#### Scenario: Web profile declares policy per gate
- **WHEN** `WebProjectType.gate_retry_policy()` is invoked
- **THEN** it SHALL return at least:
  - `"build"` → `"always"`
  - `"test"` → `"always"`
  - `"scope_check"` → `"always"`
  - `"test_files"` → `"always"`
  - `"e2e_coverage"` → `"always"`
  - `"rules"` → `"always"`
  - `"lint"` → `"always"`
  - `"i18n_check"` → `"always"`
  - `"review"` → `"cached"`
  - `"spec_verify"` → `"cached"`
  - `"design-fidelity"` → `"cached"`
  - `"e2e"` → `"scoped"`

### Requirement: Cached policy reuses prior verdict with invalidation
A gate with `policy="cached"` SHALL reuse its most recent `pass` verdict on a retry IF ALL of the following hold:
1. The retry commit's diff does NOT touch any file in the gate's declared `cache_scope_globs` (provided by `ProjectType.gate_cache_scope(gate_name) -> list[str]`).
2. Fewer than `max_consecutive_cache_uses` (default `2`) consecutive retries on this change have reused the cache for this gate. The 3rd consecutive retry SHALL force full re-run.
3. The retry commit does not add new public API surface (new exported functions, new route handlers, new database models). Detected via static scan of the retry diff.

When any condition fails, the cache is invalidated and the gate SHALL run fully. The reason SHALL be logged as one of `diff-touches-scope`, `cache-use-cap-reached`, or `new-api-surface-detected`.

The cache key SHALL be the previous `VERIFY_GATE` event's `gate_verdict_sidecar` SHA stored per-change in state.

#### Scenario: Cached review reused when retry diff is small
- **WHEN** `review` has policy `"cached"` and its previous verdict was `pass`
- **AND** the retry commit touches only `messages/hu.json` (outside review's cache scope)
- **AND** this is the 1st consecutive cache use
- **THEN** the verifier SHALL emit a `GATE_CACHED` event with `{gate: "review", verdict: "pass", source_sha: <prior verdict SHA>}`
- **AND** SHALL NOT re-invoke the review LLM

#### Scenario: Cache invalidated by scope overlap
- **WHEN** `design-fidelity` has policy `"cached"` and its cache scope is `["src/**/*.tsx", "src/**/*.css", "public/design-tokens.json"]`
- **AND** the retry commit touches `src/components/cart/cart-item.tsx`
- **THEN** the cache SHALL be invalidated with reason `diff-touches-scope`
- **AND** `design-fidelity` SHALL run fully

#### Scenario: Cache use cap reached
- **WHEN** `spec_verify` has policy `"cached"` and has been cached for 2 consecutive retries
- **AND** a 3rd retry is triggered
- **THEN** the cache SHALL be invalidated with reason `cache-use-cap-reached`
- **AND** `spec_verify` SHALL run fully
- **AND** the `max_consecutive_cache_uses` counter for this change+gate resets to 0 on this run

#### Scenario: New API surface invalidates cache
- **WHEN** `review` has policy `"cached"`
- **AND** the retry commit adds a new exported function in `src/server/**/*.ts` (detected via `git diff --unified=0` scan for `^\+export (async )?function` or `^\+export const .* = async`)
- **THEN** the cache SHALL be invalidated with reason `new-api-surface-detected`
- **AND** `review` SHALL run fully

### Requirement: Scoped policy shards gate by retry diff
A gate with `policy="scoped"` SHALL execute on a filtered subset of its usual scope determined by the retry diff's touched files and their import graph.

The profile SHALL declare `gate_scope_filter(gate_name, retry_diff_files) -> list[str] | None` returning an ordered list of "scope tokens" (interpretation is gate-specific) or `None` meaning "no overlap — treat as cached".

For the web module's `e2e` gate, the scope tokens are Playwright test files (`tests/e2e/*.spec.ts`). The filter SHALL return the union of:
- Test files whose corresponding `src/app/**` pages transitively import any file in the retry diff (compute via `src` import graph or a simpler file-co-location heuristic).
- Test files whose file path shares a domain label with a diff file (e.g., `tests/e2e/cart.spec.ts` + `src/app/**/kosar/**`).

The gate SHALL then run only the filtered tests (e.g., Playwright `--grep-file` or explicit test-path args). The `VERIFY_GATE` event SHALL record the filter result in a new field `scoped_subset: {gate_name: [tokens]}`.

If the filter returns `None` (no overlap), the gate SHALL behave like `policy="cached"` for that retry.

#### Scenario: e2e scoped to affected test files
- **WHEN** `e2e` has policy `"scoped"` and the retry commit touches `src/app/[locale]/(shop)/kosar/page.tsx`
- **AND** `gate_scope_filter("e2e", [...])` returns `["tests/e2e/cart.spec.ts"]`
- **THEN** Playwright SHALL execute only `tests/e2e/cart.spec.ts`
- **AND** the `VERIFY_GATE` event SHALL include `scoped_subset: {"e2e": ["tests/e2e/cart.spec.ts"]}`
- **AND** gate wall time SHALL be a fraction of a full-suite run

#### Scenario: e2e no overlap falls through to cached
- **WHEN** `e2e` has policy `"scoped"` and the retry commit touches only `docs/*.md`
- **AND** `gate_scope_filter("e2e", [...])` returns `None`
- **THEN** the gate SHALL reuse the prior `e2e` verdict (cached) and emit `GATE_CACHED`
- **AND** Playwright SHALL NOT be invoked

#### Scenario: Scoped filter still subject to cache-use cap
- **WHEN** `e2e` has policy `"scoped"` and has been scoped-filtered for 2 consecutive retries
- **AND** a 3rd retry is triggered
- **THEN** the gate SHALL run the FULL Playwright suite (cap forces full re-run)

### Requirement: State schema for retry policy tracking
`orchestration-state.json`'s per-change dict SHALL gain a `gate_retry_tracking: dict[str, GateRetryEntry]` field where `GateRetryEntry = {consecutive_cache_uses: int, last_verdict_sha: str | None, last_run_retry_index: int | None}` keyed by gate name. Default `{}`. Backwards-compatible with old states lacking the field.

#### Scenario: First-ever retry initialises tracking
- **WHEN** a change's first retry runs and `gate_retry_tracking` was `{}`
- **THEN** after the verify pipeline runs, `gate_retry_tracking` SHALL have entries for every executed gate
- **AND** each entry's `consecutive_cache_uses` SHALL be `0` initially

#### Scenario: Cache reuse increments counter
- **WHEN** a gate is cached on retry N
- **THEN** `gate_retry_tracking[gate_name].consecutive_cache_uses` SHALL increment by 1

#### Scenario: Full re-run resets counter
- **WHEN** a gate runs fully (not cached/scoped-filtered to empty)
- **THEN** `gate_retry_tracking[gate_name].consecutive_cache_uses` SHALL reset to 0
- **AND** `last_verdict_sha` SHALL be updated to the new verdict's SHA

### Requirement: Retry prompt references cached verdicts
When gates are cached on a retry, the structured retry prompt (see `gate-retry-context`) SHALL include a "Cached Gates" section listing each cached gate and the SHA of its reused verdict. This allows the agent to understand that its prior work on those gates is still considered valid and not rediscover it.

#### Scenario: Retry prompt lists cached gates
- **WHEN** a retry is dispatched with `review` and `design-fidelity` cached but `spec_verify` run
- **THEN** the retry prompt SHALL contain a section `## Cached Gates` listing:
  - `review (cached from <sha>)`
  - `design-fidelity (cached from <sha>)`
- **AND** `spec_verify` SHALL NOT appear in that section
