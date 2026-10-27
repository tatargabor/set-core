## 1. Schema + DIRECTIVE_DEFAULTS

- [x] 1.1 Add `models:` top-level dict to `lib/set_orch/config.py::DIRECTIVE_DEFAULTS` with all 13 leaf keys (`agent`, `digest`, `decompose_brief`, `decompose_domain`, `decompose_merge`, `review`, `review_escalation`, `spec_verify`, `spec_verify_escalation`, `classifier`, `supervisor`, `canary`, `agent_small`) plus the `trigger` sub-dict (`integration_failed`, `non_periodic_checkpoint`, `terminal_state`, `default`). Set defaults per design D1 with `agent: "opus-4-6"` [REQ: orchestration-directives-expose-a-unified-models-block, REQ: agent-default-is-opus-4-6]
- [x] 1.2 Extend the directive validator in `config.py` to validate every leaf in the `models:` block (and the trigger sub-dict) against the model-name regex. Error messages name the offending key path (e.g. `models.agent`, `models.trigger.integration_failed`) and the bad value [REQ: validator-rejects-invalid-model-names-in-models-block]
- [x] 1.3 Add backwards-compat shim: when reading `models.agent` if a user-supplied yaml contains the legacy `default_model` directive but no `models.agent`, return the legacy value with a one-shot DEPRECATION `logger.warning`. Same for `summarize_model → models.digest` and `review_model → models.review` [REQ: legacy-default-model-directive-remains-backwards-compatible]
- [x] 1.4 Confirm `subprocess_utils._MODEL_MAP["opus-4-6"] == "claude-opus-4-6"` (already present per audit; assert in a test) [REQ: agent-default-is-opus-4-6]

## 2. resolve_model helper

- [x] 2.1 Create new module `lib/set_orch/model_config.py` with `resolve_model(role, *, project_dir=".", cli_override=None) -> str` per design D2. Implement the 5-tier chain (CLI → ENV → yaml → profile → DEFAULTS). Validate output against the model-name regex; raise `ValueError` on invalid input [REQ: resolve-model-helper-exposes-the-full-resolution-chain]
- [x] 2.2 Implement nested role lookup so `resolve_model("trigger.integration_failed")` reads the dotted path from yaml and DIRECTIVE_DEFAULTS, and `SET_ORCH_MODEL_TRIGGER_INTEGRATION_FAILED` from ENV [REQ: resolve-model-helper-exposes-the-full-resolution-chain]
- [x] 2.3 Add `MODEL_NAME_RE` constant in `model_config.py` mirroring the existing validator regex; reuse from `config.py` if it already exposes one [REQ: resolve-model-helper-exposes-the-full-resolution-chain]
- [x] 2.4 Add `model_for(role: str) -> Optional[str]` to `ProjectType` ABC (lib/set_orch/profile_types.py) with `return None` default [REQ: projecttype-model-for-hook-supplies-optional-per-stack-overrides]
- [x] 2.5 Confirm `CoreProfile` inherits the None default (no override) [REQ: projecttype-model-for-hook-supplies-optional-per-stack-overrides]

## 3. CLI flags + presets + ENV

- [x] 3.1 Add per-role CLI flags to all relevant subcommands in `lib/set_orch/cli.py`: `--agent-model`, `--digest-model`, `--decompose-brief-model`, `--decompose-domain-model`, `--decompose-merge-model`, `--review-model`, `--review-escalation-model`, `--spec-verify-model`, `--spec-verify-escalation-model`, `--classifier-model`, `--supervisor-model`, `--canary-model`, `--agent-small-model`. Use `choices=` from the validation regex [REQ: per-role-cli-flags-expose-every-model]
- [x] 3.2 Keep `--default-model` accepted as an alias for `--agent-model` so existing scripts continue to work. Map it to the same dest in argparse [REQ: per-role-cli-flags-expose-every-model]
- [x] 3.3 Add `--model-profile <preset>` flag with choices `default | all-opus-4-6 | all-opus-4-7 | cost-optimized`. Resolve preset → role-mapping in argparse post-processing; per-role flags override on top [REQ: model-profile-preset-shortcut-sets-all-roles]
- [x] 3.4 Define preset table in `model_config.py::PRESETS` with the four preset mappings per design D6 [REQ: model-profile-preset-shortcut-sets-all-roles]
- [x] 3.5 Wire CLI args into `resolve_model` calls at every entry point: `engine monitor`, `dispatch`, `plan run`, `digest run`, `verify`, `set-supervisor`, `chat`. Pass the parsed `args.<role>_model` as `cli_override` [REQ: per-role-cli-flags-expose-every-model]
- [x] 3.6 Verify `SET_ORCH_MODEL_<ROLE>` ENV vars are read for every role; trigger sub-roles use dot→underscore transformation. Add a regression test asserting all 13 leaf roles + 4 trigger roles are reachable via ENV [REQ: env-vars-cover-every-role]

