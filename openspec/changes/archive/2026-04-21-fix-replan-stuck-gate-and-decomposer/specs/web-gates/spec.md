## ADDED Requirements

### Requirement: i18n_check is a hard-fail gate
The `i18n_check` gate SHALL block verify-gate success on failure, not warn. Prior behavior (to be removed): every `VERIFY_GATE` event on `craftbrew-run-20260418-1719::promotions-engine` showed `i18n_check: warn-fail` with no effect on gate pass/fail.

The gate SHALL return one of `pass`, `fail`, `skipped` (no `warn-fail`). When it returns `fail`, the verify pipeline SHALL short-circuit with `stop_gate=i18n_check` and surface the missing/mismatched keys to the retry agent.

#### Scenario: Missing Hungarian translation key fails gate
- **WHEN** a `.tsx` file uses `t("cart.checkout.cta")` but `messages/hu.json` has no `cart.checkout.cta` key
- **THEN** `i18n_check` SHALL return `fail`
- **AND** the `VERIFY_GATE` event SHALL have `stop_gate="i18n_check"` and `i18n_check="fail"`
- **AND** the retry agent's context SHALL list the missing keys with file:line pointers

#### Scenario: Both locales match
- **WHEN** every `t(...)` call has a corresponding key in both `messages/hu.json` and `messages/en.json`
- **THEN** `i18n_check` SHALL return `pass`

### Requirement: spec_verify and review run in parallel
The verify pipeline SHALL run `spec_verify` and `review` gates concurrently when both are in the active gate set, because they do not depend on each other's output. Total wall time for these two gates SHOULD approach `max(spec_verify_ms, review_ms)` rather than their sum; actual latency is subject to external model-API response time and is not contractually bounded.

Prior behavior (sequential): first-time gate passes on large changes routinely exceeded the sum of both gates' sequential cost (observed ~8 minutes for `spec_verify + review` in the field).

#### Scenario: Parallel execution records both gate_ms
- **WHEN** both gates are active
- **THEN** `gate_ms.spec_verify` and `gate_ms.review` SHALL both be recorded in the `VERIFY_GATE` event
- **AND** the event SHALL include a `parallel_group: ["spec_verify", "review"]` field when parallel execution was used

#### Scenario: Both gates allowed to complete; stop_gate is earliest by order
- **WHEN** `spec_verify` returns `fail` while `review` is still running
- **THEN** `review` SHALL be allowed to complete and its verdict AND findings SHALL be recorded in the `VERIFY_GATE` event
- **AND** the overall `stop_gate` SHALL be the earliest-ordered failing gate per the profile's `gate_order` (typically `spec_verify`)
- **AND** review findings SHALL be surfaced to the retry agent's context even though `spec_verify` is the reported `stop_gate`, so the agent can fix both in one retry iteration

### Requirement: Web profile exposes gate tuning hooks
The `WebProjectType` SHALL expose `parallel_gate_groups() -> list[set[str]]` returning `[{"spec_verify", "review"}]` by default so other profiles can opt in to parallelisation. Core profile SHALL return `[]` (no parallelisation) by default.

#### Scenario: Web profile default groups
- **WHEN** `WebProjectType().parallel_gate_groups()` is called
- **THEN** it SHALL return `[{"spec_verify", "review"}]`
