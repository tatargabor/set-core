# Proposal: Fix engine.sh arithmetic crash (ISS-001)

## Why

`engine.sh` crashes after the first ralph loop iteration due to three interrelated bash bugs in the context-tracking section. Under `set -euo pipefail`, the `grep | wc -c` pipeline produces multi-line output when grep finds no matches — the `|| true` inside `{ ... }` fires as a separate command whose output gets appended, resulting in `"0\n0"` which fails bash arithmetic. Additionally, the `cleanup_done` variable is scoped with `local` in the parent function but referenced inside the trap handler where it may be unbound under `set -u`. This crashes the orchestration loop in every project using set-core.

## What Changes

- **Fix arithmetic errors on lines 592/596**: Wrap `grep`/`sed` commands in `{ ... || true; }` so `pipefail` doesn't produce multi-line output from the `|| true` fallback. Add `${var:-0}` default guards on the captured values.
- **Fix unbound variable on line 88**: Use `${cleanup_done:-false}` guard in the trap handler so `set -u` doesn't kill the process when the trap fires before variable initialization.
- No breaking changes — pure bug fixes to bash variable handling.

## Capabilities

### New Capabilities
- `enginesh-bash-safety`: Fixes to engine.sh arithmetic and variable scoping to survive `set -euo pipefail` without crashing the ralph loop.

### Modified Capabilities
<!-- None — framework-internal fix, no spec-level behavior changes -->

## Impact

- **File:** `lib/loop/engine.sh` (lines 88, 591-599)
- **Scope:** set-core framework — affects all projects using the ralph loop
- **Risk:** Low — isolated to specific lines, no behavioral change to orchestration logic
- **If not fixed:** Ralph loop crashes after iteration 1 in every project, blocking all orchestrated work
