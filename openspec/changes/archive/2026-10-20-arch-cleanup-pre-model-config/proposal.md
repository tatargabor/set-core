## Why

The recent v0 design integration and 3-phase decompose rewrite (commits `e452b785`, `c156f6ff`, `53c885cd`, `66d8f289`, et al.) introduced four issues that block a clean rollout of the upcoming unified model-config: web-specific knowledge leaked into Layer 1 (`lib/set_orch/planner.py` hardcodes `vitest`/`jest`/`mocha`/`prisma`/`v0-export`); the test-bundling guards swallow profile-load exceptions and degrade silently to no enforcement on Core profile; the domain decompose prompt schema requires `change_type` but never tells the LLM to set it (the model assignment downstream depends on this field); and `chat.py` session-resume invocations omit `--model`, relying on Claude CLI's session-cache for model preservation. The next change layers a unified model config on top of these touch points — landing it on this foundation would inherit each defect.

## What Changes

- Move web-specific detection out of `lib/set_orch/planner.py` to new `ProjectType` hooks (`detect_test_framework`, `detect_schema_provider`, `get_design_globals_path`); CoreProfile returns neutral defaults; WebProjectType supplies the concrete vitest/prisma/v0-export values.
- Make the test-bundling profile-load guards in `lib/set_orch/templates.py::_get_test_bundling_directives` and `lib/set_orch/planner.py::_assert_no_standalone_test_changes` fail-loud (logger.warning on profile-load exception) and add a profile-independent universal-prefix backstop (`test-`, `e2e-`, `playwright-`, `vitest-`) so CoreProfile users still get protection.
- Add an explicit textual `change_type` requirement to `render_domain_decompose_prompt` so the LLM cannot drop the field. Schema already lists it; instruction now matches.
- Fix `lib/set_orch/chat.py` session-resume to always pass `--model`, even on `--resume`. **BREAKING** for any caller depending on the implicit Anthropic-server-side model preservation across resumed sessions.

## Capabilities

### New Capabilities
- `profile-arch-hooks`: ProjectType ABC hooks for test framework, schema provider, and design globals path; CoreProfile defaults; WebProjectType overrides.
- `decompose-failsafe`: Fail-loud profile-load handling and universal-prefix backstop in test-bundling guards.
- `decompose-change-type-instruction`: Explicit textual change_type requirement in domain decompose prompt.
- `chat-explicit-model`: chat.py CLI invocations always pass --model, including on --resume.

### Modified Capabilities
<!-- None. Existing decompose-test-bundling spec stays unchanged; this change only hardens its enforcement path. -->

## Impact

- **Affected files (Layer 1)**: `lib/set_orch/planner.py` (extract hardcodes), `lib/set_orch/templates.py` (fail-loud + change_type instruction), `lib/set_orch/profile_types.py` (new hooks), `lib/set_orch/profile_loader.py::CoreProfile` (default implementations), `lib/set_orch/chat.py` (session-resume model).
- **Affected files (Layer 2)**: `modules/web/set_project_web/project_type.py` (concrete overrides for new hooks).
- **Tests**: extend `tests/unit/test_decompose_test_bundling.py` for fail-loud paths and universal-prefix backstop; add `tests/unit/test_profile_arch_hooks.py` for the new hooks (core defaults + web overrides); add a regression test asserting `chat.py` always emits `--model` in cmd.
- **Consumer projects**: no template changes; the new hooks are accessed via the existing profile-loader chain.
- **Downstream**: this change unblocks `model-config-unified` (Phase B), which will introduce the central `models:` block in orchestration.yaml that depends on the new hooks and fail-loud guards.
