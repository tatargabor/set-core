## ADDED Requirements

### Requirement: set-design-import syncs ui primitives from v0-export

The `set-design-import` CLI SHALL invoke the ui-primitive sync (defined in capability `v0-ui-primitive-sync`) after fetching `v0-export/` content but before regenerating the manifest. The sync MUST run on both full imports (`--git <url>`) and `--regenerate-manifest` invocations. The sync MUST be skipped when `design_import.sync_ui` is `false` in `orchestration.yaml` or when `--no-sync-ui` is passed on the command line.

#### Scenario: Full import triggers ui sync

- **WHEN** `set-design-import --git <url>` runs against a scaffold that has `v0-export/components/ui/command.tsx` differing from `src/components/ui/command.tsx`
- **THEN** after the CLI exits successfully `src/components/ui/command.tsx` matches `v0-export/components/ui/command.tsx` byte-for-byte
- **AND** the run summary names the count of primitives synced

#### Scenario: Regenerate-manifest triggers ui sync

- **WHEN** `set-design-import --regenerate-manifest` runs against a scaffold whose `v0-export/` was updated to a newer ref
- **THEN** the ui-primitive sync executes with the same semantics as a full import
- **AND** the manifest regeneration runs to completion in the same invocation

#### Scenario: Sync ordering — fetch → sync ui → patch tsconfig → regenerate manifest

- **WHEN** `set-design-import --git <url>` runs
- **THEN** the CLI executes phases in this order: fetch v0 content, sync ui primitives, patch tsconfig exclude, regenerate manifest
- **AND** a failure in any phase produces a clear log identifying which phase failed

### Requirement: --no-sync-ui flag is documented in --help

The `set-design-import` CLI's `--help` output SHALL document the `--no-sync-ui` flag with a description that names the YAML equivalent (`design_import.sync_ui: false`).

#### Scenario: --help mentions the flag

- **WHEN** the operator runs `set-design-import --help`
- **THEN** the output includes a `--no-sync-ui` entry
- **AND** the description references `design_import.sync_ui` as the YAML equivalent
