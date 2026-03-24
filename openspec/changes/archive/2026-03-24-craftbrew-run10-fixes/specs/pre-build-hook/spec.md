# Pre-Build Hook

## Requirements

- PREBUILD-001: `ProfileType` ABC MUST have an `integration_pre_build(wt_path: str) -> bool` method with default no-op returning True.
- PREBUILD-002: `WebProjectType` MUST implement `integration_pre_build()` running `prisma db push --skip-generate --accept-data-loss` only (no seed, no generate).
- PREBUILD-003: `merger.py _run_integration_gates()` MUST call `profile.integration_pre_build(wt_path)` instead of `profile.e2e_pre_gate()` before the build gate.
- PREBUILD-004: If `integration_pre_build()` returns False, log warning but continue (non-blocking — build may still succeed without DB).
