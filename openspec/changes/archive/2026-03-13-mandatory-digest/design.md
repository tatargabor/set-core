## Context

The orchestration pipeline has three input modes: `digest` (directory spec), `spec` (single file), and `brief` (TODO list). The digest mode produces structured output (`requirements.json`, `domains/`, `ambiguities.json`) that enables coverage tracking, ambiguity detection, and better decompose prompts. The spec mode bypasses all of this — it just passes the raw file content to the decompose prompt.

The `scan_spec_directory()` function already handles single files. The `cmd_digest()` function already accepts both files and directories. The gap is purely in `find_input()` routing.

## Goals / Non-Goals

**Goals:**
- All `--spec` inputs (file or directory) produce a digest before planning
- Single-file projects get requirements tracking, coverage, ambiguity detection
- No behavioral change for directory inputs or brief mode

**Non-Goals:**
- Changing brief mode — briefs are short task lists, not spec documents
- Optimizing digest for small files — the extra API call (~30s) is acceptable
- Changing the digest output format

## Decisions

**1. Unify spec → digest in find_input()**

Change `find_input()` so `--spec <file>` sets `INPUT_MODE="digest"` instead of `"spec"`. This is the only routing change needed.

Rationale: The digest pipeline already handles single files end-to-end. No need for a separate code path.

**2. Remove INPUT_MODE="spec" entirely**

After the change, only two modes exist: `digest` and `brief`. Remove all `INPUT_MODE=="spec"` branches in `planner.sh`.

Rationale: Dead code paths are maintenance risk. The `spec` mode was the "pass raw text" fallback — with digest handling everything, it's unnecessary.

**3. Keep INPUT_PATH pointing to the file (not parent directory)**

For `--spec <file>`, `INPUT_PATH` stays as the file path (not its parent dir). The `scan_spec_directory()` already handles this correctly — it detects it's a file and scans just that one file.

Rationale: Changing to parent dir would break if multiple spec files exist in the same directory but only one was intended.

## Risks / Trade-offs

- **[Extra API call for simple specs]** → Single-file specs now incur a digest API call (~30s, ~5K tokens). Acceptable given the structured requirements output.
- **[Digest failure blocks planning]** → If digest API call fails, planning can't proceed. This is already handled: `cmd_digest` failures are logged and the orchestrator stops with a clear error.
- **[Spec mode removal]** → Any external code checking `INPUT_MODE=="spec"` will break. Grep confirms this is only in `planner.sh` — no external consumers.
