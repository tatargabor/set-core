## ADDED Requirements

### Requirement: Triage template generation
After digest completes and `ambiguities.json` contains one or more entries, the system SHALL generate `triage.md` in `wt/orchestration/digest/`. The template SHALL contain one section per ambiguity with pre-filled ID, type, source, description, and empty `**Decision:**` and `**Note:**` fields.

#### Scenario: Triage template generated after digest
- **WHEN** digest completes with 5 ambiguities detected
- **THEN** `wt/orchestration/digest/triage.md` is created
- **AND** contains 5 sections, each with `### AMB-NNN [type]`, description, `**Decision:**` (blank), and `**Note:**` (blank)

#### Scenario: No triage template when zero ambiguities
- **WHEN** digest completes with 0 ambiguities
- **THEN** no `triage.md` is generated
- **AND** the pipeline proceeds without any triage gate

#### Scenario: Triage template includes instructions header
- **WHEN** `triage.md` is generated
- **THEN** the file starts with a header explaining the three valid decisions (`fix`, `defer`, `ignore`) and how to fill in the template

#### Scenario: Triage template preserves existing decisions on re-digest
- **WHEN** re-digest runs and `triage.md` already exists with decisions filled in
- **AND** ambiguity AMB-002 still exists in the new digest
- **THEN** AMB-002 retains its existing `**Decision:**` and `**Note:**` values in the regenerated `triage.md`

#### Scenario: Removed ambiguities marked in triage template
- **WHEN** re-digest runs and ambiguity AMB-005 no longer exists in the new digest
- **THEN** AMB-005's section in `triage.md` is kept but marked with `[REMOVED]` after the ID

#### Scenario: New ambiguities appended to triage template
- **WHEN** re-digest finds a new ambiguity AMB-008 not present in existing `triage.md`
- **THEN** AMB-008 is appended as a new section with blank decision and note

### Requirement: Triage soft gate before planning
When `set-orchestrate plan` runs in digest mode and ambiguities exist, the system SHALL check triage status before proceeding to planner prompt construction.

#### Scenario: Gate generates triage and pauses on first run
- **WHEN** `set-orchestrate plan` runs in digest mode
- **AND** `ambiguities.json` has entries but `triage.md` does not exist
- **THEN** the system generates `triage.md`, prints a summary of ambiguities, and exits with code 0 and message: "Triage required. Review wt/orchestration/digest/triage.md, then re-run plan."

#### Scenario: Gate pauses on untriaged items
- **WHEN** `set-orchestrate plan` runs
- **AND** `triage.md` exists but 3 of 16 ambiguities have blank `**Decision:**` fields
- **THEN** the system prints "3 untriaged ambiguities remain. Review triage.md." and exits with code 0

#### Scenario: Gate passes when all items triaged
- **WHEN** `set-orchestrate plan` runs
- **AND** all ambiguities in `triage.md` have valid decisions (`fix`, `defer`, or `ignore`)
- **THEN** the system merges decisions into `ambiguities.json` and proceeds with planning

#### Scenario: Gate blocks on fix items
- **WHEN** all items are triaged but 2 have `**Decision:** fix`
- **THEN** the system prints "2 ambiguities marked 'fix' — update specs and re-run digest." and exits with code 0
- **AND** does NOT proceed with planning

#### Scenario: Gate auto-defers in automated mode
- **WHEN** `set-orchestrate start` triggers planning (automated orchestration)
- **AND** `triage.md` does not exist or has untriaged items
- **THEN** the system treats all untriaged items as `defer` and proceeds without pausing
- **AND** sets `resolved_by: "auto"` on auto-deferred items

### Requirement: Triage decision parsing
The system SHALL parse `triage.md` to extract decisions and notes per ambiguity ID.

#### Scenario: Valid decision parsed
- **WHEN** `triage.md` contains `**Decision:** defer` under `### AMB-003`
- **THEN** the parser returns `{id: "AMB-003", decision: "defer"}`

#### Scenario: Note field parsed
- **WHEN** `triage.md` contains `**Note:** Will sum quantities on merge` under `### AMB-003`
- **THEN** the parser returns the note text alongside the decision

#### Scenario: Invalid decision rejected
- **WHEN** `triage.md` contains `**Decision:** maybe` under `### AMB-003`
- **THEN** the parser treats AMB-003 as untriaged (blank) and warns the user

#### Scenario: Removed items skipped
- **WHEN** `triage.md` contains `### AMB-005 [REMOVED]`
- **THEN** the parser skips AMB-005 entirely

### Requirement: Resolution tracking in ambiguities.json
After triage is processed, the system SHALL add `resolution`, `resolution_note`, and `resolved_by` fields to each entry in `ambiguities.json`.

#### Scenario: Triage decisions merged into ambiguities.json
- **WHEN** gate passes with all items triaged
- **THEN** each ambiguity in `ambiguities.json` gets `resolution` (`fixed`/`deferred`/`ignored`), `resolution_note` (from triage note), and `resolved_by: "triage"`

#### Scenario: Auto-deferred items tracked
- **WHEN** automated mode auto-defers untriaged items
- **THEN** `ambiguities.json` entries get `resolution: "deferred"`, `resolution_note: ""`, `resolved_by: "auto"`

#### Scenario: Planner resolutions merged back
- **WHEN** planner output contains `resolved_ambiguities` in a change definition
- **THEN** the matching ambiguity in `ambiguities.json` gets `resolution: "planner-resolved"`, `resolution_note` from the planner, and `resolved_by: "planner"`

### Requirement: Planner receives only deferred ambiguities
The planner prompt SHALL include only ambiguities with `resolution: "deferred"`. Items marked `fixed` or `ignored` SHALL be excluded.

#### Scenario: Deferred ambiguities in planner prompt
- **WHEN** triage has 3 `defer`, 2 `ignore`, 1 `fix` (fix already handled by re-digest)
- **THEN** planner prompt includes only the 3 deferred ambiguities

#### Scenario: Planner instructed to resolve deferred items
- **WHEN** deferred ambiguities are included in planner prompt
- **THEN** the prompt instructs: "For each deferred ambiguity, include a `resolved_ambiguities` entry in the change that addresses the affected requirements. Specify your decision and rationale."

#### Scenario: No ambiguity section when all resolved
- **WHEN** all ambiguities are `fixed` or `ignored` (none deferred)
- **THEN** no ambiguity section is included in the planner prompt

### Requirement: Planner output schema extension
The plan output schema SHALL accept an optional `resolved_ambiguities` array in each change object.

#### Scenario: Change with resolved ambiguity
- **WHEN** planner output for change `cart-management` includes `"resolved_ambiguities": [{"id": "AMB-003", "resolution_note": "Sum quantities on cart merge"}]`
- **THEN** the plan parser accepts the field and stores it

#### Scenario: Change without resolved ambiguities
- **WHEN** planner output for a change does not include `resolved_ambiguities`
- **THEN** the plan parser treats it as an empty array (no error)
