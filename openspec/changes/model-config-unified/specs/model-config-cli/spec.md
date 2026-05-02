## ADDED Requirements

### Requirement: per-role CLI flags expose every model

The CLI SHALL expose flags that map to each role in the `models:` block:

- `--agent-model <name>` (alias kept: `--default-model` for backwards compat)
- `--digest-model <name>`
- `--decompose-brief-model <name>`
- `--decompose-domain-model <name>`
- `--decompose-merge-model <name>`
- `--review-model <name>`
- `--review-escalation-model <name>`
- `--spec-verify-model <name>`
- `--spec-verify-escalation-model <name>`
- `--classifier-model <name>`
- `--supervisor-model <name>`
- `--canary-model <name>`
- `--agent-small-model <name>`

Each flag SHALL accept any short model name in the validation regex. Each subcommand SHALL register the subset of flags relevant to its operation (e.g. `engine monitor` registers all roles; `digest run` registers `--digest-model`; `chat` registers `--agent-model` only). Generic flags (`--agent-model`, `--default-model`) SHALL be accepted by every subcommand that runs claude code.

#### Scenario: --agent-model overrides DIRECTIVE_DEFAULTS
- **WHEN** the CLI is invoked with `--agent-model opus-4-7` and no other override
- **THEN** `resolve_model("agent", cli_override=args.agent_model)` returns `"opus-4-7"`

#### Scenario: --default-model is accepted as alias for --agent-model
- **WHEN** the CLI is invoked with `--default-model opus-4-7`
- **THEN** the parsed args populate `args.agent_model = "opus-4-7"` (or the resolution code reads either)

#### Scenario: invalid flag value is rejected at argparse time
- **WHEN** the CLI is invoked with `--agent-model not-a-real-model`
- **THEN** argparse raises a clear error naming the invalid value (using a `choices=` or custom validator)

### Requirement: --model-profile preset shortcut sets all roles

The CLI SHALL accept `--model-profile <preset>` where `<preset>` is one of `default`, `all-opus-4-6`, `all-opus-4-7`, `cost-optimized`. When supplied, the preset SHALL pre-populate every role with the preset's mapping; individual `--<role>-model` flags supplied alongside SHALL override on top of the preset.

Preset definitions:
- `default` — values from DIRECTIVE_DEFAULTS as-is
- `all-opus-4-6` — every role → `opus-4-6`
- `all-opus-4-7` — every role → `opus-4-7`
- `cost-optimized` — agent / digest / decompose_* / supervisor / canary → `sonnet`; review / spec_verify / classifier → `haiku`; review_escalation / spec_verify_escalation / trigger.* → `sonnet`

#### Scenario: all-opus-4-6 preset sets every role to opus-4-6
- **WHEN** `--model-profile all-opus-4-6` is supplied with no individual overrides
- **THEN** `resolve_model("agent")`, `resolve_model("digest")`, `resolve_model("review")`, `resolve_model("classifier")`, etc. all return `"opus-4-6"`

#### Scenario: per-role flag overrides preset
- **WHEN** `--model-profile cost-optimized --review-model opus-4-6` is supplied
- **THEN** `resolve_model("review")` returns `"opus-4-6"` (the per-role flag wins)
- **AND** `resolve_model("agent")` returns `"sonnet"` (the preset value)

#### Scenario: invalid preset name is rejected
- **WHEN** `--model-profile not-a-real-preset` is supplied
- **THEN** argparse raises a clear error listing the valid preset names

### Requirement: ENV vars cover every role

For every CLI flag, an environment variable of the form `SET_ORCH_MODEL_<ROLE_UPPER>` SHALL provide an alternate way to set the value. The role-name-to-env-var transformation SHALL replace dots with underscores and uppercase: `agent` → `SET_ORCH_MODEL_AGENT`; `trigger.integration_failed` → `SET_ORCH_MODEL_TRIGGER_INTEGRATION_FAILED`.

#### Scenario: ENV var reading covers all standard roles
- **WHEN** ENV vars `SET_ORCH_MODEL_AGENT`, `SET_ORCH_MODEL_DIGEST`, `SET_ORCH_MODEL_REVIEW`, etc. are set to valid model names
- **THEN** each `resolve_model(<role>)` call returns the corresponding ENV value (no CLI override)
