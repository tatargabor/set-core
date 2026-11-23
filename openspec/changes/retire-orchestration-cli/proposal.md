## Why

The orchestration CLI surface (`set-orchestrate`, `set-merge`, `set-new`, `set-work`,
`set-close`, `set-list`, `set-add`, `set-loop`, `set-sentinel-*`, `set-supervisor`,
`set-recovery`, `set-run-logs`, `set-e2e-report`, `set-compare`, `set-harvest`, ~30 bins) had no
real use in 30 days, and stage 2 already stopped deploying the slash commands that drove it.
Stage 4 of `fleet-era-consolidation`.

## What Changes

- Remove those bins and their installer entries. **BREAKING** for a script that calls one.
- Archive the capability specs that describe only them.

## Precondition

- `set-project init`, `set-leakscan`, `set-kb`, `set-doctor` and the fleet call none of them
  (grep + one real init + one doctor run).

## Impact

`bin/`, `install.sh`'s command list, docs referring to them, the doctor's install check list.
