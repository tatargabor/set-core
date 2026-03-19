# Scoring Rubric

## Per-Change Metrics

Each change is scored on these dimensions after reviewing the session transcript.

### Dead Ends (0-5)

A dead end is when the agent pursues an approach, realizes it doesn't work, and backtracks.

| Score | Description |
|-------|-------------|
| 0 | No dead ends — clean implementation path |
| 1 | One minor dead end (caught and fixed within a few lines) |
| 2 | One significant dead end (wrong approach requiring file rewrites) |
| 3 | Multiple dead ends, but all resolved |
| 4 | Major dead end requiring architectural rethink |
| 5 | Stuck in dead end — change incomplete or deeply flawed |

**Examples:**
- Score 1: Agent uses wrong Prisma syntax, gets error, fixes immediately
- Score 3: Agent builds cart referencing product IDs, realizes it needs variant IDs, refactors cart API
- Score 5: Agent builds flat order model, can't implement per-vendor status in C6, runs out of iterations

### Repeated Mistakes (0-3)

A repeated mistake is when the agent makes the same error that occurred in a previous change (or earlier in the same change).

| Score | Description |
|-------|-------------|
| 0 | No repeated mistakes |
| 1 | One repeated mistake, quickly resolved |
| 2 | Multiple repeated mistakes or one that took significant time |
| 3 | Same critical mistake repeated, indicating no learning across changes |

**Examples:**
- Score 0: Agent remembers to run `prisma generate` after schema changes (no repeat of C1 error)
- Score 1: Agent forgets WAL mode again in C5 but fixes within one iteration
- Score 3: Agent hits SQLITE_BUSY in C2 AND C5, spending multiple iterations debugging each time

### Design Rework (0-3)

Design rework is when the agent needs to change code from a previous change to make the current change work.

| Score | Description |
|-------|-------------|
| 0 | No design rework needed — previous architecture supports current change |
| 1 | Minor adjustments to previous code (adding a field, tweaking an API response) |
| 2 | Significant rework (refactoring a model, rewriting API routes) |
| 3 | Fundamental architectural rework (redesigning core data model) |

**Examples:**
- Score 0: C6 works cleanly because C3 used nested orders
- Score 1: Adding vendorId to product listing API response for C3
- Score 3: Refactoring from flat orders to nested orders in C6 because C3's architecture was wrong

### Test Pass/Fail (per change)

Each change has an acceptance test (`tests/test-NN.sh`). Track:

| Metric | Description |
|--------|-------------|
| First-try pass | Did the test pass on the first run after implementation? (yes/no) |
| Iterations to pass | How many test-fix-retest cycles to achieve a full pass? |
| Checks passed | Number of individual checks passed (e.g., 4/5) |
| Checks failed | Number of individual checks failed |

**For revision/feedback changes (07-12), also track:**

| Metric | Description |
|--------|-------------|
| Repeat-failure | Did the agent reintroduce a pattern the change explicitly rejected? |
| Counter-pattern | Did the agent enhance the old pattern instead of replacing it? |

### Session Length

- **Iterations**: Number of set-loop iterations spent on this change
- **Tokens**: Total tokens consumed (from `set-loop history`)
- **Time**: Wall-clock time in minutes

## Revision Change Scoring (C07-C09)

Changes 07-09 revise earlier decisions. Additional scoring:

| Metric | C07 | C08 | C09 |
|--------|-----|-----|-----|
| Found all mutation points | Stock add/remove/clear | Image references across codebase | All money fields |
| Correctly moved/migrated | Stock to checkout | JSON to Image table | Decimal/Float to Int |
| Old code fully removed | Cart stock decrement | Product.images column | Float arithmetic |
| Test pass | test-07.sh | test-08.sh | test-09.sh |

**Key question**: How many iterations did the agent need to find all the affected code? Memory agent should know locations; baseline must search.

## Feedback Change Scoring (C10-C11)

Changes 10-11 correct design decisions. Additional scoring:

| Metric | C10 (Cart UX) | C11 (Dashboard) |
|--------|---------------|-----------------|
| Followed correction exactly | No update button, toast, inline edit, CTA | No tabs, flat list, badges, pagination |
| Avoided repeat-failure trap | No confirm(), no Update button reintroduced | Tabs fully removed (not enhanced) |
| Test iterations to pass | test-10.sh iteration count | test-11.sh iteration count |

**Critical**: These changes are designed so that without memory of "the stakeholder explicitly rejected X," the agent defaults to common patterns (adding Update button, keeping tabs). Track whether the agent fell into the trap.

## Sprint Retro Scoring (C12)

Change 12 has 12 cross-cutting bugs. Score each individually:

