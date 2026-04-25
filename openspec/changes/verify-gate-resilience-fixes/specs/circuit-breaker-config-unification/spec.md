## ADDED Requirements

## IN SCOPE
- Single source of truth (`config.py DIRECTIVE_DEFAULTS`) for all retry/circuit-breaker limits in the engine.
- `EngineConfig @dataclass` defaults read from `DIRECTIVE_DEFAULTS` at class-definition time.
- Pytest parity test that fails CI if `EngineConfig` and `DIRECTIVE_DEFAULTS` disagree on any default.
- Hardcoded module-level constants in `merger.py`, `verifier.py`, `watchdog.py`, `issues/models.py` exposed as directive parameters.
- Token-runaway pre-warning at 80% threshold.

## OUT OF SCOPE
- Refactor of how directives are parsed (still `parse_directives` in `config.py`).
- Rewriting EngineConfig as a different config primitive (Pydantic, etc.).
- Auto-bisect on token runaway (still terminal failure on threshold).

### Requirement: Single source of truth for retry/circuit limits
The framework SHALL use `config.py DIRECTIVE_DEFAULTS` as the only place where retry/circuit-breaker default values are declared. `EngineConfig @dataclass` field defaults SHALL read from `DIRECTIVE_DEFAULTS` via `field(default_factory=lambda: DIRECTIVE_DEFAULTS["<key>"])`.

#### Scenario: Raising a default value requires only one edit
- **WHEN** an operator wants to raise `max_verify_retries` from 12 to 16
- **THEN** they edit `DIRECTIVE_DEFAULTS["max_verify_retries"]` only
- **AND** `EngineConfig().max_verify_retries` returns 16 without any further edit
- **AND** the parity test continues to pass

#### Scenario: Divergence is caught at test time
- **WHEN** a developer accidentally sets `EngineConfig.max_verify_retries: int = 8` while `DIRECTIVE_DEFAULTS["max_verify_retries"] = 12`
- **THEN** the parity test `test_config_engine_parity` fails with a message naming the divergent key and both values
- **AND** the divergence cannot reach production

### Requirement: Hardcoded constants exposed as directives
The framework SHALL provide directive overrides for all retry/circuit-breaker constants previously hardcoded in module-level definitions or inline literals. The constants currently named `MAX_MERGE_RETRIES` (`merger.py`), `max_integration_retries` (`verifier.py` inline), `WATCHDOG_TIMEOUT_RUNNING`, `WATCHDOG_TIMEOUT_VERIFYING`, `WATCHDOG_TIMEOUT_DISPATCHED`, `WATCHDOG_LOOP_THRESHOLD` (`watchdog.py`), and `DEFAULT_ISSUE_DIAGNOSED_TIMEOUT_SECS` (`issues/models.py`) SHALL be replaced by lookups against the directives dict, with backward-compatible default values.

#### Scenario: Operator overrides max_merge_retries via directive
- **WHEN** an operator sets `max_merge_retries: 7` in `orchestration.yaml`
- **THEN** the merger uses 7 as the merge retry ceiling for that run
- **AND** `MAX_MERGE_RETRIES` (still defined as a module-level alias) reflects the default value (5) for backward-compatible imports

#### Scenario: Watchdog uses directive value for verifying timeout
- **WHEN** an operator sets `watchdog_timeout_verifying: 1800` in `orchestration.yaml`
- **THEN** the watchdog uses 1800 seconds (30 min) as the timeout for `verifying` state
- **AND** if the directive is not set, the default 1200 seconds (20 min) is used

### Requirement: Deprecated `token_hard_limit` directive
The framework SHALL log a deprecation warning at orchestration startup if `token_hard_limit` is set in directives, and SHALL ignore the value. The directive SHALL remain parseable (no crash on existing configs) for at least one release after this change.

#### Scenario: token_hard_limit logs deprecation
- **WHEN** an operator's `orchestration.yaml` sets `token_hard_limit: 30000000`
- **THEN** the engine logs `WARNING: token_hard_limit is deprecated, use per_change_token_runaway_threshold` once at startup
- **AND** the value is not applied to any runtime check
- **AND** orchestration starts normally

### Requirement: Token-runaway pre-warning at 80% threshold
The framework SHALL emit a `WARNING` log entry and write a memory entry (tagged `token-pressure,<change-name>`) the first time a change's `input_tokens` crosses 80% of the effective `per_change_token_runaway_threshold`. Subsequent token updates above the 80% mark SHALL NOT re-emit the warning for the same change in the same run.

#### Scenario: Pre-warning fires once at 80%
- **WHEN** a change has `per_change_token_runaway_threshold: 50_000_000` and `input_tokens` rises from 39M to 41M
- **THEN** a WARNING log entry is emitted with the change name, current usage, and threshold
- **AND** a memory entry is written under `tags=token-pressure,<change-name>` with the snapshot
- **AND** further updates (e.g., 42M, 45M) do not emit additional WARNING logs

#### Scenario: Below threshold does not warn
- **WHEN** a change has `input_tokens` at 39M with threshold 50M
- **THEN** no pre-warning is emitted (39/50 = 78% < 80%)

### Requirement: Raised default ceilings
The framework SHALL ship with the following default values in `DIRECTIVE_DEFAULTS`:

| Directive | Old | New |
|---|---|---|
| `max_verify_retries` | 8 | 12 |
| `max_merge_retries` | 3 (hardcoded) | 5 |
| `max_integration_retries` | 3 (inline) | 5 |
| `e2e_retry_limit` | 5 | 8 |
| `max_stuck_loops` | 3 | 5 |
| `max_replan_retries` | 3 | 5 |
| `watchdog_timeout_running` | 600s (hardcoded) | 1800s |
| `watchdog_timeout_verifying` | 300s (hardcoded) | 1200s |
| `watchdog_timeout_dispatched` | 120s (hardcoded) | 120s (unchanged) |
| `issue_diagnosed_timeout_secs` | 3600s (hardcoded) | 5400s |

#### Scenario: New runs use raised defaults
- **WHEN** an operator starts a new orchestration run with no directive overrides
- **THEN** `EngineConfig()` returns `max_verify_retries=12`, `max_merge_retries=5`, etc., per the table above
