# Proposal: gate-reliability-fixes

## Why

Craftbrew Run 8 revealed 3 gate reliability issues that caused 3/6 changes to fail unnecessarily:

1. **Lint gate false positives on comments** — The `dangerouslySetInnerHTML` pattern matches in code comments and commit descriptions, not just actual JSX usage. Agent fixes the code but mentions the pattern name in fix comments → lint re-fails on the fix itself.

2. **Review gate whack-a-mole** — Each review round finds new CRITICAL issues in different files. Agent fixes them, next round finds more. 5 retries × full code review = massive token waste, always fails. The review gate needs a "verify fixes only" mode after round 1.

3. **Review extra_retries too high** — `review_extra_retries: 3` means review gets `max_retries + 3 = 5` total attempts. Combined with whack-a-mole, this burns 200K+ tokens before failing. Should be 1 extra retry (3 total).

## What Changes

### Lint: comment-aware matching
The `_extract_added_lines()` diff parser gains a `skip_comments` option. Lines starting with `//`, `*`, `#`, or inside `/* */` blocks are excluded from pattern matching. The forbidden pattern dict gains an optional `skip_comments: true` field (default true for all patterns).

### Review: fix-verification mode
After round 1, subsequent review rounds receive the previous findings and are instructed to ONLY verify those specific fixes — not scan for new issues. This breaks the whack-a-mole cycle.

### Review: reduce extra_retries default
`review_extra_retries` default changes from 3 to 1. Total review attempts: `max_retries(2) + 1 = 3` instead of 5.

## Capabilities

### Modified Capabilities
- `lint-gate`: Comment-aware pattern matching (skip comment lines)
- `review-gate`: Fix-verification mode for retry rounds
- `gate-profiles`: Lower default review_extra_retries

## Impact

- **Files**: `modules/web/set_project_web/gates.py`, `lib/set_orch/verifier.py`, `lib/set_orch/gate_profiles.py`
- **Risk**: Low — targeted fixes, no structural changes
- **Size**: S
