## Why

The verification pipeline runs the same 7 gates for every change regardless of its nature. Infrastructure/setup changes fail smoke/build/e2e gates because there's no running app yet, wasting 200-400k tokens per orchestration run on false failures and unnecessary retries. E2E runs #4, #13, #14 all show this pattern: `test-infrastructure-setup` gets smoke false-fails, schema changes get unnecessary e2e runs, cleanup changes get full review cycles they don't need.

## What Changes

- Add a gate profile system that maps `change_type` to a `GateConfig` determining which gates run and whether failures block or warn
- Built-in profiles for all 6 change types (infrastructure, schema, foundational, feature, cleanup-before, cleanup-after) with sensible defaults
- 4-level resolution chain: built-in defaults → project-type plugin overrides → per-change `gate_hints` from plan → orchestration.yaml directive overrides
- Verifier pipeline (`handle_change_done`) uses resolved `GateConfig` instead of running all gates unconditionally
- Merger smoke gate respects `GateConfig.smoke` setting
- Gate modes: `"run"` (blocking), `"skip"` (don't execute), `"warn"` (execute but non-blocking), `"soft"` (non-blocking if other gates pass)
- Planning rules updated so LLM understands gate profiles are derived from `change_type` automatically
- Event logging includes gate profile info (skipped/warned gates)

## Capabilities

### New Capabilities
- `gate-profiles`: Gate profile resolution system — GateConfig dataclass, built-in profiles per change_type, resolve_gate_config() resolution chain, project-type plugin gate_overrides() extension point

### Modified Capabilities
- `verify-gate`: VG-PIPELINE gate execution now conditional on resolved GateConfig; gates can be skip/warn/soft per change_type
- `per-change-gate-skip`: Existing skip_test/skip_review mapped into GateConfig; new gate_hints dict for fine-grained per-change overrides

## Impact

- `lib/set_orch/gate_profiles.py` — new module (GateConfig, BUILTIN_GATE_PROFILES, resolve_gate_config)
- `lib/set_orch/verifier.py` — handle_change_done uses GateConfig for all gate decisions
- `lib/set_orch/merger.py` — post_merge_smoke checks GateConfig.smoke
- `lib/set_orch/state.py` — Change dataclass gets gate_hints field
- `lib/set_orch/templates.py` — planning rules + JSON schema updated with gate profile info and gate_hints
- `lib/set_orch/profile_loader.py` — NullProfile gets gate_overrides()
- `lib/set_orch/config.py` — gate_overrides directive for runtime tuning
- `set-project-base/base.py` — ProjectType ABC gets gate_overrides() method
- `set-project-web/project_type.py` — web-specific gate overrides (foundational+e2e, schema+build)
- Zero breaking changes: feature type = all gates run (identical to current behavior)
