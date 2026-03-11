## Context

The verify gate runs quality checks on completed changes before merge. Current order is test→build→e2e, but build failures (type errors) are the most common first-attempt failure — catching them earlier saves a full retry cycle. Translation JSON files cause the most merge conflicts, but unlike package.json, have no programmatic resolver. Watchdog "PID alive" messages fill logs with non-actionable warnings.

## Goals / Non-Goals

**Goals:**
- Reduce first-attempt verify gate failures by catching build errors before running tests
- Eliminate translation JSON merge conflicts through programmatic resolution
- Reduce log noise from watchdog without losing diagnostic value

**Non-Goals:**
- Changing E2E timeout values (separate concern)
- Changing watchdog escalation logic (only log level changes)
- Supporting non-JSON translation formats (YAML, PO files)

## Decisions

### D1: Build-first gate order

Reorder the verify gate steps: **build → test → e2e → review → verify**.

Rationale: Build is the cheapest check (~10s, no LLM cost) and catches the most common failure mode (TypeScript type errors from incorrect imports, wrong parameter types). Running it first means failures are caught in ~10s instead of after test execution (~5-6s) + build (~10s) + retry dispatch (~60s). The fail-fast semantics remain the same — any step failure stops the pipeline and triggers retry.

The spec currently says test→build→e2e. The spec will be updated to reflect build→test→e2e.

### D2: JSON translation file auto-resolve via jq deep-merge

Add `auto_resolve_json_files()` to `wt-merge`, modeled on the existing `auto_resolve_package_json()`. Strategy:

1. After `git merge` fails with conflicts, check if conflicted files include `.json` files
2. For each conflicted `.json` file: extract ours (`:2:`) and theirs (`:3:`) versions via `git show`
3. Validate both are valid JSON via `jq empty`
4. Deep-merge using the same `jq -s` strategy as package.json: recursively merge objects, prefer theirs (feature branch) on scalar conflicts
5. Write merged result, `git add` the file
6. If all conflicts resolved, `git commit`

This runs in the merge flow AFTER `auto_resolve_generated_files` and `auto_resolve_package_json`, BEFORE `llm_resolve_conflicts`. This ordering ensures JSON files get the cheapest resolution first.

Scope: All `.json` files in conflict, not just translation files. The deep-merge strategy is correct for any additive JSON (translation keys, config objects). Non-JSON files skip this step.

### D3: Watchdog PID-alive log level change

Change `log_warn` to `log_debug` for the "hash loop but PID alive — skipping escalation" message in `watchdog.sh`. Keep `emit_event "WATCHDOG_WARN"` unchanged so the event is still recorded in the events JSONL for tooling/TUI. Only the console/log output changes.

This is safe because:
- The system already decides correctly (skip escalation when PID alive)
- The message is purely informational ("I checked, everything is fine")
- The event emission preserves the audit trail
- True stuck detection (PID dead) remains at WARN level

## Risks / Trade-offs

- **Build-first order change**: If a project has expensive builds but cheap tests, build-first is slightly slower for test-only failures. In practice, builds are ~10s (Next.js) and tests are ~5s (Jest), so the difference is negligible. The win from catching type errors early far outweighs this.
- **JSON auto-resolve**: Could incorrectly merge JSON files where both sides modify the same key with different values (scalar conflict → theirs wins). This matches the existing package.json behavior and is the correct default for translation files (last-merged feature wins on conflicts).
- **log_debug may hide useful info**: Operators used to seeing WARN messages in logs won't see PID-alive events anymore. Mitigated by keeping the JSONL event emission — TUI and reports still show them.