## 4. Touch-point conversions — Category A (per-change agent)

- [x] 4.1 In `lib/set_orch/dispatcher.py::resolve_change_model`, replace the literal `default_model` parameter default with `resolve_model("agent")`. Keep the parameter for callers that want to override [REQ: every-python-model-literal-is-replaced-by-a-resolve-model-call]
- [x] 4.2 In `dispatcher.resolve_change_model` complexity-routing branch (lines ~1198-1202), replace literal `"sonnet"` with `resolve_model("agent_small")` [REQ: dispatcher-complexity-routing-uses-agent-small-role]
- [x] 4.3 In `lib/set_orch/engine.py::Directives` dataclass, change `default_model` field default from `"opus"` to `resolve_model("agent")` (use a default_factory to avoid import-time evaluation issues) [REQ: every-python-model-literal-is-replaced-by-a-resolve-model-call]
- [x] 4.4 In `lib/set_orch/dispatcher.py` other functions with `default_model: str = "opus"` parameters (signatures around lines 2590, 3523, 3684 per audit), change to `default_model: Optional[str] = None` and resolve inside [REQ: every-python-model-literal-is-replaced-by-a-resolve-model-call]

## 5. Touch-point conversions — Category B (planner LLM calls)

- [x] 5.1 In `lib/set_orch/digest.py::CallDigestRequest` dataclass, change `model: str = "opus"` to `model: Optional[str] = None`. In `call_digest_api`, when `request.model is None` use `resolve_model("digest")` [REQ: digest-call-digest-api-uses-resolve-model-when-model-arg-is-none]
- [x] 5.2 In `lib/set_orch/planner.py::decompose_brief`, change the `model="opus"` default to `model: Optional[str] = None`. Resolve to `resolve_model("decompose_brief")` when None [REQ: planner-decompose-brief-uses-resolve-model-when-model-arg-is-none]
- [x] 5.3 In `planner.decompose_domain`, do the same with role `"decompose_domain"` [REQ: planner-decompose-domain-uses-resolve-model-when-model-arg-is-none]
- [x] 5.4 In `planner.decompose_merge`, do the same with role `"decompose_merge"` [REQ: planner-decompose-merge-uses-resolve-model-when-model-arg-is-none]

## 6. Touch-point conversions — Category C (verify-pipeline LLM gates)

- [x] 6.1 In `lib/set_orch/verifier.py`, remove the module-level constant `DEFAULT_REVIEW_MODEL = "sonnet"`. Replace with `resolve_model("review")` calls at the initial-pass site (lines ~1430-1530 per audit) and `resolve_model("review_escalation")` at the escalation site (lines ~1499-1517) [REQ: verifier-review-gate-uses-resolve-model-for-initial-pass-and-escalation]
- [x] 6.2 In `verifier.py::_execute_spec_verify_gate` (lines ~3390-3600), use `resolve_model("spec_verify")` for the initial pass (line ~3433) and `resolve_model("spec_verify_escalation")` for the retry path (lines ~3458, ~3486) [REQ: verifier-spec-verify-gate-uses-resolve-model-for-initial-pass-and-escalation]
- [x] 6.3 In `lib/set_orch/llm_verdict.py::LLMVerdict` dataclass, change `model: str = "sonnet"` to `model: Optional[str] = None`. In `__post_init__` (or first use), resolve via `resolve_model("classifier")` [REQ: llm-verdict-classifier-uses-resolve-model]

## 7. Touch-point conversions — Category D (supervisor/canary/sentinel)

