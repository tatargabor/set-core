## ADDED Requirements

### Requirement: planner prompt instructs foundational changes to use opus

`lib/set_orch/templates.py::render_brief_prompt` SHALL contain model-selection guidance that explicitly groups `foundational` with `feature` for opus assignment, and explicitly lists only `infrastructure`, `schema`, `cleanup-before`, `cleanup-after` as candidates for sonnet. The same guidance SHALL appear in any other prompt template (`render_planning_prompt`, `render_domain_decompose_prompt`, `render_merge_prompt`) that mentions model selection.

The previous instruction "use opus for feature changes, sonnet for infrastructure / cleanup / docs / refactor changes" SHALL be replaced. The replacement SHALL include a "when unsure, prefer opus" guidance for ambiguous cases.

#### Scenario: render_brief_prompt instructs foundational uses opus
- **WHEN** `render_brief_prompt(...)` is rendered with any input
- **THEN** the output contains a phrase tying `foundational` to `opus` (e.g. "opus for feature AND foundational" or "foundational changes use opus")

#### Scenario: render_brief_prompt does not say foundational uses sonnet
- **WHEN** `render_brief_prompt(...)` is rendered
- **THEN** the output does NOT contain text suggesting `foundational` should use `sonnet`

#### Scenario: render_brief_prompt names the sonnet-allowed change_types explicitly
- **WHEN** `render_brief_prompt(...)` is rendered
- **THEN** the output identifies the change_types that may use sonnet: `infrastructure`, `schema`, `cleanup-before`, `cleanup-after` (each MUST appear)

#### Scenario: render_brief_prompt advises opus when unsure
- **WHEN** `render_brief_prompt(...)` is rendered
- **THEN** the output contains a phrase advising opus as the safe default for ambiguous cases

#### Scenario: render_domain_decompose_prompt also reflects foundational→opus
- **WHEN** `render_domain_decompose_prompt(...)` is rendered
- **THEN** if the prompt body mentions model selection, it does NOT instruct foundational changes to use sonnet
