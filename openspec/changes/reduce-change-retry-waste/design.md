# Design: Reduce Change Retry Waste

## Context

The verify pipeline currently registers gates in this order (`lib/set_orch/verifier.py:2962-3032`):

```
build → test → [profile gates: e2e, lint] → scope_check → test_files → e2e_coverage → review → rules → spec_verify
```

Two things follow from this:

1. **`review` runs at position 7, `spec_verify` at position 9.** When `review` fails (which is common — every change in recent runs has had at least one review finding), the pipeline stops, retries the change, and only reaches `spec_verify` after review passes. If `spec_verify` then reveals a spec-coverage gap, the change has already paid the cost of 1-2 review retries with no benefit.

2. **The two gates are fully independent.** Verified in the code:
   - `_execute_review_gate` (verifier.py:2310-2428) builds its prompt from prior findings JSONL, e2e coverage report, shadcn detection. No reference to `spec_verify_output` or `spec_coverage_result`.
   - `_execute_spec_verify_gate` (verifier.py:2478-2600) runs `/opsx:verify` via Claude and parses `CRITICAL_COUNT`/`VERIFY_RESULT` sentinels. No reference to `review_output` or `review_result`.

   Swapping their order has no data dependency to break.

The `e2e_retry_limit` duplication is a similar low-risk fix: `engine.py:64` is the authoritative `Directives` dataclass default (`5`), `merger.py:1704` is the fallback read when the directive dict has no key (`3`). In practice, `Directives` is always created first and then written to the state file, so the merger's fallback almost never fires — but when it does (e.g. recovery from a corrupted directives dict), the behavior silently changes.

The Playwright rule gaps are also verified against the current web template (`modules/web/set_project_web/templates/nextjs/rules/testing-conventions.md`):
- The template has a `Selector Best Practices` section and a `Playwright Strict Mode on Repeated Elements` section — both cover visual repetition (rating badges, cart counts) but not **label prefix ambiguity** (`"Description"` vs `"Short Description"`).
- The template has a `DB Isolation for E2E Tests` section explaining that SQLite is per-worktree — but says nothing about **intra-worktree cross-spec pollution** when alphabetically-ordered specs share the same dev.db.
- The template has a `waitForURL` section — but only covers client-side nav timing, not regex ambiguity on intermediate routes.

## Goals / Non-Goals

**Goals:**
- Surface specification gaps in the first verify cycle, not after multiple review retries.
- Eliminate the retry limit default mismatch so directive behavior is predictable regardless of read path.
- Codify the 3 missing Playwright patterns so agents generate isolation-safe tests on the first attempt.

**Non-Goals:**
- Redesigning the review gate's scope or prompt (it stays as-is — this change only moves it).
- Adding new gates (e.g. a dedicated cross-spec isolation gate).
- Changing the wt-e2e vs integration-e2e split, smoke phase behavior, or worktree-scoped command building. Those have their own design trade-offs and belong in a separate change.
- Overhauling the retry counter mechanism — the counter and CHANGE_REDISPATCH event stay as they are.
- Changing `scope_check` or `test_files` positioning — they remain early because they're cheap pre-flight checks.

## Decisions

### 1. Swap spec_verify to run immediately after build/test/e2e, before review

**Choice:** New order:
```
build → test → [e2e, lint] → scope_check → test_files → e2e_coverage → spec_verify → rules → review
```

**Why this specific placement?**

- `spec_verify` needs a passing build/test/e2e environment to evaluate coverage meaningfully — so it stays after those.
- `scope_check`, `test_files`, and `e2e_coverage` are structural pre-checks that are fast (milliseconds). Keeping them before `spec_verify` avoids running an LLM call when the change is trivially incomplete.
- `rules` is a static-analysis style gate (regex/pattern rules from `.claude/rules/`) — cheap, deterministic. It fits naturally between spec_verify and review.
- `review` becomes the final gate. Intuition: by the time we pay for a review LLM call, the implementation has already survived build/test/e2e/spec_verify, so review finds genuine quality issues and not spec gaps masquerading as "incomplete".

**Alternatives considered:**
- Move `spec_verify` to position 1 (before build) — rejected. It relies on compiled types and working tests to give meaningful output.
- Move `review` to run in parallel with `spec_verify` — rejected. Gates are sequential in the pipeline; parallelism would require structural changes to `PipelineRunner` out of scope here.
- Leave the order alone and add a "cheap spec-structure check" early — rejected. Would create a third mechanism to maintain and duplicates spec_verify's logic.

