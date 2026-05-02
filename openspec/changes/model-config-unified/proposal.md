## Why

LLM model selection in the orchestration pipeline is currently spread across 40+ touch points (per-change agent in `plan.json`, planner Phase 1/2/3 calls, code-review and spec-verify gates with implicit sonnet→opus escalation, llm-verdict classifier, supervisor/canary/sentinel triggers, dispatcher routing, bash mirror in `bin/set-common.sh`, deployed `orchestration.yaml` template). Each touch point uses its own default — the values are scattered across function signatures, dataclass fields, hardcoded constants, and shell case statements. There is no single place an operator can change "what model runs at step X" without grepping the codebase. Two concrete pain points motivated this change: (a) the foundational change `navigation-chrome` ran for 134 minutes on sonnet vs the prior run's `site-header-and-mobile-nav` finishing in 14 minutes on opus — the planner LLM extended its "sonnet for infrastructure/cleanup/docs" guidance to `foundational`, and we had no override; (b) we want to pin the agent model to `opus-4-6` for the next run instead of the current `opus` alias (which resolves to `opus-4-7`), to test cost/quality on a less aggressive variant. Phase A (`arch-cleanup-pre-model-config`) just landed the Layer-1 hooks, fail-loud guards, and `chat.py --model` invariant that this change builds on.

## What Changes

- Add a unified `models:` block to the directive schema (`lib/set_orch/config.py::DIRECTIVE_DEFAULTS`) covering every orchestration touch point: `agent`, `digest`, `decompose_brief`, `decompose_domain`, `decompose_merge`, `review`, `review_escalation`, `spec_verify`, `spec_verify_escalation`, `classifier`, `supervisor`, `canary`, and the `trigger.{integration_failed,non_periodic_checkpoint,terminal_state,default}` mapping.
- **BREAKING** for `agent` default: change from `opus` (alias for `opus-4-7`) to `opus-4-6`. All other defaults preserve current behavior.
- New `lib/set_orch/model_config.py::resolve_model(role, *, project_dir=".")` helper implements the resolution chain `CLI flag → ENV var (SET_ORCH_MODEL_<KEY>) → orchestration.yaml models block → profile.model_for(role) → DIRECTIVE_DEFAULTS → hardcoded last-resort`. Helper validates returned name against the existing model-name regex and raises a clear error on invalid input.
- Add `model_for(role: str) -> Optional[str]` to `ProjectType` ABC. CoreProfile returns None (no override). Plugins can supply per-stack model preferences.
- Replace every hardcoded model name in the 40+ touch-point inventory with a `resolve_model(role)` call. The hardcoded constants stay in source as the last-resort fallback inside `resolve_model`, but no other call site holds a literal model name.
- **Sonnet-routing fix in the planner prompt template** (`lib/set_orch/templates.py`): the existing instructions tell the LLM "use opus for features, sonnet for infrastructure/cleanup/docs". Extend this to explicitly state `foundational → opus` so foundational changes are not downgraded to sonnet (root cause of the 134m navigation-chrome run).
- CLI flags expose every role: `--agent-model`, `--digest-model`, `--decompose-brief-model`, `--decompose-domain-model`, `--decompose-merge-model`, `--review-model`, `--review-escalation-model`, `--spec-verify-model`, `--spec-verify-escalation-model`, `--classifier-model`, `--supervisor-model`, `--canary-model`. Also a meta `--model-profile <preset>` shortcut with presets `all-opus-4-6`, `all-opus-4-7`, `cost-optimized`, `default`.
- Bash mirror in `bin/set-common.sh` (`resolve_model_id`) gains a `--config <orchestration.yaml>` flag that reads the `models:` block and respects the same role keys. Shell scripts under `lib/orchestration/` that exec set-orch-core pass the resolved model via the existing env-or-arg path.
- Update the consumer-deployed template (`modules/web/set_project_web/templates/nextjs/set/orchestration/config.yaml`) with a documented `models:` block (commented-out by default — defaults apply).
- **Migration**: existing `orchestration.yaml` files without a `models:` block continue working via DIRECTIVE_DEFAULTS. The `agent` default change to `opus-4-6` IS a behavior change — release notes call it out explicitly. Operators that want the prior behavior set `models.agent: opus-4-7` (or `opus`) in their config.

