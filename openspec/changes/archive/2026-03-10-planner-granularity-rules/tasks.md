## 1. Update digest-mode decomposition rules

- [x] 1.1 In `lib/orchestration/planner.sh` digest-mode prompt (around line 834-839), replace the current sizing rules with granularity rules: max 6 REQs per change, complexity cap at M (8-15 tasks max, S preferred), L is not allowed — split further
- [x] 1.2 Add scope text length heuristic: 800-1500 chars healthy, >2000 chars means split
- [x] 1.3 Add sub-domain chaining rule: when splitting a domain into multiple changes, they must form a depends_on chain (sequential within domain, parallel across domains)
- [x] 1.4 Add split heuristics for common patterns: list+detail split, CRUD separation, search as separate change, auth vs profile separation

## 2. Update brief-mode decomposition rules

- [x] 2.1 In `lib/orchestration/planner.sh` brief-mode prompt (around line 967-972), apply the same granularity rules as digest-mode (max 6 REQs, M complexity cap, no L)
- [x] 2.2 Add the same scope text length heuristic, sub-domain chaining rule, and split heuristics

## 3. Throttle watchdog event spam

- [x] 3.1 In `lib/orchestration/watchdog.sh` (around line 122-126), move the `emit_event "WATCHDOG_WARN"` call inside the existing log throttle condition so it only fires at threshold + every 20th occurrence, not every poll cycle

## 4. Verify consistency

- [x] 4.1 Verify both prompt locations have identical granularity rule text
- [x] 4.2 Verify the existing rules (dependency ordering, shared resource awareness, test-per-change) are preserved and not conflicting with new granularity rules
