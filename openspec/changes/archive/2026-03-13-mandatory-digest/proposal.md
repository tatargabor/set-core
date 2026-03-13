## Why

The digest phase extracts structured requirements, ambiguities, and cross-references from spec documents — enabling coverage tracking and better decomposition. Currently it only runs when `--spec` points to a directory. Single-file specs (like minishop's `v1-minishop.md`) bypass digest entirely, resulting in no `requirements.json`, no coverage tracking, and no ambiguity detection. This means most projects lose the value of the digest system.

## What Changes

- `find_input()` in `utils.sh` sets `INPUT_MODE="digest"` for **all** `--spec` inputs (file or directory), not just directories
- Remove the separate `INPUT_MODE="spec"` code path — it becomes unnecessary
- The `planner.sh` `cmd_plan()` auto-digest trigger already handles both cases (fresh/stale check, auto-generate), so no changes needed there
- `scan_spec_directory()` in `digest.sh` already handles single files (lines 166-168), so no changes needed there
- Brief mode (`INPUT_MODE="brief"`) remains unchanged — briefs are short TODO lists, not spec documents

## Capabilities

### New Capabilities

_(none — this enables an existing capability for all inputs)_

### Modified Capabilities

- `orchestration-planning`: The planning pipeline now always runs digest for `--spec` inputs, producing `wt/orchestration/digest/` with requirements.json, domains/, ambiguities.json regardless of whether input is a file or directory

## Impact

- **`lib/orchestration/utils.sh`**: `find_input()` — remove spec-mode branches, unify to digest mode
- **`lib/orchestration/planner.sh`**: Remove dead `INPUT_MODE="spec"` code paths in `cmd_plan()` and `cmd_decompose()`
- **Token cost**: Single-file specs will now cost one extra API call for digest generation (~30s). This is acceptable given the value of structured requirements.
- **Backwards compatible**: No config changes needed. Projects using `--spec <file>` will automatically get digest.
