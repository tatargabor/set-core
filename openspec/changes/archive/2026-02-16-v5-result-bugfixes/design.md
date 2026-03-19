## Context

Benchmark v5 showed memory noise regressed from 15% (v4) to 37% (v5). Root causes:

1. **proactive_context auto-ingest**: The shodh-memory `proactive_context()` method has `auto_ingest=True` by default, which saves the context string as a `Conversation` type memory. Our recall hook passes working-state strings like "Working on change: stock-rethink" which become permanent memories with no recall value (21 entries, 25% of total).

2. **Missing change: tags**: Transcript extraction in `wt-hook-memory-save` builds tags from LLM output (`phase:auto-extract,source:hook,$tags`) but doesn't inject `change:$change_name`. The LLM sometimes includes the change name in its tags, sometimes not — resulting in 31/83 (37%) untagged memories.

3. **No convention extraction**: Agent saves error/gotcha memories well but never saves convention knowledge ("use formatPrice for all prices", "filter deletedAt IS NULL"). The save hook doesn't extract conventions from change definitions.

4. **Code map gaps**: Only 4/12 changes have code maps. The safety net in `wt-hook-memory-save` depends on commit-change-name parsing which misses changes where the commit message format doesn't match.

5. **TRAP-F repeated failure**: Three consecutive benchmarks where coupon `currentUses` is wrong. The change definition doesn't explicitly test for this.

## Goals / Non-Goals

**Goals:**
- Eliminate proactive-context noise (21 entries → 0)
- Ensure 100% of hook-saved memories have a `change:` tag
- Extract and save convention patterns from change definitions
- Improve code-map safety net reliability
- Fix TRAP-F change definition for v6

**Non-Goals:**
- Changing the shodh-memory library itself
- Modifying agent-inline memory saves (skill instructions)
- Changing the recall hook's retrieval logic
- Modifying benchmark test runner (`wt-loop`)

## Decisions

### D1: Disable auto-ingest globally

**Choice**: Pass `auto_ingest=False` in `set-memory proactive` command.

**Alternatives considered:**
- Tag the auto-ingested entries and filter them at recall → adds complexity, noise still in store
- Post-cleanup with `set-memory cleanup` → reactive not preventive, adds latency
- Make auto-ingest configurable with `--no-ingest` flag → over-engineering, we always want it off

**Rationale**: Simplest fix. The auto-ingest feature is designed for chatbot-style apps where conversation context is valuable. In our hook-driven pipeline, we control what gets saved explicitly — auto-ingest just creates noise.

### D2: Inject change: tag at the bash level in save hook

**Choice**: In `wt-hook-memory-save` transcript extraction, prepend `change:$change_name` to the tags string before passing to `set-memory remember`.

**Rationale**: The LLM sometimes includes the change name in its extracted tags, sometimes not. Adding it at the bash level guarantees it. Duplicate tags (if LLM also includes it) are harmless.

### D3: Convention extraction via LLM prompt enhancement

**Choice**: Enhance the existing transcript extraction LLM prompt to also scan for conventions established in the session. Add a second extraction category: "conventions/patterns this change establishes that future changes should follow."

**Alternatives considered:**
- Separate convention extraction pass → doubles LLM cost
- Regex-based convention detection → too brittle, can't handle natural language patterns
- Post-change hook → would need access to change definition files, complex to add

**Rationale**: The existing LLM call already processes the session context. Adding a prompt section for conventions is zero extra cost and leverages the model's comprehension.

### D4: Code-map safety net uses all commits in range

**Choice**: Instead of only checking the single latest commit per change, scan all commits since last marker. Also check active openspec changes directory for change names (not just commit message parsing).

**Rationale**: Current approach parses `change-name:` from commit message prefix, but many commits don't follow this format. Checking the active changes directory is more reliable.

## Risks / Trade-offs

- [Risk] Disabling auto-ingest removes a potential future feature → Mitigation: can re-enable with flag if needed; current value is negative
- [Risk] Convention extraction may produce low-quality conventions → Mitigation: LLM prompt includes "established in this session" filter; max 2 convention saves per session
- [Risk] Code-map scanning all commits may be slow → Mitigation: still bounded by marker file; only processes new commits since last run
