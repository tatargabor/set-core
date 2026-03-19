## Why

The orchestration system has evolved through 7 completed changes (orchestrator-layer, verify-gate, memory-integration, quality-gates, tui, stabilization, spec-driven-orchestration, merge-conflict-hardening) but the capability specs have drifted significantly from the actual implementation. Key issues:
- Specs reference outdated values (30s poll → code uses 15s, brief-context.md → code uses proposal.md)
- Major features are completely undocumented (agent-assisted merge rebase, post-merge build verification, conflict fingerprint dedup)
- Contradictions exist between specs and code (stall_count reset location, verify gate step order)
- `init_state()` still creates `verify_retried: boolean` while all code uses `verify_retry_count: integer`
- `auto_detect_test_command()` is dead code — defined but never called
- None of the orchestration change specs have been synced to main specs

## What Changes

- Update 6 existing capability specs with corrections matching current implementation
- Document 3 undocumented features as new capability specs
- Fix `init_state()` to use `verify_retry_count: 0` instead of `verify_retried: false`
- Remove dead `auto_detect_test_command()` function or wire it into the flow
- Sync all orchestration delta specs to main `openspec/specs/`

## Capabilities

### New Capabilities
- `agent-merge-resolution`: Agent-assisted merge conflict resolution — on first merge conflict, orchestrator launches agent in worktree to merge main, resolve conflicts, then retries merge
- `post-merge-verification`: Post-merge build verification and dependency install — after successful merge, verify main still builds and run package manager install if package.json changed
- `merge-conflict-fingerprint`: Conflict fingerprint deduplication — md5 hash of conflicted files to detect repeating identical conflicts and stop retrying early

### Modified Capabilities
- `orchestration-engine`: Update poll interval (30s→15s), dispatch creates proposal.md (not brief-context.md), init_state uses verify_retry_count integer, document stalled change cooldown resume, document retry_failed_builds in monitor loop
- `verify-gate`: Correct gate step order to match implementation (test→build→test-file-check→review→verify), remove auto_detect_test_command reference or document its activation
- `ralph-loop`: Update stall_count reset behavior — reset happens in poll_change() on fresh mtime, NOT in resume_change()

## Impact

- `bin/set-orchestrate`: minor code fix in `init_state()` (boolean→integer), potential dead code removal
- `openspec/specs/`: 6+ new or updated main spec files
- `openspec/changes/*/specs/`: delta specs corrected in archived changes (informational only)