### 2. Single constant for e2e_retry_limit default

**Choice:** Define `DEFAULT_E2E_RETRY_LIMIT = 3` in `lib/set_orch/engine.py` as a module-level constant. Both `Directives.e2e_retry_limit` field default and `merger.py`'s fallback read reference the same constant.

**Why `3` and not `5`?**
- The current `merger.py:1704` fallback is `3`, and recent runs show that legitimate successes need at most 2 redispatches. A limit of `3` already allows a retry-for-flakiness margin.
- Lowering from `5` to `3` prevents runaway loops that waste tokens on changes where repeated failure is symptomatic of a deeper issue.
- Directive overrides still work — users who want `5` set it explicitly in the config.

**Alternatives considered:**
- Pick `5` (the current engine default) — rejected. It's too permissive; the minishop-level observations show 3 is enough.
- Leave both values as-is and add a warning log — rejected. The mismatch is a silent footgun; a warning doesn't fix it.

### 3. Append three rule sections to testing-conventions.md, not replace existing sections

**Choice:** Each rule becomes a new `## ` section appended after the existing `## Selector Best Practices` / `## Playwright Strict Mode on Repeated Elements` sections:
1. `## Cross-Spec DB Pollution — Exact Counts Forbidden`
2. `## getByLabel Prefix Ambiguity — Require exact: true`
3. `## toHaveURL Regex — Exclude Intermediate Routes`

**Why append, not edit existing sections?** The existing sections are well-scoped; interleaving would fragment them. New sections keep the narrative flow of the document. Each section is ~15-25 lines and self-contained.

**Rule text content** (summarized, full text in the tasks):
- Section 1: Warn about `toHaveCount(N)` when specs from multiple changes run against the same dev.db in the integration run. Use `toHaveCount({ min: N })` or scope the count to a data-testid'd container.
- Section 2: `getByLabel("Description")` matches both `"Description"` and `"Short Description"` labels by default. Use `getByLabel("Description", { exact: true })` whenever a label text is a substring of another on the same page.
- Section 3: `toHaveURL(/\/admin/)` matches `/admin/login` immediately, causing races. Use negative-lookahead: `toHaveURL(/\/admin(?!\/login)/)` or anchor: `toHaveURL(/\/admin\/dashboard/)`.

## Risks / Trade-offs

- **[Risk] Reordering hides review feedback that spec_verify could tolerate.** If `spec_verify` fails loudly on something review would've caught more gracefully, the agent gets a different (possibly less-actionable) error first. Mitigation: both gates remain in the pipeline and both write their outputs to state. The retry prompt aggregates all failing gates, so the agent still sees review findings if they accumulate.
- **[Risk] Lowering e2e_retry_limit default from 5 to 3 causes premature failure on flaky suites.** Mitigation: directive override still exists; projects with known flakiness can set `e2e_retry_limit: 5` explicitly.
- **[Risk] New Playwright rules bloat the agent context.** Mitigation: the rules file is already ~460 lines; adding ~60 lines (3 sections × ~20 lines) is <15% growth. The rules are only injected into prompts that touch `tests/e2e/*`, not every call.
- **[Trade-off] This change does NOT fix cross-spec DB pollution at the orchestration level** (e.g. by running full-suite e2e in the worktree, or blocking the smoke phase of integration e2e). Those are bigger redesigns and are intentionally deferred. The rules in this change are a preventive teaching measure; the deeper fix is a separate future change.
- **[Trade-off] Gate reorder may shift gate_ms totals in dashboards.** Expected — dashboards display per-gate timings and users will simply see spec_verify appear earlier in the timeline. No metric keys change.

## Verification Plan

- Unit: no behavioral unit tests exist for verifier pipeline order today. Add a regression test that asserts the registered gate names in order.
- Integration: run a small e2e (2-3 changes) against the new order and compare total wall time and retry count against a baseline. Expect same or fewer retries.
- Code search: grep for any other hardcoded `e2e_retry_limit` references to ensure the constant is the only source.
- Template lint: ensure the 3 new sections parse as valid markdown headings and the rule snippets are syntactically valid TypeScript.
