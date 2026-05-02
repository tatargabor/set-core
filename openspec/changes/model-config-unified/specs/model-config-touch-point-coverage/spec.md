## ADDED Requirements

### Requirement: every Python model literal is replaced by a resolve_model call

The Python source tree in `lib/set_orch/`, `modules/web/set_project_web/`, and `bin/` (Python entry points) SHALL contain zero hardcoded short-model-name string literals (`"opus"`, `"sonnet"`, `"haiku"`, `"opus-4-6"`, `"opus-4-7"`, `"sonnet-1m"`, `"opus-1m"`, `"opus-4-6-1m"`, `"opus-4-7-1m"`) outside of:

- `lib/set_orch/config.py::DIRECTIVE_DEFAULTS["models"]` (the canonical defaults table)
- `lib/set_orch/model_config.py` (the resolver — preset definitions and last-resort fallbacks)
- `lib/set_orch/subprocess_utils.py::_MODEL_MAP` (the short-name → full-id translation table)
- `lib/set_orch/cost.py::_RATES` (the cost-tracking rates table)
- `lib/set_orch/cli.py` argparse `choices=` lists (validation only)
- Test files (`tests/**`)
- Comments and docstrings explaining the policy

Every other call site SHALL read its model via `resolve_model(role)` (or accept it via a kwarg whose default is `None`, then call `resolve_model(role)` when the caller didn't supply one).

#### Scenario: dispatcher.resolve_change_model uses resolve_model for default
- **WHEN** `dispatcher.resolve_change_model` is invoked with no `default_model` argument
- **THEN** the function consults `resolve_model("agent")` for its default

#### Scenario: digest.call_digest_api uses resolve_model when model arg is None
- **WHEN** `digest.call_digest_api(...)` is called without an explicit `model` keyword
- **THEN** the function consults `resolve_model("digest")` to pick the model

#### Scenario: planner decompose_brief uses resolve_model when model arg is None
- **WHEN** `planner.decompose_brief(...)` is invoked without an explicit model
- **THEN** the function consults `resolve_model("decompose_brief")`

#### Scenario: planner decompose_domain uses resolve_model when model arg is None
- **WHEN** `planner.decompose_domain(...)` is invoked without an explicit model
- **THEN** the function consults `resolve_model("decompose_domain")`

#### Scenario: planner decompose_merge uses resolve_model when model arg is None
- **WHEN** `planner.decompose_merge(...)` is invoked without an explicit model
- **THEN** the function consults `resolve_model("decompose_merge")`

#### Scenario: verifier review gate uses resolve_model for initial pass and escalation
- **WHEN** the code-review gate runs its initial pass
- **THEN** it consults `resolve_model("review")` (default sonnet)
- **AND** when escalating after failure, it consults `resolve_model("review_escalation")` (default opus-4-6)

#### Scenario: verifier spec_verify gate uses resolve_model for initial pass and escalation
- **WHEN** the spec_verify gate runs
- **THEN** it consults `resolve_model("spec_verify")` for the initial pass
- **AND** `resolve_model("spec_verify_escalation")` for the escalation

#### Scenario: llm_verdict classifier uses resolve_model
- **WHEN** an `LLMVerdict` is constructed without an explicit model
- **THEN** the model field is populated from `resolve_model("classifier")`

#### Scenario: canary uses resolve_model for canary role
- **WHEN** the canary monitor runs a health check
- **THEN** it consults `resolve_model("canary")` for the model arg

#### Scenario: ephemeral spawn uses resolve_model for caller-supplied role
- **WHEN** an `EphemeralRequest` is constructed without an explicit model
- **THEN** the model field is populated from `resolve_model("supervisor")` (default sonnet)

#### Scenario: trigger map reads resolve_model for each trigger
- **WHEN** the supervisor triggers an action of type `integration_failed`
- **THEN** the model used is `resolve_model("trigger.integration_failed")`

#### Scenario: manager.supervisor.py uses resolve_model for sentinel agent
- **WHEN** `manager.supervisor.py` builds the sentinel.md command
- **THEN** the `--model` value is `resolve_model("supervisor")`

#### Scenario: chat.ChatSession uses resolve_model on init
- **WHEN** a `ChatSession` is constructed without an explicit model
- **THEN** `self.model = resolve_model("agent")`

### Requirement: dispatcher complexity routing uses agent_small role

`dispatcher.resolve_change_model()`'s complexity-based routing SHALL return `resolve_model("agent_small")` for the downgrade target instead of the literal string `"sonnet"`. The default value of `agent_small` in DIRECTIVE_DEFAULTS SHALL be `"sonnet"`.

#### Scenario: complexity routing returns agent_small for S+non-feature
- **WHEN** `model_routing="complexity"` is active and the change is `complexity="S"` and `change_type != "feature"`
- **THEN** `resolve_change_model` returns `resolve_model("agent_small")`

#### Scenario: agent_small default is sonnet
- **WHEN** no override and `resolve_model("agent_small")` is called
- **THEN** the result is `"sonnet"`
