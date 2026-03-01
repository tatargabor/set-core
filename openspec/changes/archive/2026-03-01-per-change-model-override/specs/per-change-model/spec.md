## ADDED Requirements

### Requirement: Plan JSON model field
Each change in the plan JSON MAY include a `model` field specifying the Claude model to use for implementation. Valid values SHALL be `"opus"`, `"sonnet"`, or `"haiku"`. When not specified, the field SHALL default to `null`.

#### Scenario: Plan with explicit model
- **WHEN** a plan JSON contains `{"name": "doc-sync-ui", "model": "sonnet", ...}`
- **THEN** `init_state()` SHALL carry the `model` field into the state JSON for that change

#### Scenario: Plan without model field
- **WHEN** a plan JSON change has no `model` field
- **THEN** `init_state()` SHALL set `model` to `null` in the state JSON

### Requirement: Default model directive
The directives block SHALL support a `default_model` field specifying the global model for implementation work. Default value SHALL be `"opus"`.

#### Scenario: Directive sets default_model
- **WHEN** directives contain `"default_model": "sonnet"`
- **THEN** all changes without explicit `model` override SHALL use sonnet

#### Scenario: No default_model directive
- **WHEN** directives do not contain `default_model`
- **THEN** the default SHALL be `"opus"`

### Requirement: Model resolution chain
The effective model for a change SHALL be resolved in this order:
1. Per-change `model` field from state JSON (if not null)
2. `default_model` from directives (if set)
3. Complexity-based heuristic

The heuristic SHALL map: S-complexity changes with `change_type` in `["cleanup-before", "cleanup-after"]` → `"sonnet"`. All other combinations → `"opus"`.

#### Scenario: Explicit model wins over directive
- **WHEN** a change has `"model": "haiku"` and directive has `"default_model": "opus"`
- **THEN** the effective model SHALL be `"haiku"`

#### Scenario: Directive wins over heuristic
- **WHEN** a change has `model: null`, directive has `"default_model": "sonnet"`, and the change is L-complexity feature
- **THEN** the effective model SHALL be `"sonnet"` (directive overrides heuristic)

#### Scenario: Heuristic fallback for S cleanup
- **WHEN** a change has `model: null`, no `default_model` directive, complexity `"S"`, change_type `"cleanup-after"`
- **THEN** the effective model SHALL be `"sonnet"`

#### Scenario: Heuristic fallback for M feature
- **WHEN** a change has `model: null`, no `default_model` directive, complexity `"M"`, change_type `"feature"`
- **THEN** the effective model SHALL be `"opus"`

### Requirement: Dispatch and resume use effective model
`dispatch_change()` and `resume_change()` SHALL pass the resolved effective model to `wt-loop start` via the `--model` flag instead of hardcoding `opus`.

#### Scenario: Dispatch with per-change sonnet
- **WHEN** dispatching a change with effective model `"sonnet"`
- **THEN** `wt-loop start` SHALL be called with `--model sonnet`

#### Scenario: Resume preserves model
- **WHEN** resuming a change (retry after verify failure)
- **THEN** the same effective model resolution SHALL apply (not hardcoded opus)

### Requirement: Documentation updates
`docs/plan-checklist.md` SHALL include a checklist item for model selection. `docs/planning-guide.md` SHALL include a section explaining model selection strategy and cost implications.

#### Scenario: Checklist includes model item
- **WHEN** a user reviews the plan checklist
- **THEN** they SHALL see guidance on choosing models per change (e.g., sonnet for S/cleanup, opus for complex features)
