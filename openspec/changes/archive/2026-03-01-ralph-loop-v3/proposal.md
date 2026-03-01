## Why

Two remaining pain points from v6/v6_2 orchestration runs: (1) when `opsx:ff` fails to create `tasks.md`, the Ralph loop stalls with `ff_exhausted` but has no recovery — the agent wasted tokens and the change is stuck; (2) the Ralph loop terminal shows no real-time output during Claude execution, making it impossible to see what the agent is doing or where it's stuck.

## What Changes

- **FF exhausted fallback**: When `ff_attempts` reaches the retry limit and no `tasks.md` exists, the loop generates a minimal `tasks.md` from existing artifacts (proposal.md scope, design.md if present) instead of stalling. This turns `ff_exhausted` from a terminal state into a recovery path.
- **Real-time terminal output**: Replace the buffered pipe (`claude ... | tee log`) with `--output-format stream-json` parsing that shows tool use events, file reads/writes, and progress in real-time during each iteration.

## Capabilities

### New Capabilities
- `ff-exhausted-recovery`: Automatic tasks.md generation when ff retry limit is exceeded
- `ralph-realtime-output`: Stream-json based real-time terminal output during Ralph loop iterations

### Modified Capabilities
- `ralph-loop`: New ff_exhausted recovery path and stream-json output mode in the iteration runner

## Impact

- `bin/wt-loop`: iteration runner (`cmd_run`), ff_exhausted handler, Claude invocation pipe
- No API or dependency changes — uses existing Claude CLI `--output-format stream-json`
