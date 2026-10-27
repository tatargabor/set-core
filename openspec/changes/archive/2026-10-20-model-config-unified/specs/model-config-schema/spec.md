## ADDED Requirements

### Requirement: orchestration directives expose a unified models block

`lib/set_orch/config.py::DIRECTIVE_DEFAULTS` SHALL include a top-level `models` key containing role-to-model mappings. Required keys: `agent`, `digest`, `decompose_brief`, `decompose_domain`, `decompose_merge`, `review`, `review_escalation`, `spec_verify`, `spec_verify_escalation`, `classifier`, `supervisor`, `canary`, `agent_small`, `trigger` (sub-dict). The `trigger` sub-dict SHALL include keys `integration_failed`, `non_periodic_checkpoint`, `terminal_state`, `default`. Each leaf value SHALL be a short model name validated against the existing model-name regex.

#### Scenario: DIRECTIVE_DEFAULTS contains a models block with all required keys
- **WHEN** `lib/set_orch/config.py` is imported and `DIRECTIVE_DEFAULTS["models"]` is read
- **THEN** the dict contains all 13 leaf keys (`agent`, `digest`, `decompose_brief`, `decompose_domain`, `decompose_merge`, `review`, `review_escalation`, `spec_verify`, `spec_verify_escalation`, `classifier`, `supervisor`, `canary`, `agent_small`) plus the `trigger` sub-dict with its 4 keys

#### Scenario: every default model name is a valid short name
- **WHEN** every leaf in `DIRECTIVE_DEFAULTS["models"]` (including trigger sub-dict values) is checked against the model-name regex `^(haiku|sonnet|opus|sonnet-1m|opus-1m|opus-4-6|opus-4-7|opus-4-6-1m|opus-4-7-1m)$`
- **THEN** every value matches

### Requirement: agent default is opus-4-6

The default value of `models.agent` SHALL be `"opus-4-6"`. This is a deliberate change from the prior `"opus"` (which aliases to `opus-4-7`).

#### Scenario: agent default resolves to opus-4-6
- **WHEN** no orchestration.yaml override and no CLI flag and no ENV var
- **THEN** `resolve_model("agent")` returns `"opus-4-6"`

#### Scenario: opus-4-6 short name maps to claude-opus-4-6
- **WHEN** `subprocess_utils._MODEL_MAP["opus-4-6"]` is read
- **THEN** the value is `"claude-opus-4-6"`

### Requirement: validator rejects invalid model names in models block

`lib/set_orch/config.py` SHALL validate every leaf in a user-supplied `models:` block against the model-name regex. Invalid values SHALL raise a configuration error naming the offending key and value.

#### Scenario: invalid agent value is rejected
- **WHEN** an orchestration.yaml contains `models.agent: gpt-4` (not in the supported set)
- **THEN** loading the directives raises a configuration error whose message names `models.agent` and `gpt-4`

#### Scenario: invalid trigger sub-key value is rejected
- **WHEN** an orchestration.yaml contains `models.trigger.integration_failed: invalid-name`
- **THEN** loading raises a configuration error naming `models.trigger.integration_failed`

### Requirement: legacy default_model directive remains backwards-compatible

When an orchestration.yaml supplies the legacy `default_model` directive but no `models.agent`, `resolve_model("agent")` SHALL return the legacy value with a one-shot DEPRECATION warning logged at WARNING level. The legacy `summarize_model` and `review_model` directives SHALL similarly continue to feed `digest` and `review` resolutions for backwards compatibility.

#### Scenario: legacy default_model is honored with deprecation warning
- **WHEN** orchestration.yaml has `default_model: opus-4-7` and no `models:` block
- **THEN** `resolve_model("agent")` returns `"opus-4-7"`
- **AND** a WARNING log record is emitted naming `default_model` as deprecated and pointing to `models.agent`

#### Scenario: explicit models.agent overrides legacy default_model
- **WHEN** orchestration.yaml has both `default_model: opus-4-7` and `models.agent: opus-4-6`
- **THEN** `resolve_model("agent")` returns `"opus-4-6"` (explicit wins, no deprecation warning required)
