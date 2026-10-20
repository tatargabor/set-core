## ADDED Requirements

### Requirement: domain decompose prompt requires explicit change_type assignment

`lib/set_orch/templates.py::render_domain_decompose_prompt` SHALL emit a textual instruction in its `## Constraints` block that requires every emitted change to set `change_type` to one of `infrastructure | schema | foundational | feature | cleanup-before | cleanup-after`. The instruction SHALL state that the dispatcher's per-change model routing reads this field, so it must not be omitted.

#### Scenario: rendered prompt names every change_type value
- **WHEN** `render_domain_decompose_prompt(...)` is invoked with any input
- **THEN** the rendered prompt body contains each of the six values: `infrastructure`, `schema`, `foundational`, `feature`, `cleanup-before`, `cleanup-after`

#### Scenario: rendered prompt asserts change_type is required
- **WHEN** `render_domain_decompose_prompt(...)` is invoked
- **THEN** the rendered prompt body contains the substring `change_type` AND a phrase indicating it is mandatory (e.g. "MUST set", "required", "must be one of")

#### Scenario: rendered prompt explains why change_type matters
- **WHEN** `render_domain_decompose_prompt(...)` is invoked
- **THEN** the rendered prompt body explains that downstream model routing uses the field, so the LLM understands the cost of dropping it
