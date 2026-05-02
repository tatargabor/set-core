## 1. Sync logic in v0_importer

- [ ] 1.1 Add `sync_ui_primitives(v0_export_dir, project_dir)` to `modules/web/set_project_web/v0_importer.py` that walks `v0_export_dir/components/ui/**.tsx`, mirrors each file under `project_dir/src/components/ui/`, creates parents, overwrites on byte difference, never deletes [REQ: ui-sync-overwrites-shared-files]
- [ ] 1.2 Make `sync_ui_primitives` create missing target files with v0 content and create intermediate directories as needed [REQ: ui-sync-creates-missing-files]
- [ ] 1.3 Make `sync_ui_primitives` leave files in `src/components/ui/` that have no v0 counterpart untouched, and never call any delete operation on `src/components/ui/` [REQ: ui-sync-preserves-project-only-files]
- [ ] 1.4 Emit INFO log per overwrite (`synced ui primitive <relpath> old=sha256:<…> new=sha256:<…>`) and per add (`added ui primitive <relpath> hash=sha256:<…>`); DEBUG-only on byte-equal no-op [REQ: ui-sync-overwrites-shared-files]
- [ ] 1.5 Preserve subdirectory structure (e.g. `v0-export/components/ui/sidebar/x.tsx` → `src/components/ui/sidebar/x.tsx`) [REQ: ui-sync-overwrites-shared-files]

## 2. CLI plumbing in design_import_cli

- [ ] 2.1 Read `design_import.sync_ui` boolean from the project's `orchestration.yaml` (default `true` when key absent or section missing) in `modules/web/set_project_web/design_import_cli.py` [REQ: opt-out-via-orchestration-config]
- [ ] 2.2 Add `--no-sync-ui` argparse flag to `set-design-import`; flag wins over YAML when both are present [REQ: --no-sync-ui-cli-flag]
- [ ] 2.3 Document `--no-sync-ui` in `--help` output, naming `design_import.sync_ui` as the YAML equivalent [REQ: --no-sync-ui-flag-is-documented-in---help]
- [ ] 2.4 Wire the call: after v0-export fetch and before tsconfig patch, call `sync_ui_primitives` (skip when disabled, log the skip with reason) [REQ: set-design-import-syncs-ui-primitives-from-v0-export]
- [ ] 2.5 Ensure phase ordering inside `design_import_cli` is fetch → sync ui → patch tsconfig → regenerate manifest, with per-phase failure logging [REQ: set-design-import-syncs-ui-primitives-from-v0-export]
- [ ] 2.6 Run sync on both full import and `--regenerate-manifest` paths with identical semantics [REQ: sync-runs-on-both-full-import-and-regenerate-manifest]

## 3. Skew detection in v0_fidelity_gate

- [ ] 3.1 Add `_extract_primitive_signatures(file: Path) -> dict[str, set[str]]` to `modules/web/set_project_web/v0_fidelity_gate.py`: regex-walks `*.tsx` for top-level exports plus the field set of each export's first-parameter Props type [REQ: ui-primitive-skew-detection-phase]
- [ ] 3.2 Add `run_ui_primitive_skew_check(wt_path, v0_export_dir) -> list[Violation]` that compares signatures pairwise and emits `ui-primitive-skew` violations naming file/export/missing-fields [REQ: ui-primitive-skew-detection-phase]
- [ ] 3.3 Treat project Props as superset-of-v0 = no violation; treat strict-subset = violation; ignore project-only primitives [REQ: ui-primitive-skew-detection-phase]
- [ ] 3.4 Hook the skew phase into `run_skeleton_check` BEFORE the existing shell-mount and shell-shadow phases [REQ: phase-ordering---skew-before-shell-not-mounted]
- [ ] 3.5 Order any aggregated `retry_context` so `ui-primitive-skew` items appear before `missing-shared-file` and `shell-not-mounted` items [REQ: phase-ordering---skew-before-shell-not-mounted]

## 4. Severity routing in the gate

- [ ] 4.1 Treat `ui-primitive-skew` as a blocking status by adding it to `blocking_statuses` in `_run_gate` (`v0_fidelity_gate.py`) when `design_import.sync_ui` is `true` (default) [REQ: ui-primitive-skew-is-blocking-by-default]
- [ ] 4.2 Build the retry context to name `set-design-import` (or `--regenerate-manifest`) as the canonical fix; do NOT instruct the agent to hand-edit primitive types [REQ: ui-primitive-skew-is-blocking-by-default]
- [ ] 4.3 Read `design_import.sync_ui` from the project's orchestration config inside the gate; when `false`, downgrade `ui-primitive-skew` violations to non-blocking warnings (gate result PASS-with-warning, no retry) [REQ: ui-primitive-skew-downgrades-to-warning-when-sync_ui-is-disabled]
- [ ] 4.4 Ensure WARN-mode output still names the missing field(s) so operators can see the drift [REQ: ui-primitive-skew-downgrades-to-warning-when-sync_ui-is-disabled]

