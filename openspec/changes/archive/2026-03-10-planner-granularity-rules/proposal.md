## Why

The orchestration planner produces changes that are too large — e.g., `product-catalog` with 22 requirements in a single change. This overloads agent context, increases verify-fail retry risk, and wastes tokens. The current prompt says "1-3 Ralph loop sessions" and allows L complexity (25+ tasks) with no upper bound. CraftBrew E2E and MiniShop runs both showed this: large changes take 2-3x longer and are more likely to need retries.

Additionally, when a large feature domain is split into multiple smaller changes, those sub-changes must run sequentially (depends_on chain) so each can build on the previous one's code — but they can still run in parallel with unrelated feature chains.

Separately, the watchdog emits `WATCHDOG_WARN` with reason `hash_loop_pid_alive` on every poll cycle when a loop's hash doesn't change but the PID is alive. This produces 200+ false-positive events per run, drowning out real signals in the event log. The log message is already throttled (every 20th), but the event emission is not.

## What Changes

- Add hard limits to planner decomposition rules: max 6 requirements per change, max M complexity (15 tasks), scope text cap at 2000 chars
- Add split heuristics for common patterns (list+detail, CRUD, search, auth+profile)
- Add sub-domain chaining rule: when a feature domain is split, resulting changes must form a depends_on chain (sequential within the domain, parallel across domains)
- L complexity becomes a warning/split trigger, not an accepted category
- Both prompt locations updated: digest-mode decomposition (line ~835) and brief-mode decomposition (line ~968)
- Throttle watchdog `hash_loop_pid_alive` event emission to match log throttle (every 20th occurrence), reducing event noise from 200+ to ~10 per run

## Capabilities

### New Capabilities
- `change-granularity`: Rules and heuristics for planner change sizing — max requirements, complexity caps, split patterns, sub-domain dependency chaining
- `watchdog-event-throttle`: Throttle false-positive watchdog events when PID is alive

### Modified Capabilities

## Impact

- `lib/orchestration/planner.sh` — both decomposition prompt blocks (digest-mode and brief-mode)
- `lib/orchestration/watchdog.sh` — event emission throttle at line ~126
- Affects all future orchestration runs — changes will be smaller and more numerous
- May increase total change count by 30-50% but reduce per-change token usage and retry rate
