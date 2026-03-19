## ADDED Requirements

### Requirement: Change-boundary recall
Modify `bin/wt-hook-memory-recall` to fire only when the agent starts working on a NEW change, not on every prompt.

Detection logic:
1. Read current `detect_next_change_action` result (e.g., `apply:discounts`)
2. Compare with last-recalled change stored in `.claude/last-recall-change`
3. If same → skip recall (return empty, no token cost)
4. If different → recall memories for the new change name, update marker file

Query strategy:
- Use the change name as primary query: `set-memory recall "<change-name> implementation" --limit 5`
- If revision change (07-09): also recall the original change being revised (e.g., C07 recalls C02 memories)

#### Scenario: First prompt of new change
- **WHEN** agent starts iteration for `apply:discounts` and last-recall was `ff:discounts`
- **THEN** recall fires with query "discounts implementation", outputs memories

#### Scenario: Subsequent prompts in same change
- **WHEN** agent is still in `apply:discounts` (same as last recall)
- **THEN** recall hook returns immediately with no output, saving tokens

#### Scenario: Revision change recalls original
- **WHEN** agent starts `ff:stock-rethink` (Change 07)
- **THEN** recall query includes both "stock-rethink" AND "shopping-cart" (the original C02)

---

### Requirement: Reduced token overhead
The recall hook must add ZERO tokens to prompts when skipping (same change as before). When firing, output must be concise — max 5 memories, max 100 chars each, bulleted format.

#### Scenario: Token overhead measurement
- **WHEN** benchmark runs 18 iterations with targeted recall
- **THEN** recall fires ~9 times (once per change transition) instead of 18+ times