## Capabilities

### New Capabilities
- `model-config-schema`: `models:` directive block schema, validation, DIRECTIVE_DEFAULTS, and `opus-4-6` agent default.
- `model-resolution-chain`: `resolve_model(role)` helper + the 5-tier resolution chain (CLI → ENV → models.yaml → profile → DEFAULTS).
- `model-config-cli`: per-role CLI flags + `--model-profile` shortcut presets.
- `model-config-bash-mirror`: bash `resolve_model_id --config` support and shell→python plumbing.
- `model-config-touch-point-coverage`: every model-using call site reads via `resolve_model`; no model literals elsewhere.
- `planner-prompt-foundational-uses-opus`: planner prompt template explicitly says foundational → opus, not sonnet.
- `model-config-template-deployment`: web template ships a documented `models:` block.

### Modified Capabilities
<!-- None. The decompose-test-bundling, profile-arch-hooks, decompose-failsafe, decompose-change-type-instruction, and chat-explicit-model capabilities from Phase A stay unchanged; this change reads them but doesn't modify their requirements. -->

## Impact

- **Affected Layer 1 files**: `lib/set_orch/config.py` (schema + defaults), `lib/set_orch/model_config.py` (NEW — resolver), `lib/set_orch/profile_types.py` (`model_for` ABC method), `lib/set_orch/profile_loader.py::CoreProfile` (None default), `lib/set_orch/cli.py` (12+ new flags), `lib/set_orch/dispatcher.py` (resolver in `resolve_change_model`), `lib/set_orch/digest.py` (resolver in `call_digest_api`), `lib/set_orch/planner.py` (resolver in `decompose_brief/domain/merge`), `lib/set_orch/templates.py` (foundational→opus prompt edit), `lib/set_orch/verifier.py` (resolver in review + spec_verify), `lib/set_orch/llm_verdict.py` (resolver in classifier), `lib/set_orch/supervisor/canary.py` + `ephemeral.py` + `triggers.py` (resolver in canary + ephemeral + trigger map), `lib/set_orch/manager/supervisor.py` (resolver for supervisor agent), `lib/set_orch/chat.py` (resolver in ChatSession init).
- **Affected Layer 2 files**: `modules/web/set_project_web/project_type.py` (optional `model_for` override; default no-op), `modules/web/set_project_web/templates/nextjs/set/orchestration/config.yaml` (documented `models:` block).
- **Affected bash files**: `bin/set-common.sh` (`resolve_model_id --config`), `lib/orchestration/dispatcher.sh` + `lib/orchestration/digest.sh` (use the new helper).
- **Tests**: `tests/unit/test_model_config.py` (NEW — resolution chain, CLI/ENV/yaml/profile/defaults order, validation, presets, opus-4-6 default), extend `tests/unit/test_dispatcher.py`, `tests/unit/test_planner.py`, `tests/unit/test_verifier.py`, `tests/unit/test_supervisor_*.py` to assert each role uses `resolve_model` rather than hardcoded literals.
- **Consumer projects**: existing `orchestration.yaml` files keep working; new projects deployed via `set-project init` get the documented `models:` block. Operators that want the prior agent default explicitly set `models.agent: opus-4-7` (or `opus`).
- **Cost**: opus-4-6 is older and currently cheaper per token than opus-4-7. The aggregate cost of an end-to-end run on the new default may shift slightly; the `cost-optimized` preset can pin all roles to lower-tier models for further savings.
- **Downstream**: this change unblocks operator-controlled model experimentation per role (e.g., test sonnet-only orchestration, opus-only mode, hybrid configurations) without code edits.
