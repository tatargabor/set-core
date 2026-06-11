## Why

With `ikp-bridge` providing the bridge module, the decomposer and dispatcher need to actually use it. The decomposer should read L1+L2 (knowledge + planning) layers to understand integration complexity and assign `ikp_packs` to each change. The dispatcher should inject L3 (implementation) as `.claude/rules/ikp-<pack>.md` into worktrees so agents get auth patterns, error handling code, and API boilerplate without wasting tokens on independent research. This is the wiring that makes IKP packs flow through the orchestration pipeline.

## What Changes

- **Decomposer** (`planner.py`): add IKP context section to `build_decomposition_context()` — pack summaries from L1+L2 with capabilities, complexity, and pitfalls. Enrich change metadata output schema with `ikp_packs: list[str]` field so the planner can assign relevant packs per change.
- **Dispatcher** (`dispatcher.py`): read `ikp_packs` from change metadata, call `ikp_bridge.inject_rules_for_change()` to write `ikp-<pack>.md` into worktree's `.claude/rules/`. Add IKP context section to `_build_input_content()` with pack overview (capabilities, env vars, pitfalls).
- **Category resolver**: add IKP-aware category detection — if a change has `ikp_packs`, add `integration` to its content categories so integration-relevant rules get injected.
- **Verify gate** (minimal): inject L4 (testing) summary into review prompt when the change has IKP packs — test fixtures, sandbox setup, edge cases the reviewer should check.

## Capabilities

### New Capabilities
- `ikp-decompose-context`: Decomposer reads IKP L1+L2 layers and includes integration context in the decomposition prompt; planner output includes `ikp_packs` per change
- `ikp-dispatch-injection`: Dispatcher injects IKP L3 implementation layers as rule files into agent worktrees based on change metadata

### Modified Capabilities
- `dispatch-core`: Add IKP rule injection step and IKP context section to input.md
- `change-category-resolver`: Add integration category when ikp_packs present
- `verify-review`: Include L4 testing context in review prompt for integration changes

## Impact

- `lib/set_orch/planner.py` — add IKP section to decomposition context, enrich output schema (~40 lines)
- `lib/set_orch/dispatcher.py` — add IKP rule injection + input.md section (~40 lines)
- `lib/set_orch/category_resolver.py` — add integration category (~10 lines)
- `lib/set_orch/verifier.py` — add L4 context to review prompt (~20 lines)
- Depends on `ikp-bridge` change being merged first
