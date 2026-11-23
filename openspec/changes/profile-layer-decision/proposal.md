## Why

The profile layer (`modules/web`, `modules/example`, `modules/mobile`, `profile_deploy`, the
`ProjectType` ABC) was built to feed the orchestration engine's gates. `set-project init` still
uses part of it (project types, templates, rules). Once stage 5 removes the engine, what remains
must be decided rather than inherited. Stage 6 of `fleet-era-consolidation`.

## What Changes

- Decide, per piece, keep / shrink / remove, keeping exactly what `set-project init` and the
  project types in use (including external Layer-3 types) need.

## Precondition

- Stage 5 done. A list of which `ProjectType` methods `init` and the doctor still call.

## Impact

`modules/`, `lib/set_orch/profile_*`, `lib/set_project_base/`, external plugins' entry points.