- [x] 7.1 In `lib/set_orch/supervisor/canary.py::CanaryMonitor.run` (line ~242), replace literal `model="sonnet"` with `model=resolve_model("canary")` [REQ: canary-uses-resolve-model-for-canary-role]
- [x] 7.2 In `lib/set_orch/supervisor/ephemeral.py::EphemeralRequest` dataclass, change `model: str = "sonnet"` to `model: Optional[str] = None`. In the spawn function, resolve via `resolve_model("supervisor")` when None [REQ: ephemeral-spawn-uses-resolve-model-for-caller-supplied-role]
- [x] 7.3 In `lib/set_orch/supervisor/triggers.py`, replace `DEFAULT_MODEL_BY_TRIGGER` static dict with a function `default_model_for_trigger(trigger: TriggerType) -> str` that returns `resolve_model(f"trigger.{trigger.name.lower()}")`. The `default` fallback uses `resolve_model("trigger.default")` [REQ: trigger-map-reads-resolve-model-for-each-trigger]
- [x] 7.4 In `lib/set_orch/manager/supervisor.py` (line ~315), replace hardcoded `--model sonnet` in the sentinel.md command with `--model {resolve_model("supervisor")}` [REQ: manager-supervisor-py-uses-resolve-model-for-sentinel-agent]
- [x] 7.5 In `lib/set_orch/chat.py::ChatSession.__init__`, change `self.model: str = "sonnet"` to `self.model: str = resolve_model("agent")` [REQ: chat-chatsession-uses-resolve-model-on-init]

## 8. Sonnet-routing prompt fix

- [x] 8.1 In `lib/set_orch/templates.py::render_brief_prompt`, locate the existing model-selection guidance (around lines 453-456 per audit) and replace it. New guidance: opus is for `feature` AND `foundational`; sonnet is for `infrastructure`, `schema`, `cleanup-before`, `cleanup-after`; advise opus when unsure [REQ: planner-prompt-instructs-foundational-changes-to-use-opus]
- [x] 8.2 Apply the same replacement to the duplicate guidance at lines 537, 556, 577, 811 (audit identified these as repeats). Verify a grep finds no remaining "sonnet for infrastructure / cleanup / docs / refactor" instruction [REQ: planner-prompt-instructs-foundational-changes-to-use-opus]
- [x] 8.3 Verify the rendered prompt contains: `foundational` linked to `opus`; the four sonnet-allowed change_types named explicitly; "when unsure, prefer opus" phrasing [REQ: planner-prompt-instructs-foundational-changes-to-use-opus]

## 9. Bash mirror

- [x] 9.1 Update `bin/set-common.sh::resolve_model_id` to accept `--config <yaml>` and `--role <role>` flags. Implement yaml read via Python one-liner. Fall back to positional `<name|fallback>` when yaml read returns nothing [REQ: set-common-sh-resolve-model-id-supports-config-and-role]
- [x] 9.2 Cache the parsed yaml in a process-local shell variable so repeated invocations don't re-parse [REQ: set-common-sh-resolve-model-id-supports-config-and-role]
- [x] 9.3 Update `lib/orchestration/dispatcher.sh` to pass `--config "$ORCH_YAML" --role agent` (and similar for any other role it resolves) before the positional fallback [REQ: lib-orchestration-shell-scripts-pass-config-role-to-resolve-model-id]
- [x] 9.4 Update `lib/orchestration/digest.sh` to pass `--config "$ORCH_YAML" --role digest` before the positional fallback [REQ: lib-orchestration-shell-scripts-pass-config-role-to-resolve-model-id]

## 10. Template deployment

- [x] 10.1 Update `modules/web/set_project_web/templates/nextjs/set/orchestration/config.yaml` to include a fully-documented `models:` block (commented out by default). Each role gets a one-line comment naming its purpose [REQ: web-template-ships-a-documented-models-block]
- [x] 10.2 Verify `set-project init` produces a working orchestration.yaml — load via `load_directives` and confirm no validation errors with the commented block [REQ: web-template-ships-a-documented-models-block]

## 11. Release notes

- [x] 11.1 Add a prominent entry to `docs/release/v1.8.0.md` calling out the `models.agent` default change to `opus-4-6` as breaking. Include the migration recipe (`models.agent: opus-4-7` or `--model-profile all-opus-4-7`) [REQ: release-notes-document-the-agent-default-change-as-breaking]

## 12. Tests