| Bug | What to check | Memory value | Trap type |
|-----|--------------|--------------|-----------|
| 1. API format | All list endpoints use `{data, total, page, limit}` | Knows all endpoints | Convention |
| 2. Payout rounding | Largest-remainder method, sum == payment | Knows payout code location | Algorithm |
| 3. Expired reservation | Returns 400 with RESERVATION_EXPIRED code | Knows checkout validation | Location |
| 4. Missing index | `@@index([vendorId])` on SubOrder | Knows schema location | Location |
| 5. Seed data | All money values in cents | Knows seed script | Location |
| 6. formatPrice | All price displays use formatPrice() | Knows utility location (TRAP-H) | Convention |
| 7. Error codes | All errors use constants from errors.ts | Knows convention (TRAP-J) | Convention |
| 8. Soft delete | All product queries filter deletedAt | Knows pattern (TRAP-K) | Convention |
| 9. Pagination API | All list endpoints use consistent format | Knows convention (TRAP-I) | Convention |
| 10. Responsive layout | All pages use ResponsiveContainer, sm:480px | Knows convention (TRAP-L) | Convention |
| 11. Pagination UI | Shared `<Pagination>` component, no ad-hoc UI | Knows each page's UI (TRAP-M) | **Drift** |
| 12. Toast/notifications | Shared `<Toast>`, no alert()/confirm() | Knows each page's pattern (TRAP-N) | **Drift** |

**Expected iteration difference**: Memory agent should fix all 12 in ~2-3 iterations (knows all locations, conventions, AND implementation details). Baseline may need 4-6 iterations. Bugs 11-12 (drift traps) are expected to show the LARGEST iteration delta — the memory agent knows HOW each page implemented its own version.

## Active Trap Scoring (V3)

V3 embeds active traps in C01-C06 that create measurable memory advantages:

### TRAP-A: JSON images (C01 → C08 → C12)
| Metric | Description |
|--------|-------------|
| C01 implementation | Did agent use JSON string as instructed? |
| C08 migration difficulty | Did agent know the exact JSON format to migrate from? |
| Iterations saved (memory) | Compare C08 iteration count between runs |

### TRAP-B: $queryRaw pain (C02 → C05)
| Metric | Description |
|--------|-------------|
| C02 first encounter | How many iterations to resolve $queryRaw issues? |
| C05 second encounter | Did agent avoid $queryRaw (memory) or hit same issue again? |
| Time saved | C05 iteration delta between runs |

### TRAP-D: Float money precision (C04 → C05 → C09)
| Metric | Description |
|--------|-------------|
| C04 rounding discovery | Did agent encounter Float precision issues? How fixed? |
| C05 payout rounding | Did agent immediately add rounding (memory) or debug again? |
| C09 migration rationale | Did agent recall WHY integer cents are needed? |

### TRAP-E: Error format inconsistency (C01 → C03 → C05 → C12)
| Metric | Description |
|--------|-------------|
| Format used per change | C01: {error}, C03: {error, code}, C05: {error, code, details} |
| C12 consistency fix | How many endpoints needed fixing? Did agent know which? |
| Memory advantage | Memory agent knows which endpoints use which format |

### TRAP-F: Hidden cross-dependency (C04 → C07)
| Metric | Description |
|--------|-------------|
| C07 coupon stock fix | Did agent update the coupon stock validation when changing stock logic? |
| Discovery method | Memory recall vs. test failure vs. code search |
| Iterations to find | Count of iterations before the hidden dependency was discovered |

### TRAP-G: UI regression (C02 → C04/C07/C10/C12)
| Metric | Description |
|--------|-------------|
| Regression count | How many times did a UI fix get undone by a later change? |
| First-fix saves | Did memory of C02 UI fixes prevent regression in C04/C07? |
| Test regression fails | Count of REGRESSION check failures across all test scripts |
| Time to fix regressions | Iterations spent re-fixing previously fixed UI patterns |

### TRAP-H: formatPrice convention (C01 → C04 → C05 → C09 → C12)
| Metric | Description |
|--------|-------------|
| C01 creation | Did agent create `formatPrice()` at `src/lib/formatPrice.ts`? |
| C04/C05 usage | Did agent import and use `formatPrice()` for new price displays? |
| C09 payoff | Was updating a single utility sufficient, or did agent hunt for inline formats? |
| C12 consistency | How many inline format sites found and fixed? |

### TRAP-I: API pagination convention (C01 → C03 → C05 → C11 → C12)
| Metric | Description |
|--------|-------------|
| C01 format | Did agent implement `{ data, total, page, limit }` with query params? |
| C03/C05 consistency | Did new list endpoints follow the same format? |
| C11 payoff | Did agent recall the convention or implement pagination from scratch? |
| C12 consistency | How many endpoints needed format fixes? |

### TRAP-J: Error code constants (C02 → C03 → C05 → C07 → C12)
| Metric | Description |
|--------|-------------|
| C02 creation | Did agent create `src/lib/errors.ts` with constants? |
| C03/C05/C07 extension | Did agent extend the same file or create inline codes? |
| C12 consistency | How many error responses needed constant migration? |

