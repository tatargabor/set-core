## Context

The planner decomposition prompt in `lib/orchestration/planner.sh` controls how specifications are broken into implementable changes. Currently it has weak sizing guidance ("1-3 Ralph loop sessions", L complexity allowed with no cap). Real-world runs show 20+ requirement changes taking 2-3x longer with higher retry rates.

The prompt appears in two places:
- **Digest-mode** (line ~834): used when orchestrating from a digest pipeline
- **Brief-mode** (line ~967): used when orchestrating from a spec/brief directly

Both share identical rules text — changes must be applied to both locations.

## Goals / Non-Goals

**Goals:**
- Enforce max 6 requirements per change via prompt rules
- Cap complexity at M (15 tasks) — eliminate L category
- Add scope text length as a sizing signal (>2000 chars = too big)
- Provide split heuristics for common UI/feature patterns
- Add sub-domain chaining rule: split changes within a domain form a depends_on chain
- Keep rules concise — the prompt is already long

**Non-Goals:**
- Programmatic enforcement (e.g., rejecting plans with >10 REQs) — this is prompt-level guidance only
- Changing the plan JSON schema
- Modifying plan validation logic
- Changing the digest requirement extraction

## Decisions

**1. Max 6 REQs per change** — Based on CraftBrew data: changes with 5-7 REQs completed in 12-19 min, while 22 REQs took 41 min with verify-fail. The sweet spot is 5-6 REQs — small enough to keep context focused, large enough to avoid excessive overhead.

**2. Eliminate L complexity** — L (25+ tasks) was never a good target. M (8-15 tasks) is the new cap, S (<8) preferred. If decomposition produces >15 tasks, it should split further.

**3. Sub-domain dependency chaining** — When splitting `product-catalog` into `product-list` + `product-detail` + `product-search`, they must have explicit depends_on links. This is critical: without it, the parallel scheduler would run them simultaneously, causing merge conflicts on shared files. But these chains can run in parallel with unrelated domains (e.g., `user-auth`).

**4. Scope text as a proxy metric** — The scope field length correlates with change complexity. 800-1500 chars is healthy; >2000 chars signals the change should be split. This is a soft heuristic, not a hard rule.

**5. Pattern-based split heuristics** — Common patterns:
- List page + detail page → split if >8 REQs combined
- CRUD operations → separate from read-only views
- Search/filtering with own API routes → separate change
- Auth + profile + password management → separate changes

**6. Watchdog event throttle** — In `watchdog.sh` line ~122, the log message is already throttled (`consecutive_same == threshold || consecutive_same % 20 == 0`), but the `emit_event` on line ~125-126 fires unconditionally. Move the emit_event inside the same throttle condition. This is a one-line change with zero risk.

## Risks / Trade-offs

**More changes = more merge overhead** — Splitting 7 changes into 12 means more merge operations. Mitigated by depends_on chains (sequential within domain = no conflicts within chain).

**More changes = more verify cycles** — Each change goes through test/review/smoke gates. But smaller changes pass gates faster with fewer retries, so net effect should be positive.

**Prompt length increase** — Adding ~15 lines to an already long prompt. Acceptable — these are concrete rules, not verbose instructions.

**LLM may still produce large changes** — Prompt guidance is not enforcement. If this proves insufficient, we could add post-plan validation that warns/rejects L-sized changes. But start with prompt rules first.