- [x] 12.1 Create `tests/unit/test_model_config.py` with cases: every leaf role in DIRECTIVE_DEFAULTS validates against the regex; agent default is opus-4-6; trigger sub-dict has all 4 keys; opus-4-6 maps to claude-opus-4-6 [REQ: directive_defaults-contains-a-models-block-with-all-required-keys, REQ: every-default-model-name-is-a-valid-short-name, REQ: agent-default-is-opus-4-6]
- [x] 12.2 Add tests for `resolve_model` resolution chain: cli_override beats all; ENV beats yaml/profile/defaults; yaml beats profile/defaults; profile beats defaults; defaults are last; nested trigger.* roles work; ENV name dot→underscore mapping works; invalid values raise ValueError; unknown role raises ValueError [REQ: resolve-model-helper-exposes-the-full-resolution-chain]
- [x] 12.3 Add tests for `model_for` ABC hook: CoreProfile returns None; a custom profile override fires when nothing higher in chain wins [REQ: projecttype-model-for-hook-supplies-optional-per-stack-overrides]
- [x] 12.4 Add tests for legacy `default_model`/`summarize_model`/`review_model` backwards-compat: legacy honored with deprecation warning; explicit `models.<role>` overrides legacy [REQ: legacy-default-model-directive-remains-backwards-compatible]
- [x] 12.5 Add tests for CLI flag wiring: each per-role flag overrides DIRECTIVE_DEFAULTS; `--default-model` aliases `--agent-model`; argparse rejects invalid model names; preset names are validated [REQ: per-role-cli-flags-expose-every-model]
- [x] 12.6 Add tests for `--model-profile`: each preset sets all roles correctly; per-role flag overrides preset values; cost-optimized preset uses haiku/sonnet mix [REQ: model-profile-preset-shortcut-sets-all-roles]
- [x] 12.7 Add a touch-point coverage test that imports each affected module and asserts that calling its public API without an explicit model results in a `resolve_model` call. Mock `resolve_model` and assert the role argument matches expectation [REQ: every-python-model-literal-is-replaced-by-a-resolve-model-call]
- [x] 12.8 Add a regression test that scans `lib/set_orch/`, `modules/web/set_project_web/`, and `bin/` for hardcoded short-model-name string literals OUTSIDE the allowed files (config.py, model_config.py, subprocess_utils.py, cost.py, cli.py choices, comments). Assert zero violations [REQ: every-python-model-literal-is-replaced-by-a-resolve-model-call]
- [x] 12.9 Add tests for `dispatcher.resolve_change_model`: complexity routing returns `resolve_model("agent_small")` for S+non-feature; default value of agent_small is sonnet [REQ: dispatcher-complexity-routing-uses-agent-small-role]
- [x] 12.10 Add tests for the planner prompt fix: render_brief_prompt output contains foundational→opus; lists the four sonnet-allowed change_types; advises opus when unsure; does NOT instruct foundational to use sonnet [REQ: planner-prompt-instructs-foundational-changes-to-use-opus]
- [x] 12.11 Add bash-side smoke test (shell script under `tests/orchestrator/test-resolve-model-id.sh`) that exercises `resolve_model_id --config <yaml> --role agent` and `resolve_model_id --config <yaml> --role digest` and verifies the correct full-id output [REQ: set-common-sh-resolve-model-id-supports-config-and-role, REQ: lib-orchestration-shell-scripts-pass-config-role-to-resolve-model-id]
- [x] 12.12 Add a deployment test that loads the deployed `modules/web/.../templates/.../config.yaml` via `load_directives` and asserts no validation errors [REQ: web-template-ships-a-documented-models-block]

## Acceptance Criteria (from spec scenarios)

