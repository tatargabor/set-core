# loop-token-budget Specification

## Purpose
Track and enforce per-change token budgets based on change size — checkpoint on exceed.

## Requirements

### Requirement: Per-change token budget enforcement
The Ralph loop SHALL enforce a maximum token budget per change, stopping gracefully when the budget is exceeded.

#### Scenario: Token budget flag accepted
- **WHEN** `wt-loop start` is called with `--token-budget N` (where N is a number in thousands)
- **THEN** the budget SHALL be stored in `loop-state.json` as `token_budget` (in raw token count, i.e., N * 1000)
- **AND** the banner SHALL display the budget: "Budget: {N}K tokens"

#### Scenario: Budget exceeded between iterations
- **WHEN** an iteration completes
- **AND** `total_tokens` in `loop-state.json` exceeds `token_budget`
- **THEN** the loop SHALL stop with status `"budget_exceeded"`
- **AND** a message SHALL be displayed: "Token budget exceeded: {total}K / {budget}K"

#### Scenario: Budget not set (default)
- **WHEN** `wt-loop start` is called without `--token-budget`
- **THEN** `token_budget` SHALL be `0` in loop-state.json
- **AND** no budget enforcement SHALL occur (unlimited)

#### Scenario: Budget exceeded status in loop-state
- **WHEN** the loop stops due to budget exceeded
- **THEN** `loop-state.json` SHALL have `"status": "budget_exceeded"`
- **AND** the orchestrator MAY extend the budget and resume the loop

#### Scenario: Orchestrator sets budget based on change size
- **WHEN** the orchestrator dispatches a change with size annotation
- **THEN** it SHALL pass `--token-budget` to `wt-loop start` based on the size:
  - `S` → `--token-budget 100`
  - `M` → `--token-budget 300`
  - `L` → `--token-budget 500`
  - `XL` → `--token-budget 1000`
