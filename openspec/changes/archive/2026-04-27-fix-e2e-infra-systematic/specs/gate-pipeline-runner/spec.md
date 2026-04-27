## ADDED Requirements

### Requirement: Cross-change regression detection

When the integration gate in the merger detects a full-suite e2e failure, the engine SHALL parse the list of failing tests and resolve the owning change for each. If any failing test is owned by an ALREADY-MERGED change (different from the current change), the engine SHALL emit a `CROSS_CHANGE_REGRESSION` event and prepend a prescriptive block to the agent's redispatch `retry_context`, naming the affected already-merged features and directing the agent to fix the current change rather than modifying the already-merged code.

Owning-change resolution SHALL attempt, in order:
1. **Filename convention** — a test at `tests/e2e/<change>.spec.ts` is owned by change `<change>`.
2. **REQ-id tag** — a test body containing `@REQ-...` is owned by the change whose `requirements` list contains that REQ-id.
3. **Scope overlap** — a touched file in the current change's diff that overlaps with `merged_scope_files` of an already-merged change; the test run at that spec file is attributed to the overlapping merged change.

Unresolved ownership falls through as a generic failure (no event, no prescriptive framing). This is a safe default: worst case is the current baseline behavior.

At merge time, the merger SHALL populate `change.merged_scope_files` with the list of files the merge touched (from `git diff --name-only` of the merge commit), enabling path (3) lookups for future cross-change detection. Changes merged before this field existed SHALL be handled via forward-compat: path (3) is skipped for them.

#### Scenario: Failing test belongs to already-merged feature
- **GIVEN** current change `C` is being merged and the integration gate's full e2e fails with:
  - `tests/e2e/admin-products.spec.ts:127` failed
  - `tests/e2e/cart-and-session.spec.ts:102` failed
- **AND** changes `admin-products` and `cart-and-session` are both in state with `status=merged`
- **WHEN** the engine parses the failing tests
- **THEN** `resolve_owning_change` SHALL attribute both tests via filename convention to `admin-products` and `cart-and-session` respectively
- **AND** a `CROSS_CHANGE_REGRESSION` event SHALL be emitted with payload `{current_change: "C", regressed_tests: [{test: "tests/e2e/admin-products.spec.ts:127", owning_change: "admin-products"}, {test: "tests/e2e/cart-and-session.spec.ts:102", owning_change: "cart-and-session"}]}`

#### Scenario: Retry context includes prescriptive framing
- **GIVEN** a `CROSS_CHANGE_REGRESSION` was just emitted for current change `C` with 2 regressed tests from 2 distinct already-merged features
- **WHEN** the engine assembles the redispatch `retry_context`
- **THEN** the retry_context SHALL begin with a section headed "⚠ Cross-change regression"
- **AND** the section SHALL name each already-merged feature and list the tests it lost
- **AND** the section SHALL list the files in the current change's diff that overlap the already-merged features' scopes
- **AND** the section SHALL contain the directive: "Do NOT modify those features' code. Fix your change so it doesn't affect their surface."

#### Scenario: Own-change failing tests only — no regression event
- **GIVEN** the integration gate's full e2e fails with only tests owned by the current change
- **WHEN** the engine parses the failing tests
- **THEN** NO `CROSS_CHANGE_REGRESSION` event SHALL be emitted
- **AND** the normal retry_context SHALL be used (no prescriptive framing)

#### Scenario: Unresolved ownership falls through
- **GIVEN** a failing test that matches no file convention, has no REQ-id tag, and overlaps no merged scope
- **WHEN** the engine attempts resolution
- **THEN** the test SHALL be left attributed to "unknown"
- **AND** it SHALL NOT be counted as a cross-change regression
- **AND** baseline retry behavior SHALL apply

#### Scenario: Merger populates merged_scope_files at merge time
- **WHEN** a change `C` is merged by the merger
- **THEN** `change.merged_scope_files` SHALL be set to the list of files returned by `git diff --name-only` of the merge commit
- **AND** this list SHALL persist in orchestration state for later cross-change detection lookups

#### Scenario: Legacy merged change without merged_scope_files
- **GIVEN** an already-merged change from a run predating this change (no `merged_scope_files` field)
- **WHEN** `resolve_owning_change` runs for a failing test
- **THEN** resolution paths (1) and (2) SHALL still be attempted
- **AND** path (3) SHALL be skipped for that legacy change without error
- **AND** resolution SHALL succeed when paths (1) or (2) match