### Capability: model-config-schema
- [x] AC-1: WHEN `lib/set_orch/config.py` is imported and `DIRECTIVE_DEFAULTS["models"]` is read THEN the dict contains all 13 leaf keys plus the `trigger` sub-dict with its 4 keys [REQ: orchestration-directives-expose-a-unified-models-block, scenario: directive_defaults-contains-a-models-block-with-all-required-keys]
- [x] AC-2: WHEN every leaf in `DIRECTIVE_DEFAULTS["models"]` is checked against the model-name regex THEN every value matches [REQ: orchestration-directives-expose-a-unified-models-block, scenario: every-default-model-name-is-a-valid-short-name]
- [x] AC-3: WHEN no orchestration.yaml override and no CLI flag and no ENV var THEN `resolve_model("agent")` returns `"opus-4-6"` [REQ: agent-default-is-opus-4-6, scenario: agent-default-resolves-to-opus-4-6]
- [x] AC-4: WHEN `subprocess_utils._MODEL_MAP["opus-4-6"]` is read THEN the value is `"claude-opus-4-6"` [REQ: agent-default-is-opus-4-6, scenario: opus-4-6-short-name-maps-to-claude-opus-4-6]
- [x] AC-5: WHEN an orchestration.yaml contains `models.agent: gpt-4` THEN loading raises a configuration error naming `models.agent` and `gpt-4` [REQ: validator-rejects-invalid-model-names-in-models-block, scenario: invalid-agent-value-is-rejected]
- [x] AC-6: WHEN orchestration.yaml has `models.trigger.integration_failed: invalid-name` THEN loading raises a configuration error naming `models.trigger.integration_failed` [REQ: validator-rejects-invalid-model-names-in-models-block, scenario: invalid-trigger-sub-key-value-is-rejected]
- [x] AC-7: WHEN orchestration.yaml has `default_model: opus-4-7` and no `models:` block THEN `resolve_model("agent")` returns `"opus-4-7"` AND a WARNING log record is emitted naming `default_model` as deprecated [REQ: legacy-default-model-directive-remains-backwards-compatible, scenario: legacy-default-model-is-honored-with-deprecation-warning]
- [x] AC-8: WHEN orchestration.yaml has both `default_model: opus-4-7` and `models.agent: opus-4-6` THEN `resolve_model("agent")` returns `"opus-4-6"` [REQ: legacy-default-model-directive-remains-backwards-compatible, scenario: explicit-models-agent-overrides-legacy-default-model]

### Capability: model-resolution-chain
- [x] AC-9: WHEN `resolve_model("agent", cli_override="haiku")` is called with conflicting ENV/yaml/defaults THEN the result is `"haiku"` [REQ: resolve-model-helper-exposes-the-full-resolution-chain, scenario: cli_override-beats-every-other-source]
- [x] AC-10: WHEN ENV `SET_ORCH_MODEL_AGENT=opus-4-7` is set, yaml has `models.agent: sonnet`, DEFAULTS has `agent: opus-4-6`, and `cli_override` is None THEN `resolve_model("agent")` returns `"opus-4-7"` [REQ: resolve-model-helper-exposes-the-full-resolution-chain, scenario: env-var-beats-yaml-and-defaults]
- [x] AC-11: WHEN no CLI override and no ENV var, yaml has `models.agent: sonnet`, profile.model_for returns `"opus-4-7"`, DEFAULTS has `agent: opus-4-6` THEN `resolve_model("agent")` returns `"sonnet"` [REQ: resolve-model-helper-exposes-the-full-resolution-chain, scenario: yaml-beats-profile-and-defaults]
- [x] AC-12: WHEN no CLI, no ENV, no yaml override, profile.model_for("agent") returns `"opus-4-7"`, DEFAULTS has `agent: opus-4-6` THEN `resolve_model("agent")` returns `"opus-4-7"` [REQ: resolve-model-helper-exposes-the-full-resolution-chain, scenario: profile-beats-defaults]
- [x] AC-13: WHEN no override at any level THEN `resolve_model("agent")` returns the DIRECTIVE_DEFAULTS value (`"opus-4-6"`) [REQ: resolve-model-helper-exposes-the-full-resolution-chain, scenario: defaults-are-last-resort]
- [x] AC-14: WHEN `resolve_model("trigger.integration_failed")` is called with no overrides THEN the value is the DIRECTIVE_DEFAULTS `models.trigger.integration_failed` value [REQ: resolve-model-helper-exposes-the-full-resolution-chain, scenario: nested-trigger-role-resolves-dotted-path]
- [x] AC-15: WHEN `resolve_model("trigger.integration_failed")` is called with ENV `SET_ORCH_MODEL_TRIGGER_INTEGRATION_FAILED=opus-4-7` set THEN the result is `"opus-4-7"` [REQ: resolve-model-helper-exposes-the-full-resolution-chain, scenario: env-var-name-maps-dots-to-underscores]
- [x] AC-16: WHEN `SET_ORCH_MODEL_AGENT=not-a-real-model` is set and `resolve_model("agent")` is called THEN the call raises `ValueError` whose message names ENV and `not-a-real-model` [REQ: resolve-model-helper-exposes-the-full-resolution-chain, scenario: invalid-env-var-value-raises]
- [x] AC-17: WHEN `resolve_model("agent", cli_override="not-a-real-model")` is called THEN the call raises `ValueError` [REQ: resolve-model-helper-exposes-the-full-resolution-chain, scenario: invalid-cli-override-raises]
- [x] AC-18: WHEN `resolve_model("not-a-real-role")` is called with no override at any level THEN the call raises `ValueError` whose message names the unknown role [REQ: resolve-model-helper-exposes-the-full-resolution-chain, scenario: unknown-role-raises]
- [x] AC-19: WHEN `CoreProfile().model_for("agent")` is called THEN the result is `None` [REQ: projecttype-model-for-hook-supplies-optional-per-stack-overrides, scenario: coreprofile-model-for-returns-none-for-any-role]
- [x] AC-20: WHEN a custom profile returns `"opus-4-7"` from `model_for("review_escalation")`, no CLI/ENV/yaml override, DIRECTIVE_DEFAULTS has `review_escalation: opus-4-6` THEN `resolve_model("review_escalation", project_dir=...)` returns `"opus-4-7"` [REQ: projecttype-model-for-hook-supplies-optional-per-stack-overrides, scenario: plugin-override-fires-when-nothing-higher-in-chain-wins]