## 5. Tests

- [ ] 5.1 Unit test in `modules/web/tests/` covering `sync_ui_primitives`: byte-different overwrite, byte-equal no-op, missing-file create, project-only preserve, never-delete, subdir mirror [REQ: ui-sync-overwrites-shared-files, REQ: ui-sync-creates-missing-files, REQ: ui-sync-preserves-project-only-files]
- [ ] 5.2 Unit test for `_extract_primitive_signatures` against fixture v0 + project `command.tsx` files where the project lacks `title`/`description` — confirm the violation lists those fields exactly [REQ: ui-primitive-skew-detection-phase]
- [ ] 5.3 Unit test for the superset case (project wider than v0) — confirm no violation emitted [REQ: ui-primitive-skew-detection-phase]
- [ ] 5.4 Unit test for the cosmetic-only case (whitespace/import-order/comment differences) — confirm no violation emitted [REQ: ui-primitive-skew-detection-phase]
- [ ] 5.5 Unit test for `--no-sync-ui` CLI flag and `design_import.sync_ui: false` YAML — confirm sync is skipped in both cases and YAML-only path emits the documented INFO log [REQ: opt-out-via-orchestration-config, REQ: --no-sync-ui-cli-flag]
- [ ] 5.6 Integration test (or runner-driven E2E reproduction): re-run the `micro-web` runner with the change applied and assert `foundational-scaffold-and-shell` reaches all-green in 1 verify attempt (down from 2+) [REQ: set-design-import-syncs-ui-primitives-from-v0-export]

## 6. Docs and rules

- [ ] 6.1 Update `templates/core/rules/design-bridge.md` to describe ui-primitive sync semantics (this file deploys to consumer projects via `set-project init`) — keep external project names out per CLAUDE.md confidentiality [REQ: set-design-import-syncs-ui-primitives-from-v0-export]
- [ ] 6.2 Update `lib/set_orch/.../audit` (or wherever `set-audit scan` formats output) to surface `design_import.sync_ui` setting so operators can verify their opt-out [REQ: opt-out-via-orchestration-config]
- [ ] 6.3 Add a one-line note to `tests/e2e/README.md` describing that fresh runs now sync ui primitives at scaffold time [REQ: set-design-import-syncs-ui-primitives-from-v0-export]

## Acceptance Criteria (from spec scenarios)

### Capability: v0-ui-primitive-sync

- [ ] AC-1: WHEN `set-design-import` runs against a scaffold where v0's `command.tsx` declares `title?`/`description?` and the project's omits them THEN `src/components/ui/command.tsx` is overwritten with v0 content AND an INFO log records old/new sha256 hashes [REQ: ui-sync-overwrites-shared-files, scenario: shared-file-with-different-content-is-overwritten]
- [ ] AC-2: WHEN `set-design-import` runs and `v0-export/components/ui/button.tsx` is byte-identical to the project copy THEN file mtime is unchanged AND only DEBUG log records the comparison [REQ: ui-sync-overwrites-shared-files, scenario: shared-file-with-identical-content-is-a-no-op]
- [ ] AC-3: WHEN `set-design-import` runs and `v0-export/components/ui/sidebar/sidebar-menu.tsx` exists but `src/components/ui/sidebar/` does not THEN the target file and intermediate dir are created [REQ: ui-sync-overwrites-shared-files, scenario: subdirectory-structure-preserved]
- [ ] AC-4: WHEN `set-design-import` runs and `v0-export/components/ui/sonner.tsx` exists but the project does not have it THEN `src/components/ui/sonner.tsx` is created with v0 content AND an INFO log records the add with hash [REQ: ui-sync-creates-missing-files, scenario: missing-file-is-created]
- [ ] AC-5: WHEN `set-design-import` runs and `src/components/ui/payment-card.tsx` exists with no v0 counterpart THEN the file is byte-identical before and after [REQ: ui-sync-preserves-project-only-files, scenario: project-only-primitive-is-preserved]
- [ ] AC-6: WHEN `set-design-import` runs and `src/components/ui/legacy-modal.tsx` exists with no v0 counterpart THEN the file still exists on disk after the run [REQ: ui-sync-preserves-project-only-files, scenario: sync-never-deletes]
- [ ] AC-7: WHEN `orchestration.yaml` has `design_import.sync_ui: false` AND `set-design-import` runs THEN no file under `src/components/ui/` is created or modified AND an INFO log records the skip reason [REQ: opt-out-via-orchestration-config, scenario: sync_ui-false-skips-the-sync]
- [ ] AC-8: WHEN `orchestration.yaml` is silent on `design_import.sync_ui` AND `set-design-import` runs THEN sync runs as if `sync_ui: true` was set [REQ: opt-out-via-orchestration-config, scenario: default-behavior-is-sync-on]
- [ ] AC-9: WHEN `orchestration.yaml` has `design_import.sync_ui: true` AND operator runs `set-design-import --no-sync-ui` THEN the sync is skipped AND an INFO log records the `--no-sync-ui flag` reason [REQ: --no-sync-ui-cli-flag, scenario: cli-flag-overrides-yaml]
- [ ] AC-10: WHEN `set-design-import --regenerate-manifest` runs against a scaffold with newer v0 content THEN `src/components/ui/command.tsx` is overwritten AND manifest regen completes in the same invocation [REQ: sync-runs-on-both-full-import-and-regenerate-manifest, scenario: sync-runs-on-regenerate-manifest]

