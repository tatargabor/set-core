## ADDED Requirements

### Requirement: set-common.sh resolve_model_id supports --config and --role

`bin/set-common.sh::resolve_model_id` SHALL accept optional `--config <yaml-path>` and `--role <role>` flags. When both are supplied, the function SHALL read `models.<role>` (or nested `models.trigger.<sub>`) from the yaml and use the result as the short name to translate. When the yaml read returns nothing, the function SHALL fall back to the existing positional `<name|fallback>` argument.

The yaml read SHALL use a Python one-liner via `python3 -c` (project already requires Python 3.10+); shelling out to yq is not required.

#### Scenario: resolve_model_id reads yaml when --config and --role supplied
- **WHEN** `resolve_model_id --config /path/to/orchestration.yaml --role agent` is called and the yaml has `models.agent: opus-4-6`
- **THEN** stdout contains `claude-opus-4-6`

#### Scenario: resolve_model_id falls back to positional fallback when yaml unset
- **WHEN** `resolve_model_id --config /path/to/orchestration.yaml --role agent sonnet` is called and the yaml has no `models:` block
- **THEN** stdout contains `claude-sonnet-4-6` (the positional `sonnet` fallback)

#### Scenario: resolve_model_id without --config preserves legacy behavior
- **WHEN** `resolve_model_id opus` is called (no flags)
- **THEN** stdout contains `claude-opus-4-7` (the existing short-name → full-id behavior)

#### Scenario: invalid --role with valid config returns the positional fallback
- **WHEN** `resolve_model_id --config orch.yaml --role not-a-real-role haiku` is called
- **THEN** stdout contains `claude-haiku-4-5-20251001` (the positional fallback)

### Requirement: lib/orchestration shell scripts pass --config --role to resolve_model_id

`lib/orchestration/dispatcher.sh` and `lib/orchestration/digest.sh` SHALL invoke `resolve_model_id --config "$ORCH_YAML" --role <role>` for every model selection point that previously used a positional model fallback. The fallback positional argument SHALL still be supplied for compatibility when `$ORCH_YAML` is unavailable (e.g. environment-only invocations).

#### Scenario: dispatcher.sh uses resolve_model_id with role
- **WHEN** dispatcher.sh resolves the agent model for a change
- **THEN** the invocation includes `--config "$ORCH_YAML" --role agent` arguments before the positional fallback

#### Scenario: digest.sh uses resolve_model_id with role digest
- **WHEN** digest.sh resolves the model for digest API calls
- **THEN** the invocation includes `--config "$ORCH_YAML" --role digest` arguments before the positional fallback
