## Why

A hook analysis of one week of agent sessions in a downstream project family (2026-11-13) found
three false refusals by the agent-side leak gate. All three were measured and reproduced:

- **Two refused correct commits.** The command was `cd openspec/changes/<x> && … && cd ../../.. &&
  git commit`. The gate took only the last `cd` and resolved `../../..` against the session's
  directory, three levels above the repository. The scanner reported "not inside a git
  repository", and the gate turned that into "this commit would carry content that must not enter
  the repository's history".
- **One was a crash reported as a finding.** A staged CSV in a legacy single-byte encoding made
  the strict UTF-8 decode of `git diff` raise in `set-leakscan`. The traceback reached the agent
  as a leak.

The analysis proposed failing open on both "no repository" and "traceback". Only the first is
safe, and only when the resolution is certain: git refuses a commit outside a repository itself.
A crash that passes would let an unscanned commit through, so it stays refused, but it is now
named as a crash.

## What Changes

- The hook follows every `cd`/`pushd` before the verb in order, then the verb's `-C <path>`,
  expanding `~` and variables assigned in the command or the environment.
- A certain resolution outside any repository is not refused; it is announced on stderr.
- An uncertain resolution never fails open.
- A scanner traceback is refused with a message that names the crash.
- `set-leakscan` decodes git output with replacement, so a non-UTF-8 diff is scanned (the ASCII
  around an undecodable byte still is) instead of crashing.

## Capabilities

### Modified Capabilities

- `env-leak-gate`: how the agent-side gate picks the repository it scans, and what it does when
  it cannot.

## Impact

`bin/set-hook-leakscan`, `bin/set-leakscan`, `tests/unit/test_leakscan.py`. The hook is linked
onto PATH from the checkout, so the fix is live everywhere the moment it is committed.
