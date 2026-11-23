## ADDED Requirements

### Requirement: ui-primitive-skew detection phase

The fidelity gate's `run_skeleton_check` SHALL include a `ui-primitive-skew` phase that runs BEFORE the existing shell-mount and shell-shadow phases. For each `*.tsx` file under `v0-export/components/ui/`, the phase SHALL:

1. Locate the corresponding `src/components/ui/<same-relpath>.tsx` in the agent worktree.
2. Extract the set of top-level exported component names from each file (regex over `export {…}`, `export const`, `export function`, `export default`).
3. For each shared exported name, compare the structural signature of the component's first parameter (Props) — the set of declared field names and their optionality.
4. Emit a `ui-primitive-skew` violation when:
   - An exported name exists in v0 but not in project (missing primitive export), OR
   - The project's Props field set is a strict subset of v0's (a field declared in v0 is absent in project).

The violation MUST include the file path, the exported name, and the specific missing field(s) or export(s).

#### Scenario: Missing prop on shared primitive triggers skew

- **GIVEN** `v0-export/components/ui/command.tsx` exports `CommandDialog` whose Props type declares `title?: string` and `description?: string`
- **AND** `src/components/ui/command.tsx` exports `CommandDialog` whose Props type omits both fields
- **WHEN** the `ui-primitive-skew` phase runs
- **THEN** a `ui-primitive-skew` violation is emitted naming `components/ui/command.tsx`, export `CommandDialog`, missing fields `title`, `description`

#### Scenario: Project Props superset of v0 does not trigger skew

- **GIVEN** v0's `CommandDialog` Props declares `title?`, `description?`
- **AND** the project's `CommandDialog` Props declares `title?`, `description?`, `theme?`
- **WHEN** the phase runs
- **THEN** no `ui-primitive-skew` violation is emitted (project is wider; allowed)

#### Scenario: Identical signatures do not trigger skew

- **GIVEN** v0 and project `Button` Props have the same field set with the same optionality
- **WHEN** the phase runs
- **THEN** no violation emitted regardless of cosmetic file differences (whitespace, import order, comments)

#### Scenario: Project-only primitive does not trigger skew

- **GIVEN** `src/components/ui/payment-card.tsx` exists with no v0 counterpart
- **WHEN** the phase runs
- **THEN** the file is ignored (skew check is v0-driven; project-only primitives are out of scope)

### Requirement: ui-primitive-skew is blocking by default

`ui-primitive-skew` violations SHALL be blocking (gate result FAIL, retry triggered) by default. The retry context SHALL name `set-design-import` (or `--regenerate-manifest`) as the canonical remediation, NOT instruct the agent to hand-edit primitive types.

#### Scenario: Blocking violation triggers retry with import-based remediation

- **GIVEN** the phase emits a `ui-primitive-skew` violation
- **WHEN** the gate evaluates the result
- **THEN** the gate result is FAIL
- **AND** the `retry_context` written to the journal references `set-design-import` as the fix path
- **AND** the `retry_context` does NOT instruct the agent to manually extend `src/components/ui/<file>.tsx` types

### Requirement: ui-primitive-skew downgrades to warning when sync_ui is disabled

When `orchestration.yaml` has `design_import.sync_ui: false`, the `ui-primitive-skew` phase MUST emit findings as non-blocking warnings (gate result PASS-with-warning, merge proceeds, no retry). The warning text MUST still name the missing fields so operators can act on the drift if desired.

#### Scenario: sync_ui=false downgrades skew to warning

- **GIVEN** `orchestration.yaml` contains `design_import:\n  sync_ui: false`
- **AND** v0's `CommandDialog` Props has fields the project's `CommandDialog` Props lacks
- **WHEN** the gate runs
- **THEN** the `ui-primitive-skew` finding is logged as WARN
- **AND** the gate result is PASS (or PASS-with-warning) and merge proceeds
- **AND** the missing field names appear in the gate output

### Requirement: Phase ordering — skew before shell-not-mounted

The `ui-primitive-skew` phase SHALL execute before the `shell-not-mounted` and `missing-shared-file` phases of `run_skeleton_check`. When skew is detected and is blocking, the gate MAY short-circuit and skip subsequent phases, OR continue and report all findings — implementation choice. But the skew finding MUST appear first in any aggregated `retry_context` so the agent's actionable signal is the root cause, not a downstream symptom.

#### Scenario: Skew reported as primary cause when both skew and missing shell exist

- **GIVEN** v0 has `CommandDialog` with new props AND `v0-export/components/site-header.tsx` exists
- **AND** `src/components/ui/command.tsx` has older Props AND `src/components/site-header.tsx` does not exist
- **WHEN** the gate runs
- **THEN** the aggregated `retry_context` lists the `ui-primitive-skew` finding before any `missing-shared-file` or `shell-not-mounted` findings
