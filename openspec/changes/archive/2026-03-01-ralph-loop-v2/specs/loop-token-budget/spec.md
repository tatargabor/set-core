## MODIFIED Requirements

### Requirement: Per-change token budget enforcement
The Ralph loop SHALL enforce a maximum token budget per change, pausing for human decision when the budget is exceeded.

#### Scenario: Token budget flag accepted
- **WHEN** `wt-loop start` is called with `--token-budget N` (where N is a number in thousands)
- **THEN** the budget SHALL be stored in `loop-state.json` as `token_budget` (in raw token count, i.e., N * 1000)
- **AND** the banner SHALL display the budget: "Budget: {N}K tokens"

#### Scenario: Budget exceeded — human checkpoint
- **WHEN** an iteration completes
- **AND** `total_tokens` in `loop-state.json` exceeds `token_budget`
- **THEN** the loop SHALL update status to `"waiting:budget"`
- **AND** display a checkpoint banner: "Budget checkpoint: {total}K / {budget}K — waiting for human decision"
- **AND** send a desktop notification via `notify-send`
- **AND** enter a wait loop polling `loop-state.json` status every 30 seconds

#### Scenario: Human approves continuation
- **WHEN** the loop is in `waiting:budget` status
- **AND** the status is changed to `"running"` (via `wt-loop resume`)
- **THEN** the loop SHALL continue from the next iteration
- **AND** log: "Budget checkpoint approved, continuing"

#### Scenario: Human updates budget
- **WHEN** `wt-loop budget <N>` is called while status is `waiting:budget`
- **THEN** `token_budget` SHALL be updated to N * 1000
- **AND** status SHALL be changed to `"running"`
- **AND** the loop SHALL continue from the next iteration

#### Scenario: Human stops loop
- **WHEN** `wt-loop stop` is called while status is `waiting:budget`
- **THEN** status SHALL be changed to `"stopped"`
- **AND** the loop SHALL exit cleanly

#### Scenario: Budget not set (default)
- **WHEN** `wt-loop start` is called without `--token-budget`
- **THEN** `token_budget` SHALL be `0` in loop-state.json
- **AND** no budget enforcement SHALL occur (unlimited)

#### Scenario: Orchestrator recognizes waiting:budget
- **WHEN** the orchestrator polls a change with status `"waiting:budget"`
- **THEN** it SHALL NOT increment `stall_count`
- **AND** it SHALL NOT attempt to restart the loop
- **AND** it SHALL treat it the same as `"waiting:human"` (requires manual intervention)