### Capability: model-config-cli
- [x] AC-21: WHEN the CLI is invoked with `--agent-model opus-4-7` and no other override THEN `resolve_model("agent", cli_override=args.agent_model)` returns `"opus-4-7"` [REQ: per-role-cli-flags-expose-every-model, scenario: --agent-model-overrides-directive_defaults]
- [x] AC-22: WHEN the CLI is invoked with `--default-model opus-4-7` THEN parsed args populate `args.agent_model = "opus-4-7"` [REQ: per-role-cli-flags-expose-every-model, scenario: --default-model-is-accepted-as-alias-for---agent-model]
- [x] AC-23: WHEN the CLI is invoked with `--agent-model not-a-real-model` THEN argparse raises a clear error [REQ: per-role-cli-flags-expose-every-model, scenario: invalid-flag-value-is-rejected-at-argparse-time]
- [x] AC-24: WHEN `--model-profile all-opus-4-6` is supplied with no individual overrides THEN every role resolves to `"opus-4-6"` [REQ: model-profile-preset-shortcut-sets-all-roles, scenario: all-opus-4-6-preset-sets-every-role-to-opus-4-6]
- [x] AC-25: WHEN `--model-profile cost-optimized --review-model opus-4-6` is supplied THEN `resolve_model("review")` returns `"opus-4-6"` AND `resolve_model("agent")` returns `"sonnet"` [REQ: model-profile-preset-shortcut-sets-all-roles, scenario: per-role-flag-overrides-preset]
- [x] AC-26: WHEN `--model-profile not-a-real-preset` is supplied THEN argparse raises a clear error listing valid preset names [REQ: model-profile-preset-shortcut-sets-all-roles, scenario: invalid-preset-name-is-rejected]
- [x] AC-27: WHEN ENV vars `SET_ORCH_MODEL_<ROLE>` are set to valid model names THEN each `resolve_model(<role>)` call returns the corresponding ENV value [REQ: env-vars-cover-every-role, scenario: env-var-reading-covers-all-standard-roles]