### Capability: v0-design-import

- [ ] AC-11: WHEN `set-design-import --git <url>` runs and `v0-export/components/ui/command.tsx` differs from `src/components/ui/command.tsx` THEN after CLI exit the project file matches v0 byte-for-byte AND the run summary names the count synced [REQ: set-design-import-syncs-ui-primitives-from-v0-export, scenario: full-import-triggers-ui-sync]
- [ ] AC-12: WHEN `set-design-import --regenerate-manifest` runs and v0-export was updated to a newer ref THEN the ui sync executes and the manifest regen runs to completion [REQ: set-design-import-syncs-ui-primitives-from-v0-export, scenario: regenerate-manifest-triggers-ui-sync]
- [ ] AC-13: WHEN `set-design-import --git <url>` runs THEN phases execute in order: fetch v0 → sync ui → patch tsconfig → regenerate manifest, with per-phase failure logging [REQ: set-design-import-syncs-ui-primitives-from-v0-export, scenario: sync-ordering---fetch--sync-ui--patch-tsconfig--regenerate-manifest]
- [ ] AC-14: WHEN operator runs `set-design-import --help` THEN `--no-sync-ui` is listed AND its description references `design_import.sync_ui` as the YAML equivalent [REQ: --no-sync-ui-flag-is-documented-in---help, scenario: --help-mentions-the-flag]

### Capability: design-fidelity-gate

- [ ] AC-15: WHEN v0's `CommandDialog` Props declares `title?`/`description?` and project's omits them THEN a `ui-primitive-skew` violation is emitted naming `components/ui/command.tsx`, export `CommandDialog`, fields `title`, `description` [REQ: ui-primitive-skew-detection-phase, scenario: missing-prop-on-shared-primitive-triggers-skew]
- [ ] AC-16: WHEN project's `CommandDialog` Props is a strict superset of v0's (`title?`, `description?`, `theme?`) THEN no `ui-primitive-skew` violation is emitted [REQ: ui-primitive-skew-detection-phase, scenario: project-props-superset-of-v0-does-not-trigger-skew]
- [ ] AC-17: WHEN v0 and project `Button` Props field sets are identical with the same optionality THEN no violation regardless of cosmetic file differences (whitespace/import-order/comments) [REQ: ui-primitive-skew-detection-phase, scenario: identical-signatures-do-not-trigger-skew]
- [ ] AC-18: WHEN `src/components/ui/payment-card.tsx` exists with no v0 counterpart THEN the skew phase ignores it (no violation) [REQ: ui-primitive-skew-detection-phase, scenario: project-only-primitive-does-not-trigger-skew]
- [ ] AC-19: WHEN the skew phase emits a violation THEN gate result is FAIL AND `retry_context` references `set-design-import` AND does NOT instruct hand-editing primitive types [REQ: ui-primitive-skew-is-blocking-by-default, scenario: blocking-violation-triggers-retry-with-import-based-remediation]
- [ ] AC-20: WHEN `orchestration.yaml` has `design_import.sync_ui: false` AND v0/project Props differ THEN finding is logged WARN AND gate result is PASS-with-warning AND merge proceeds AND missing field names appear in output [REQ: ui-primitive-skew-downgrades-to-warning-when-sync_ui-is-disabled, scenario: sync_ui-false-downgrades-skew-to-warning]
- [ ] AC-21: WHEN both `ui-primitive-skew` and `missing-shared-file`/`shell-not-mounted` exist THEN aggregated `retry_context` lists skew findings before shell findings [REQ: phase-ordering---skew-before-shell-not-mounted, scenario: skew-reported-as-primary-cause-when-both-skew-and-missing-shell-exist]
