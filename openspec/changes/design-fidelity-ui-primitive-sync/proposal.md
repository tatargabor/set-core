## Why

The `design-fidelity` skeleton check requires the agent to mount `v0-export/components/*.tsx` shells verbatim, but the v0 source frequently uses **extended shadcn primitive APIs** (e.g. `CommandDialog` accepting `title`/`description` props, newer `Dialog` variants) that the agent's project-side `components/ui/` does not implement. The result: skeleton check passes, then the next gate run dies with a TypeScript build error like `Property 'title' does not exist on type 'IntrinsicAttributes & DialogProps'`.

This is **not** a v0 bug, an agent bug, or a build/test/e2e bug — it is a contract gap between the design source (`v0-export/components/ui/`) and the project primitive layer (`src/components/ui/`). Right now the framework treats the two as independent, so any v0-side primitive customization causes a guaranteed retry cycle (skeleton-fail → mount → build-fail → patch primitives → re-mount → eventual pass after 2–3 expensive iterations).

Observed in a recent micro-web E2E run on a foundational-scaffold change: 2 verify attempts, first stop on `design-fidelity` (skeleton), second stop on `build` (TS error in a `command-palette.tsx` calling `<CommandDialog title=…>`), agent then patched `src/components/ui/command.tsx` manually to extend the type. Same drift class will hit every UI change for every v0 design that touches a shadcn primitive.

## What Changes

- **NEW** `set-design-import` SHALL sync `v0-export/components/ui/**` into `src/components/ui/**` whenever a v0-export is present, treating v0-export as the single source of truth for shadcn primitive APIs.
- **NEW** Sync is bidirectionally deterministic: every `set-design-import` run produces the same `src/components/ui/` content that `v0-export/components/ui/` defines (additive primitives appear, drift in shared primitives is overwritten).
- **NEW** Project-only primitives (files that exist in `src/components/ui/` but NOT in `v0-export/components/ui/`) are preserved untouched — the project may legitimately add primitives that v0 never used.
- **NEW** `design-fidelity` skeleton check SHALL include a `ui-primitive-skew` phase that detects when a v0 primitive file differs structurally from its project counterpart (signature/exports), reporting a blocking `ui-primitive-skew` violation with a remediation that points at `set-design-import --sync-ui` (escape hatch for the rare case where sync is intentionally disabled).
- **NEW** `orchestration.yaml` gains `design_import.sync_ui: true|false` (default: `true`). When `false`, the importer skips ui sync and the gate's skew detection becomes informational only — for projects that intentionally diverge their primitive layer.
- **NEW** Sync MUST log every overwrite at INFO level with file name, old hash, new hash so forensic review can trace primitive drift.
- Skeleton check MUST run BEFORE shell-mount checks so that skew is reported as the actionable root cause, not as downstream `shell-not-mounted`.

## Capabilities

### New Capabilities

- `v0-ui-primitive-sync`: defines the contract for syncing `v0-export/components/ui/` into `src/components/ui/` — what files are in scope, what's preserved, what's overwritten, how the sync is logged, and how operators opt out.

### Modified Capabilities

- `v0-design-import`: add the new sync step to `set-design-import` (full and `--regenerate-manifest` runs); document the `design_import.sync_ui` config knob; specify ordering relative to existing tsconfig patching.
- `design-fidelity-gate`: add the `ui-primitive-skew` phase to `run_skeleton_check`; specify ordering (skew before shell-mount); specify config-driven severity downgrade when `design_import.sync_ui` is disabled.

## Impact

- **Code**: `modules/web/set_project_web/v0_importer.py` (new sync logic), `modules/web/set_project_web/v0_fidelity_gate.py` (new skew phase), `modules/web/set_project_web/design_import_cli.py` (config plumbing).
- **Configs**: `orchestration.yaml` schema — new optional `design_import.sync_ui` boolean.
- **Behavior**: every existing web project that has both `v0-export/` and `src/components/ui/` will, on next `set-design-import`, see overwrites in `src/components/ui/`. **This is the intent**, but it IS a one-time observable disk change. Projects that already manually diverged their ui layer will need `design_import.sync_ui: false` in their `orchestration.yaml` before the next import — call this out in the migration note.
- **Gate retry cycles**: eliminates the skeleton→build→patch→retry loop documented above. Projected savings ~1 retry attempt (~5 min + ~$1 token cost) per v0-driven change that touches a primitive.
- **No impact** on non-web profiles, on changes without `v0-export/`, or on projects that intentionally set `sync_ui: false`.
