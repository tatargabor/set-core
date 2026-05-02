## ADDED Requirements

### Requirement: Phase 1 brief prompt forbids test-only domains

The Phase 1 brief prompt (rendered by `render_brief_prompt` in `lib/set_orch/templates.py`) SHALL include a "DOMAIN ENUMERATION RULES" block that instructs the LLM to populate `domain_priorities` with feature/code domains only, and explicitly forbids the domain-name tokens `testing`, `tests`, `e2e`, `playwright`, `vitest`, `qa`, `validation`. The prompt SHALL further instruct that test requirements (e2e specs, unit tests) belong in the feature domain that owns the code under test, and that the only allowed test-related cross-cutting change is `test-infrastructure-setup`.

#### Scenario: Phase 1 prompt enumerates the forbidden tokens

- **GIVEN** the planner calls `render_brief_prompt(...)` for any spec
- **WHEN** the rendered prompt string is inspected
- **THEN** it contains the literal phrase `DOMAIN ENUMERATION RULES`
- **AND** it lists `testing`, `tests`, `e2e`, `playwright`, `vitest`, `qa`, `validation` as forbidden tokens
- **AND** it names `test-infrastructure-setup` as the singleton allowed cross-cutting test-related change

#### Scenario: Phase 1 prompt instructs feature-domain test ownership

- **GIVEN** the rendered Phase 1 prompt
- **WHEN** the prompt's task instructions are inspected
- **THEN** the prompt explicitly states that test requirements belong to the feature domain that owns the code under test (not a separate `testing` domain)

### Requirement: Phase 2 per-domain prompt requires e2e ownership in feature changes

The Phase 2 per-domain decompose prompt (rendered by `render_domain_decompose_prompt`) SHALL include in its `## Constraints` block an explicit rule stating that each change in the output `changes[]` array which adds user-facing UI or HTTP routes MUST own at least one e2e spec file in `spec_files`, and the change's `scope` text MUST mention the spec file path the implementing agent will create.

#### Scenario: Phase 2 prompt names the e2e ownership constraint

- **GIVEN** the planner calls `render_domain_decompose_prompt(...)` for any feature domain
- **WHEN** the rendered prompt string is inspected
- **THEN** the `## Constraints` section contains an instruction that user-facing changes MUST list an e2e spec file in `spec_files`
- **AND** the instruction names the path pattern `tests/e2e/<feature>.spec.ts`

### Requirement: Phase 3 merge prompt refolds standalone test changes

The Phase 3 merge prompt (rendered by `render_merge_prompt`) SHALL include in its `## Rules` block an instruction that any incoming change name matching `^(playwright|e2e|vitest)-` AND not equal to `test-infrastructure-setup` MUST be refolded — its `requirements`, `spec_files`, and `also_affects_reqs` MUST be merged into the corresponding feature change rather than emitting a standalone test-only change.

#### Scenario: Phase 3 prompt names the refold rule

- **GIVEN** the planner calls `render_merge_prompt(...)` with any domain plans
- **WHEN** the rendered prompt string is inspected
- **THEN** the `## Rules` section contains an instruction to refold standalone `playwright-*`/`e2e-*`/`vitest-*` changes into feature changes
- **AND** the rule names `test-infrastructure-setup` as the singleton exception

### Requirement: Post-Phase-3 fail-fast guard rejects standalone test changes

After the `decompose_merge` LLM call returns, before plan persistence, `_try_domain_parallel_decompose` (or its caller in `lib/set_orch/planner.py`) SHALL inspect every change in the parsed plan. For any change whose `name` field matches the regex `^(playwright|e2e|vitest)-` AND is not exactly `test-infrastructure-setup`, the planner MUST raise `RuntimeError` with a message naming the violating change and pointing at this capability spec. The plan MUST NOT be persisted on violation.

#### Scenario: Standalone playwright change triggers fail-fast

- **GIVEN** Phase 3 returns a plan containing a change named `playwright-smoke-tests`
- **WHEN** the planner runs the post-merge guard
- **THEN** a `RuntimeError` is raised
- **AND** the error message names `playwright-smoke-tests` as the violating change
- **AND** the message references `decompose-test-bundling`
- **AND** the plan is not written to disk

#### Scenario: Singleton test-infrastructure-setup is allowed

- **GIVEN** Phase 3 returns a plan containing exactly one change named `test-infrastructure-setup`
- **WHEN** the planner runs the post-merge guard
- **THEN** no error is raised
- **AND** the plan persistence proceeds normally

#### Scenario: Feature changes with bundled e2e specs pass

- **GIVEN** Phase 3 returns a plan whose changes are `content-home-page`, `content-blog-list`, `command-palette` (each with their own `tests/e2e/<feature>.spec.ts` in `spec_files`)
- **WHEN** the planner runs the post-merge guard
- **THEN** no error is raised
- **AND** the plan persistence proceeds normally

#### Scenario: Mixed-prefix violation triggers fail-fast

- **GIVEN** Phase 3 returns a plan containing both `vitest-validation-suite` and a feature change `auth-login`
- **WHEN** the guard runs
- **THEN** a `RuntimeError` is raised naming `vitest-validation-suite`

### Requirement: Flat decompose path is unaffected

Changes to the domain-parallel pipeline MUST NOT modify `render_planning_prompt` (the flat decompose path), the digest module, any gate executor, the dispatcher, or any consumer-deployed file. The flat path's `_PLANNING_RULES` already enforces the bundling invariant correctly; this change propagates the same invariant through the 3-phase pipeline without touching the flat path.

#### Scenario: Flat planner output unchanged

- **GIVEN** a spec with `req_count` below the domain-parallel threshold OR `planner.force_strategy: flat`
- **WHEN** the planner runs and emits a plan
- **THEN** the plan generation goes through `render_planning_prompt` exactly as before this change
- **AND** the post-Phase-3 guard does NOT execute (it is gated to the domain-parallel return path only)
