## ADDED Requirements

### Requirement: ui sync overwrites shared files

The sync logic SHALL, for each `*.tsx` file under `v0-export/components/ui/`, write its content to the corresponding path under `src/components/ui/` whenever the existing target's bytes differ. The sync MUST preserve relative subdirectory structure (e.g. `v0-export/components/ui/sidebar/sidebar-menu.tsx` → `src/components/ui/sidebar/sidebar-menu.tsx`).

#### Scenario: Shared file with different content is overwritten

- **GIVEN** `v0-export/components/ui/command.tsx` exports `CommandDialog` with optional `title`/`description` props
- **AND** `src/components/ui/command.tsx` exports `CommandDialog` without those props
- **WHEN** `set-design-import` runs
- **THEN** `src/components/ui/command.tsx` is overwritten with the v0 content
- **AND** an INFO log line records `synced ui primitive components/ui/command.tsx old=sha256:<…> new=sha256:<…>`

#### Scenario: Shared file with identical content is a no-op

- **GIVEN** `v0-export/components/ui/button.tsx` and `src/components/ui/button.tsx` are byte-identical
- **WHEN** `set-design-import` runs
- **THEN** the file's mtime on disk is unchanged
- **AND** only a DEBUG log records the comparison

#### Scenario: Subdirectory structure preserved

- **GIVEN** `v0-export/components/ui/sidebar/sidebar-menu.tsx` exists
- **AND** `src/components/ui/sidebar/` does not yet exist in the project
- **WHEN** `set-design-import` runs
- **THEN** `src/components/ui/sidebar/sidebar-menu.tsx` is created with v0's content
- **AND** intermediate directory `src/components/ui/sidebar/` is created if missing

### Requirement: ui sync creates missing files

When `v0-export/components/ui/<name>.tsx` exists but `src/components/ui/<name>.tsx` does not, the sync MUST create the target file with v0's content. The intermediate `src/components/ui/` directory MUST be created if it does not exist.

#### Scenario: Missing file is created

- **GIVEN** `v0-export/components/ui/sonner.tsx` exists
- **AND** `src/components/ui/sonner.tsx` does not exist in the project
- **WHEN** `set-design-import` runs
- **THEN** `src/components/ui/sonner.tsx` is created with v0's content
- **AND** an INFO log line records `added ui primitive components/ui/sonner.tsx hash=sha256:<…>`

### Requirement: ui sync preserves project-only files

When `src/components/ui/<name>.tsx` exists and has NO counterpart at `v0-export/components/ui/<name>.tsx`, the sync MUST leave it untouched. The sync MUST NOT delete files from `src/components/ui/`.

#### Scenario: Project-only primitive is preserved

- **GIVEN** `src/components/ui/payment-card.tsx` exists in the project
- **AND** `v0-export/components/ui/payment-card.tsx` does not exist
- **WHEN** `set-design-import` runs
- **THEN** `src/components/ui/payment-card.tsx` is byte-identical before and after the run

#### Scenario: Sync never deletes

- **GIVEN** `src/components/ui/legacy-modal.tsx` exists with no v0 counterpart
- **WHEN** `set-design-import` runs
- **THEN** `src/components/ui/legacy-modal.tsx` still exists on disk

### Requirement: Opt-out via orchestration config

The orchestration config schema SHALL accept an optional `design_import.sync_ui` boolean (default `true`). When set to `false`, `set-design-import` MUST skip the ui sync entirely, and the design-fidelity gate's `ui-primitive-skew` phase MUST downgrade its findings to non-blocking warnings (specified in the `design-fidelity-gate` spec delta).

#### Scenario: sync_ui=false skips the sync

- **GIVEN** `orchestration.yaml` contains `design_import:\n  sync_ui: false`
- **WHEN** `set-design-import` runs
- **THEN** no file under `src/components/ui/` is created or modified by the importer
- **AND** an INFO log line records `ui sync skipped (design_import.sync_ui=false)`

#### Scenario: Default behavior is sync ON

- **GIVEN** `orchestration.yaml` is silent on `design_import.sync_ui`
- **WHEN** `set-design-import` runs
- **THEN** the sync runs as if `sync_ui: true` were set explicitly

### Requirement: --no-sync-ui CLI flag

The `set-design-import` CLI SHALL accept a `--no-sync-ui` flag that overrides the YAML knob and skips the sync for that invocation. The flag MUST take precedence over `design_import.sync_ui: true` in `orchestration.yaml`.

#### Scenario: CLI flag overrides YAML

- **GIVEN** `orchestration.yaml` contains `design_import:\n  sync_ui: true`
- **WHEN** the operator runs `set-design-import --no-sync-ui`
- **THEN** the sync is skipped for that invocation
- **AND** an INFO log line records the skip with reason `--no-sync-ui flag`

### Requirement: Sync runs on both full import and regenerate-manifest

The sync SHALL execute on both `set-design-import --git <url>` (full import) and `set-design-import --regenerate-manifest` invocations. Behavior MUST be identical between the two modes — sync semantics are not gated by which mode was invoked.

#### Scenario: Sync runs on regenerate-manifest

- **GIVEN** an existing scaffold with `v0-export/components/ui/command.tsx` updated since the last sync
- **AND** `src/components/ui/command.tsx` still has the older content
- **WHEN** `set-design-import --regenerate-manifest` runs
- **THEN** `src/components/ui/command.tsx` is overwritten with the new v0 content
- **AND** the manifest regeneration completes normally
