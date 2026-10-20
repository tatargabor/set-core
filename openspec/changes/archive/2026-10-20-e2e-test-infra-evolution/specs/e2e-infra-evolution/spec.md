# Capability: e2e-infra-evolution

## Purpose

Ensures agents discover, extend, and reuse a project's shared E2E test infrastructure during orchestrated changes, rather than reinventing helpers in each spec file.

## IN SCOPE
- Profile method for scanning existing test infrastructure
- Dispatch injection of test infra summary into agent input
- Planning rule template for the "scan → extend → use" workflow
- Web module implementation of test infra scanning
- Web template scaffold for helpers directory
- Scope check advisory for helper bypass detection

## OUT OF SCOPE
- Automatic helper generation from specs
- Blocking merges based on helper usage
- Prescribing a specific helper structure (projects decide their own)
- Non-web project type implementations (future modules add their own)

## ADDED Requirements

### Requirement: TEST-INFRA-PROFILE — Profile method for test infrastructure discovery

The `ProjectType` ABC SHALL define an abstract method `get_test_infra_summary(project_path: Path) -> dict` that returns a structured summary of the project's existing E2E test infrastructure. The return dict SHALL contain keys `helper_files` (list of relative paths), `fixture_dirs` (list of relative paths), and `patterns_detected` (list of descriptive strings). `CoreProfile` SHALL return an empty dict (no helpers known). `NullProfile` SHALL return an empty dict.

#### Scenario: Core profile returns empty summary
- **WHEN** `CoreProfile.get_test_infra_summary()` is called
- **THEN** it SHALL return `{"helper_files": [], "fixture_dirs": [], "patterns_detected": []}`

#### Scenario: Web profile scans Playwright helpers
- **WHEN** `WebProjectType.get_test_infra_summary()` is called on a project with `tests/e2e/helpers/ws-mock.ts` and `tests/e2e/helpers/seed-data.ts`
- **THEN** `helper_files` SHALL contain `["tests/e2e/helpers/ws-mock.ts", "tests/e2e/helpers/seed-data.ts"]`

#### Scenario: Web profile detects test patterns in spec files
- **WHEN** `WebProjectType.get_test_infra_summary()` is called on a project where `tests/e2e/*.spec.ts` files contain `routeWebSocket` calls
- **THEN** `patterns_detected` SHALL include a string mentioning WebSocket mock pattern

#### Scenario: Web profile detects test route pages
- **WHEN** the project has `app/__test/workspace/page.tsx`
- **THEN** `patterns_detected` SHALL include a string mentioning test route pages
- **AND** the paths SHALL appear in the summary

### Requirement: TEST-INFRA-DISPATCH — Dispatch injects test infra context

The dispatcher SHALL call `profile.get_test_infra_summary(project_path)` during input.md generation. If the result is non-empty (any list has entries), the dispatcher SHALL append an `## E2E Test Infrastructure` section to the agent's `input.md` containing the helper file list, fixture directories, and detected patterns.

#### Scenario: Non-empty test infra injected
- **WHEN** dispatch generates input.md for a change
- **AND** `get_test_infra_summary()` returns helpers and patterns
- **THEN** input.md SHALL contain an `## E2E Test Infrastructure` section listing the helpers and patterns

#### Scenario: Empty test infra omitted
- **WHEN** `get_test_infra_summary()` returns all empty lists
- **THEN** input.md SHALL NOT contain an `## E2E Test Infrastructure` section

### Requirement: TEST-INFRA-RULE — Planning rule for scan-extend-use workflow

A planning rule template SHALL exist at `templates/core/rules/e2e-infra-evolution.md` that instructs agents to: (1) read existing test helpers before writing E2E tests, (2) identify infrastructure gaps for their feature, (3) extend shared helpers with new utilities, (4) write E2E tests that use the shared helpers. This rule SHALL deploy to consumer projects via `set-project init`.

#### Scenario: Rule deploys to consumer project
- **WHEN** `set-project init` runs on a consumer project
- **THEN** `.claude/rules/e2e-infra-evolution.md` SHALL exist in the consumer project

### Requirement: TEST-INFRA-SCAFFOLD — Web template helpers directory

The web module template SHALL include a `tests/e2e/helpers/README.md` scaffold file that documents the shared helper convention. This file SHALL deploy to consumer projects on `set-project init --project-type web`.

#### Scenario: Helpers README deploys
- **WHEN** `set-project init --project-type web` runs
- **THEN** `tests/e2e/helpers/README.md` SHALL exist in the consumer project

### Requirement: TEST-INFRA-ADVISORY — Scope check helper usage warning

The `ProjectType` ABC SHALL define an optional method `check_test_infra_usage(changed_files: list[Path], project_path: Path) -> list[str]` returning warning strings. The verify pipeline's scope check step SHALL call this method and log any returned warnings as non-blocking advisories. `WebProjectType` SHALL implement this to detect when new `.spec.ts` files define inline helper functions that duplicate patterns available in `tests/e2e/helpers/`.

#### Scenario: Inline helper detected
- **WHEN** scope check runs on a change that added a `.spec.ts` file containing a function definition matching an existing helper pattern
- **THEN** `check_test_infra_usage()` SHALL return a warning string suggesting the helper be moved to `tests/e2e/helpers/`
- **AND** the warning SHALL be logged but SHALL NOT block the merge

#### Scenario: No inline helpers
- **WHEN** all new `.spec.ts` files import from `tests/e2e/helpers/`
- **THEN** `check_test_infra_usage()` SHALL return an empty list
