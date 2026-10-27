## ADDED Requirements

### Requirement: resolve_model helper exposes the full resolution chain

`lib/set_orch/model_config.py::resolve_model(role: str, *, project_dir: str = ".", cli_override: Optional[str] = None) -> str` SHALL implement a five-tier resolution chain. First match wins:

1. `cli_override` argument if non-None
2. ENV var `SET_ORCH_MODEL_<ROLE_UPPER>` (dots in role names become underscores: `trigger.integration_failed` → `SET_ORCH_MODEL_TRIGGER_INTEGRATION_FAILED`)
3. `orchestration.yaml::models.<role>` (or `models.trigger.<sub>` for nested roles)
4. `profile.model_for(role)` from `load_profile(project_dir)` — when it returns a non-None value
5. `DIRECTIVE_DEFAULTS["models"][<role>]` (resolves nested via `models.trigger.<sub>`)

The returned name SHALL be a valid short name validated against the model-name regex. Invalid values from any source SHALL raise `ValueError` whose message names the source tier and the offending value. An unknown `role` (no defaults entry, nothing in the chain) SHALL raise `ValueError`.

#### Scenario: cli_override beats every other source
- **WHEN** `resolve_model("agent", cli_override="haiku")` is called with ENV `SET_ORCH_MODEL_AGENT=opus`, yaml `models.agent: sonnet`, and DEFAULTS `agent: opus-4-6`
- **THEN** the result is `"haiku"`

#### Scenario: ENV var beats yaml and defaults
- **WHEN** ENV `SET_ORCH_MODEL_AGENT=opus-4-7` is set, yaml has `models.agent: sonnet`, DEFAULTS has `agent: opus-4-6`, and `cli_override` is None
- **THEN** `resolve_model("agent")` returns `"opus-4-7"`

#### Scenario: yaml beats profile and defaults
- **WHEN** no CLI override and no ENV var, yaml has `models.agent: sonnet`, profile.model_for returns `"opus-4-7"`, DEFAULTS has `agent: opus-4-6`
- **THEN** `resolve_model("agent")` returns `"sonnet"`

#### Scenario: profile beats defaults
- **WHEN** no CLI, no ENV, no yaml override, profile.model_for("agent") returns `"opus-4-7"`, DEFAULTS has `agent: opus-4-6`
- **THEN** `resolve_model("agent")` returns `"opus-4-7"`

#### Scenario: defaults are last-resort
- **WHEN** no override at any level
- **THEN** `resolve_model("agent")` returns the DIRECTIVE_DEFAULTS value (`"opus-4-6"`)

#### Scenario: nested trigger role resolves dotted path
- **WHEN** `resolve_model("trigger.integration_failed")` is called with no overrides
- **THEN** the value is the DIRECTIVE_DEFAULTS `models.trigger.integration_failed` value

#### Scenario: ENV var name maps dots to underscores
- **WHEN** `resolve_model("trigger.integration_failed")` is called with ENV `SET_ORCH_MODEL_TRIGGER_INTEGRATION_FAILED=opus-4-7` set
- **THEN** the result is `"opus-4-7"`

#### Scenario: invalid ENV var value raises
- **WHEN** `SET_ORCH_MODEL_AGENT=not-a-real-model` is set and `resolve_model("agent")` is called
- **THEN** the call raises `ValueError` whose message names ENV and `not-a-real-model`

#### Scenario: invalid CLI override raises
- **WHEN** `resolve_model("agent", cli_override="not-a-real-model")` is called
- **THEN** the call raises `ValueError`

#### Scenario: unknown role raises
- **WHEN** `resolve_model("not-a-real-role")` is called with no override at any level
- **THEN** the call raises `ValueError` whose message names the unknown role

### Requirement: ProjectType.model_for hook supplies optional per-stack overrides

The `ProjectType` ABC SHALL expose `model_for(role: str) -> Optional[str]` returning either a short model name override or `None` for "no opinion". `CoreProfile` SHALL inherit the None default. Plugins MAY override per-stack; the override SHALL be consulted in tier 4 of the resolution chain.

#### Scenario: CoreProfile model_for returns None for any role
- **WHEN** `CoreProfile().model_for("agent")` (or any other role) is called
- **THEN** the result is `None`

#### Scenario: plugin override fires when nothing higher in chain wins
- **WHEN** a custom profile returns `"opus-4-7"` from `model_for("review_escalation")`, no CLI/ENV/yaml override exists, and DIRECTIVE_DEFAULTS has `review_escalation: opus-4-6`
- **THEN** `resolve_model("review_escalation", project_dir=...)` returns `"opus-4-7"`
