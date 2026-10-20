## Why

When orchestrating projects with external API integrations (Billingo, Wise, Gmail, Stripe, etc.), agents waste significant tokens researching integration patterns independently. The IKP (Integration Knowledge Pack) system at `~/code2/ikp/` provides pre-verified, layered integration knowledge — but set-core has no way to consume it. A bridge module is needed so the decomposer, dispatcher, and verify gate can load IKP packs at the right phase with the right layers.

## What Changes

- Add `lib/set_orch/ikp_bridge.py` — thin wrapper over the `ikp` Python package providing set-core-native functions: config loading, pack discovery, phase-appropriate layer loading, and rule file injection into worktrees
- Add `.ikp.yaml` config format support — projects declare which packs they use and where pack files live
- Add `ikp_pipeline` directive to `orchestration.yaml` — controls whether IKP integration is active (auto/none, analogous to `design_pipeline`)
- IKP is an optional dependency — if the `ikp` package is not installed, the pipeline gracefully skips (like `has_design_pipeline`)

## Capabilities

### New Capabilities
- `ikp-bridge`: Core IKP bridge module — config loading, pack discovery, layer loading by phase, rule file injection, graceful degradation when ikp package unavailable

### Modified Capabilities
- `orchestration-config`: Add `ikp_pipeline` directive (auto/none) to DIRECTIVE_DEFAULTS

## Impact

- `lib/set_orch/ikp_bridge.py` — new module (~200 lines)
- `lib/set_orch/config.py` — add ikp_pipeline directive
- `pyproject.toml` — add ikp as optional dependency (`[project.optional-dependencies] ikp = ["ikp"]`)
- Consumer projects need `.ikp.yaml` at project root to opt in