### Capability: model-config-bash-mirror
- [x] AC-28: WHEN `resolve_model_id --config /path/to/orchestration.yaml --role agent` is called and the yaml has `models.agent: opus-4-6` THEN stdout contains `claude-opus-4-6` [REQ: set-common-sh-resolve-model-id-supports-config-and-role, scenario: resolve_model_id-reads-yaml-when---config-and---role-supplied]
- [x] AC-29: WHEN `resolve_model_id --config /path/to/orchestration.yaml --role agent sonnet` is called and the yaml has no `models:` block THEN stdout contains `claude-sonnet-4-6` [REQ: set-common-sh-resolve-model-id-supports-config-and-role, scenario: resolve_model_id-falls-back-to-positional-fallback-when-yaml-unset]
- [x] AC-30: WHEN `resolve_model_id opus` is called (no flags) THEN stdout contains `claude-opus-4-7` [REQ: set-common-sh-resolve-model-id-supports-config-and-role, scenario: resolve_model_id-without---config-preserves-legacy-behavior]
- [x] AC-31: WHEN `resolve_model_id --config orch.yaml --role not-a-real-role haiku` is called THEN stdout contains `claude-haiku-4-5-20251001` [REQ: set-common-sh-resolve-model-id-supports-config-and-role, scenario: invalid---role-with-valid-config-returns-the-positional-fallback]
- [x] AC-32: WHEN dispatcher.sh resolves the agent model for a change THEN the invocation includes `--config "$ORCH_YAML" --role agent` arguments before the positional fallback [REQ: lib-orchestration-shell-scripts-pass-config-role-to-resolve-model-id, scenario: dispatcher-sh-uses-resolve_model_id-with-role]
- [x] AC-33: WHEN digest.sh resolves the model for digest API calls THEN the invocation includes `--config "$ORCH_YAML" --role digest` arguments before the positional fallback [REQ: lib-orchestration-shell-scripts-pass-config-role-to-resolve-model-id, scenario: digest-sh-uses-resolve_model_id-with-role-digest]

### Capability: model-config-touch-point-coverage
- [x] AC-34: WHEN `dispatcher.resolve_change_model` is invoked with no `default_model` argument THEN the function consults `resolve_model("agent")` for its default [REQ: every-python-model-literal-is-replaced-by-a-resolve-model-call, scenario: dispatcher-resolve_change_model-uses-resolve_model-for-default]
- [x] AC-35: WHEN `digest.call_digest_api(...)` is called without an explicit `model` keyword THEN the function consults `resolve_model("digest")` [REQ: every-python-model-literal-is-replaced-by-a-resolve-model-call, scenario: digest-call_digest_api-uses-resolve_model-when-model-arg-is-none]
- [x] AC-36: WHEN `planner.decompose_brief(...)` is invoked without an explicit model THEN the function consults `resolve_model("decompose_brief")` [REQ: every-python-model-literal-is-replaced-by-a-resolve-model-call, scenario: planner-decompose_brief-uses-resolve_model-when-model-arg-is-none]
- [x] AC-37: WHEN `planner.decompose_domain(...)` is invoked without an explicit model THEN the function consults `resolve_model("decompose_domain")` [REQ: every-python-model-literal-is-replaced-by-a-resolve-model-call, scenario: planner-decompose_domain-uses-resolve_model-when-model-arg-is-none]
- [x] AC-38: WHEN `planner.decompose_merge(...)` is invoked without an explicit model THEN the function consults `resolve_model("decompose_merge")` [REQ: every-python-model-literal-is-replaced-by-a-resolve-model-call, scenario: planner-decompose_merge-uses-resolve_model-when-model-arg-is-none]
- [x] AC-39: WHEN the code-review gate runs its initial pass THEN it consults `resolve_model("review")` (default sonnet) AND when escalating after failure consults `resolve_model("review_escalation")` (default opus-4-6) [REQ: every-python-model-literal-is-replaced-by-a-resolve-model-call, scenario: verifier-review-gate-uses-resolve_model-for-initial-pass-and-escalation]
- [x] AC-40: WHEN the spec_verify gate runs THEN it consults `resolve_model("spec_verify")` for the initial pass AND `resolve_model("spec_verify_escalation")` for the escalation [REQ: every-python-model-literal-is-replaced-by-a-resolve-model-call, scenario: verifier-spec_verify-gate-uses-resolve_model-for-initial-pass-and-escalation]
- [x] AC-41: WHEN an `LLMVerdict` is constructed without an explicit model THEN the model field is populated from `resolve_model("classifier")` [REQ: every-python-model-literal-is-replaced-by-a-resolve-model-call, scenario: llm_verdict-classifier-uses-resolve_model]
- [x] AC-42: WHEN the canary monitor runs a health check THEN it consults `resolve_model("canary")` for the model arg [REQ: every-python-model-literal-is-replaced-by-a-resolve-model-call, scenario: canary-uses-resolve_model-for-canary-role]
- [x] AC-43: WHEN an `EphemeralRequest` is constructed without an explicit model THEN the model field is populated from `resolve_model("supervisor")` [REQ: every-python-model-literal-is-replaced-by-a-resolve-model-call, scenario: ephemeral-spawn-uses-resolve_model-for-caller-supplied-role]
- [x] AC-44: WHEN the supervisor triggers an action of type `integration_failed` THEN the model used is `resolve_model("trigger.integration_failed")` [REQ: every-python-model-literal-is-replaced-by-a-resolve-model-call, scenario: trigger-map-reads-resolve_model-for-each-trigger]
- [x] AC-45: WHEN `manager.supervisor.py` builds the sentinel.md command THEN the `--model` value is `resolve_model("supervisor")` [REQ: every-python-model-literal-is-replaced-by-a-resolve-model-call, scenario: manager-supervisor-py-uses-resolve_model-for-sentinel-agent]
- [x] AC-46: WHEN a `ChatSession` is constructed without an explicit model THEN `self.model = resolve_model("agent")` [REQ: every-python-model-literal-is-replaced-by-a-resolve-model-call, scenario: chat-chatsession-uses-resolve_model-on-init]
- [x] AC-47: WHEN `model_routing="complexity"` is active and the change is `complexity="S"` and `change_type != "feature"` THEN `resolve_change_model` returns `resolve_model("agent_small")` [REQ: dispatcher-complexity-routing-uses-agent-small-role, scenario: complexity-routing-returns-agent_small-for-s-non-feature]
- [x] AC-48: WHEN no override and `resolve_model("agent_small")` is called THEN the result is `"sonnet"` [REQ: dispatcher-complexity-routing-uses-agent-small-role, scenario: agent_small-default-is-sonnet]

