## MODIFIED Requirements

### Requirement: Ralph loop state file format
The Ralph loop SHALL write state to `<worktree>/.claude/loop-state.json` with a documented, stable format for MCP consumption.

#### Scenario: Iteration history entry
- **WHEN** Ralph completes an iteration
- **THEN** adds entry to `iterations` array with:
  - `n`: number - iteration number
  - `started`: string - ISO timestamp
  - `ended`: string - ISO timestamp
  - `done_check`: boolean - whether done criteria met
  - `commits`: array - commit hashes made
  - `tokens_used`: number - tokens consumed this iteration
  - `timed_out`: boolean - whether iteration was killed by timeout (optional, only if true)
  - `no_op`: boolean - whether iteration produced no meaningful work (optional, only if true)
  - `ff_exhausted`: boolean - whether ff retry limit was exceeded (optional, only if true)
  - `ff_recovered`: boolean - whether fallback tasks.md was generated (optional, only if true)
  - `log_file`: string - path to per-iteration log file
  - `resumed`: boolean - whether this iteration used `--resume` (optional, only if true)