### TRAP-K: Soft delete pattern (C01 → C04 → C08 → C12)
| Metric | Description |
|--------|-------------|
| C01 implementation | Did agent add `deletedAt` field and filter in queries? |
| C04 test | Did coupon validation check soft-delete status? |
| C08 migration | Did image migration handle soft-deleted products? |
| C12 audit | How many queries needed `deletedAt IS NULL` filter? |

### TRAP-L: Responsive convention (C01 → C02/C05/C06 → C10/C11 → C12)
| Metric | Description |
|--------|-------------|
| C01 creation | Did agent set up custom `sm:480px` breakpoints and `ResponsiveContainer`? |
| C02/C05/C06 recall | Did new pages use `ResponsiveContainer` without being reminded? |
| C10/C11 preservation | Did redesigned pages maintain the responsive convention? |
| C12 audit scope | How many pages needed ResponsiveContainer? How many iterations? |
| Intermediate test failures | Count of TRAP-L check failures in test-01 through test-11 |

### TRAP-M: Pagination UI drift (C01 → C03 → C11 → C12) — IMPLEMENTATION DRIFT
| Metric | Description |
|--------|-------------|
| C01 initial UI | What pagination UI pattern did the agent build on /products? |
| C03 divergence | Did /vendors and /orders use the same or different pagination pattern? |
| C11 reusability | Did agent create a reusable `<Pagination>` component or ad-hoc code? |
| Divergence count | How many DIFFERENT pagination implementations exist pre-C12? |
| C12 Bug 11 iterations | How many iterations to create shared Pagination and replace all instances? |
| C12 Bug 11 completeness | Were ALL list pages migrated to the shared component? |

### TRAP-N: Notification/feedback drift (C02 → C05 → C06 → C10 → C12) — IMPLEMENTATION DRIFT
| Metric | Description |
|--------|-------------|
| C02 initial pattern | What feedback did the agent use for cart removal? (alert/inline/nothing) |
| C05 error feedback | What pattern for checkout errors? Same or different from C02? |
| C06 status feedback | What pattern for vendor status changes? Same or different? |
| C10 toast reuse | Did agent build a reusable toast or cart-specific? |
| Divergence count | How many DIFFERENT feedback patterns exist pre-C12? |
| C12 Bug 12 iterations | How many iterations to create shared Toast and replace all instances? |
| C12 Bug 12 completeness | Were ALL alert()/confirm() calls removed? |

**Implementation drift vs convention traps**: Convention traps (H-L) test rule compliance. Drift traps (M-N) test whether the agent remembers its OWN implementation choices across pages. Memory value for drift traps comes from code-map memories, not convention memories.

## Run B Memory Metrics (additional)

For Run B (with memory) only, also track:

| Metric | Description |
|--------|-------------|
| Memory recalls | Count of `set-memory recall` invocations |
| Useful recalls | Recalls that visibly influenced agent behavior (from transcript review) |
| Memories saved | Count of `set-memory remember` invocations |
| Save quality | Were saves specific and actionable, or vague? (High/Medium/Low) |
| Recall efficiency | useful recalls / total recalls |

### How to identify "useful recalls"

A recall is useful if, after receiving recall results, the agent:
- Explicitly references the recalled information
- Adjusts its approach based on recalled knowledge
- Avoids a mistake that the baseline agent made

A recall is NOT useful if:
- The agent recalls but doesn't use the information
- The recalled memories are irrelevant to the current task
- The agent would have done the same thing without the recall

## Aggregate Scoring

After scoring all 12 changes, calculate:

| Aggregate Metric | Calculation |
|-----------------|-------------|
| Total dead ends | Sum across all changes |
| Total repeated mistakes | Sum across all changes |
| Total design rework | Sum across all changes |
| Test pass rate | Changes with first-try pass / 12 |
| Total test iterations | Sum of test-fix cycles across all changes |
| Total iterations | Sum of set-loop iterations across all changes |
| Total tokens | Sum across all changes |
| Total time | Sum across all changes |
| Revision change score | C07+C08+C09 aggregate |
| Feedback change score | C10+C11 aggregate |
| Sprint retro score | C12 bugs fixed on first try (out of 12) |
| Memory efficiency (Run B) | Useful recalls / total recalls |
| Save rate (Run B) | Memories saved / changes completed |

## Scoring Tips

- Review the full session transcript (`ralph-loop.log`), not just the final code
- Look for moments where the agent backtracks, comments on confusion, or retries
- Compare the agent's approach to the trap documentation — did they fall into the trap?
- For Run B, trace the causal chain: recall → behavior change → better outcome
- When in doubt, score conservatively (lower score = better performance)
- **Run the evaluator scripts** (`benchmark/evaluator/`) for automated schema/API/behavior checks
- **Run the test scripts** (`tests/test-NN.sh`) to get objective pass/fail data
- Focus on C07-C12 for the largest expected delta between runs
