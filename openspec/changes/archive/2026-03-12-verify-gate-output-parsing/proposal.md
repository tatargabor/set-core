## Why

The verify gate runs `/opsx:verify` on every change before merge (Step 6), but only checks the Claude CLI exit code — not the actual verify output content. A verify report with "3 CRITICAL issues found" returns exit code 0 (Claude ran successfully), so the gate passes. This allowed 8 artifact-only changes to merge in CraftBrew E2E Run #3 despite the verify step correctly identifying them as incomplete.

Additionally, `review_before_merge` defaults to `false`, meaning the LLM code review (Step 5) never runs unless explicitly opted in. Combined with the scope check bug (fixed in b1a0e327c), this left no working defense against incomplete implementations.

## What Changes

- Parse `/opsx:verify` output for CRITICAL issues — treat CRITICAL findings as gate failure, triggering retry with specific findings as context
- Add structured output format to `/opsx:verify` so the gate can reliably detect pass/fail (not just grep for "CRITICAL")
- Change `review_before_merge` default from `false` to `true` — defense in depth **BREAKING**
- Log `scope_check` and `has_tests` results in the VERIFY_GATE event for post-mortem visibility
- Add `spec_coverage_result` field to change state tracking

## Capabilities

### New Capabilities
_None_

### Modified Capabilities
- `verify-gate`: Add verify output parsing, change review default, improve event logging

## Impact

- `lib/orchestration/verifier.sh` — verify output parsing logic, review default, event fields
- `bin/set-orchestrate` — DEFAULT_REVIEW_BEFORE_MERGE constant
- `.claude/skills/openspec-verify-change/SKILL.md` — structured output format addition
- `openspec/specs/verify-gate/spec.md` — updated requirements
- Existing orchestration configs with `review_before_merge` unset will now get reviews (breaking change — may increase token usage)
