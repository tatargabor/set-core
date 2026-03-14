## Purpose

Migrate `lib/orchestration/digest.sh` (1,311 LOC) to `lib/wt_orch/digest.py`. The digest engine scans multi-file spec directories, classifies content, extracts structured requirements, validates output, and tracks coverage. This is the largest unmigrated orchestration module.

## Requirements

### DIGEST-01: Spec Directory Scanning
- `scan_spec_directory(spec_path)` accepts a directory or single file path
- For directories: recursively find all `.md`, `.yaml`, `.yml`, `.txt` files
- Return list of `SpecFile(path, size_bytes, content)` dataclasses
- Skip files matching ignore patterns: `archive/`, `node_modules/`, `.git/`

### DIGEST-02: Digest Prompt Construction
- `build_digest_prompt(spec_files, project_context)` assembles the LLM prompt
- Include all spec file contents with path headers
- Include project context (from orchestration.yaml directives)
- Output: string prompt ready for Claude API call

### DIGEST-03: Digest API Call
- `call_digest_api(prompt, model)` calls Claude CLI in print mode
- Parse JSON response: `{requirements: [], domains: [], ambiguities: []}`
- Handle API errors with retry (max 3 attempts)
- Return parsed `DigestResult` dataclass

### DIGEST-04: Digest Output Writing
- `write_digest_output(digest_result, output_dir)` writes to `wt/orchestration/digest/`
- Files: `index.yaml`, `requirements.yaml`, `dependencies.yaml`, `coverage.yaml`
- Domain summaries: `domains/<domain-name>.md`
- All YAML must be valid and parseable

### DIGEST-05: Requirement ID Stabilization
- `stabilize_ids(new_digest, existing_digest)` preserves IDs across re-digests
- Match requirements by content similarity (>80% match keeps same ID)
- New requirements get fresh IDs (REQ-NNN format)
- Removed requirements tracked in `coverage.yaml` as deprecated

### DIGEST-06: Digest Validation
- `validate_digest(digest_dir)` checks structural integrity
- Verify all required files exist
- Verify requirement IDs are unique
- Verify dependency references point to existing IDs
- Return list of validation errors (empty = valid)

### DIGEST-07: Coverage Tracking
- `populate_coverage(state, digest)` maps requirements to plan changes
- `check_coverage_gaps(coverage)` identifies uncovered requirements
- `update_coverage_status(coverage, change_name, status)` updates per-change status
- Coverage stored in `coverage.yaml`

### DIGEST-08: Triage Generation
- `generate_triage_md(ambiguities)` creates human-readable triage document
- `parse_triage_md(triage_path)` reads back resolved triage decisions
- `merge_triage_to_ambiguities(triage, digest)` applies resolutions
- `merge_planner_resolutions(planner_output, digest)` applies auto-resolutions

### DIGEST-09: Freshness Check
- `check_digest_freshness(spec_path, digest_dir)` compares modification times
- Return stale if any spec file is newer than digest output
- Used by planner to auto-trigger re-digest

### DIGEST-10: CLI Subcommands
- `wt-orch-core digest run --spec <path> [--dry-run]` — full digest pipeline
- `wt-orch-core digest validate [--dir <path>]` — validate existing digest
- `wt-orch-core digest coverage [--dir <path>]` — show coverage report
- `wt-orch-core digest freshness --spec <path> [--dir <path>]` — check staleness
- All subcommands registered in `cli.py` under `digest` group

### DIGEST-11: Unit Tests
- Test spec scanning with mock directory structures
- Test ID stabilization with overlapping/changed requirements
- Test validation with valid and invalid digest structures
- Test coverage tracking state transitions
- Test freshness detection with mock file timestamps