### Capability: planner-prompt-foundational-uses-opus
- [x] AC-49: WHEN `render_brief_prompt(...)` is rendered with any input THEN the output contains a phrase tying `foundational` to `opus` [REQ: planner-prompt-instructs-foundational-changes-to-use-opus, scenario: render_brief_prompt-instructs-foundational-uses-opus]
- [x] AC-50: WHEN `render_brief_prompt(...)` is rendered THEN the output does NOT contain text suggesting `foundational` should use `sonnet` [REQ: planner-prompt-instructs-foundational-changes-to-use-opus, scenario: render_brief_prompt-does-not-say-foundational-uses-sonnet]
- [x] AC-51: WHEN `render_brief_prompt(...)` is rendered THEN the output identifies `infrastructure`, `schema`, `cleanup-before`, `cleanup-after` as the change_types that may use sonnet [REQ: planner-prompt-instructs-foundational-changes-to-use-opus, scenario: render_brief_prompt-names-the-sonnet-allowed-change_types-explicitly]
- [x] AC-52: WHEN `render_brief_prompt(...)` is rendered THEN the output contains a phrase advising opus as the safe default for ambiguous cases [REQ: planner-prompt-instructs-foundational-changes-to-use-opus, scenario: render_brief_prompt-advises-opus-when-unsure]
- [x] AC-53: WHEN `render_domain_decompose_prompt(...)` is rendered THEN if the prompt body mentions model selection it does NOT instruct foundational changes to use sonnet [REQ: planner-prompt-instructs-foundational-changes-to-use-opus, scenario: render_domain_decompose_prompt-also-reflects-foundational-opus]

### Capability: model-config-template-deployment
- [x] AC-54: WHEN the file `modules/web/set_project_web/templates/nextjs/set/orchestration/config.yaml` is read THEN it contains a `# models:` block listing each of the 13 leaf roles plus the trigger sub-dict, with role descriptions [REQ: web-template-ships-a-documented-models-block, scenario: deployed-config-yaml-contains-a-models-block-commented]
- [x] AC-55: WHEN the `models:` block in the deployed template is read THEN each role line has a comment explaining what the role does [REQ: web-template-ships-a-documented-models-block, scenario: each-documented-role-has-a-per-line-comment]
- [x] AC-56: WHEN `set-project init` is run on a fresh project THEN the resulting `set/orchestration/config.yaml` contains the commented `models:` block AND running `resolve_model("agent")` against the new project returns `"opus-4-6"` [REQ: web-template-ships-a-documented-models-block, scenario: deploying-the-template-produces-a-working-orchestration-yaml]
- [x] AC-57: WHEN `docs/release/v1.8.0.md` is read THEN it contains a one-line entry naming `models.agent` and the new default `opus-4-6` AND it documents the migration recipe [REQ: release-notes-document-the-agent-default-change-as-breaking, scenario: release-notes-mention-the-agent-default-change]
