## Context

The write-spec skill uses `profile.spec_sections()` to determine what to ask the user. The web module defines 7 sections (data_model, seed_catalog, pages_routes, auth_roles, i18n, design_tokens, test_strategy). The `test_strategy` section is `required=False`, placed last at phase 9, and its prompt_hint asks only two things: critical flows and test credentials.

The mature craftbrew spec demonstrates that effective test infrastructure descriptions cover 6 distinct concerns: credentials, data strategy, selectors, flows, mocks, and error contracts. This level of detail correlates with 14/14 merge success. Minimal specs produce agents that reinvent test patterns per-change.

The planner's `_PLANNING_RULES_CORE` already knows to create `test-infrastructure-setup` as the first change, but scopes it generically ("set up Playwright, config, helpers") because the spec doesn't describe what infrastructure is actually needed.

The review_learnings pipeline (`review_learnings_checklist()` → dispatcher input.md → review gate prefix) has been implemented across multiple changes. **Validated on set-designer v2 run (2026-05-10)**: JSONL has 15 entries, input.md files contain `## Review Learnings Checklist` with 30+ scope-filtered learnings, both `[project]` and `[template]` sources appear with count tracking (e.g., "seen 5x"). The pipeline works end-to-end. Remaining question: does the review gate LLM actually *use* the learnings to flag violations, or does it ignore them?

## Goals / Non-Goals

**Goals:**
- Transform the test_strategy SpecSection into a structured, multi-concern testing contract that guides spec authors toward craftbrew-level completeness
- Add profile-driven pre-decompose validation that catches missing testing context proportional to spec complexity
- Validate that review_learnings actually flows from JSONL → agent context → review gate on real runs
- Enable the planner to create spec-driven test-infra-setup changes with specific scope

**Non-Goals:**
- Changing the SpecSection dataclass structure (the existing fields are sufficient)
- Making pre-decompose validation blocking (it's advisory)
- Building new review_learnings features (only validating what exists works)
- Changing how the dispatcher injects test infra context (get_test_infra_summary is correct)
- Implementing test-plan.json changes (covered by e2e-test-enforcement change)

## Decisions

### Decision 1: Single expanded SpecSection vs multiple sub-sections

**Choice: Single section with structured prompt_hint that covers all 6 sub-concerns.**

Alternative considered: Split `test_strategy` into 6 separate SpecSections (test_credentials, test_data, test_selectors, etc.). Rejected because:
- The write-spec skill iterates sections sequentially — 6 testing prompts would feel repetitive
- Some sub-concerns are conditional (mock strategy only matters with external APIs)
- The skill is an LLM conversation — a rich prompt_hint with conditional guidance is more natural than rigid section boundaries
- A single section keeps the output in one place (docs/spec.md or docs/features/testing.md)

The prompt_hint becomes a structured guide with conditional branches the LLM follows based on detected project features.

### Decision 2: Phase placement for testing section

**Choice: Phase 6 (after pages_routes at 5, alongside auth_roles).**

Rationale: Testing strategy is informed by pages/routes (which flows to test) and auth (which users to test with). Placing it at phase 6 means the user has already described their features and auth when they reach testing. Phase 9 (current) is too late — by then the user is fatigued and skips.

### Decision 3: required=True vs conditional requirement

**Choice: `required=True` for web projects.**

The section is always required for web projects because even minimal web apps need test credentials and critical flows. The sub-concerns within the section are conditionally prompted — the skill asks about mocks only if external APIs are detected, asks about selectors only if multiple features exist, etc. This way the section is never skippable but its depth adapts to project complexity.

### Decision 4: Pre-decompose validation location

**Choice: In `planner.py`, in `build_decomposition_context()`, before the decompose LLM call.**

Alternative considered: Separate validation step called by the engine before planner. Rejected because:
- The planner already loads the spec content and has access to the profile
- Warnings should appear in planner output/logs, not a separate process
- The validation is lightweight (regex/keyword scanning, not LLM)

Implementation: `profile.validate_spec_testing(spec_content: str) -> list[str]` returns warning strings. The planner logs them at WARNING level and includes them in the decompose context as "SPEC COMPLETENESS WARNINGS" so the LLM can compensate.

### Decision 5: Spec-driven test-infra-setup scoping

**Choice: Planner reads testing section from spec, appends specific items to test-infra-setup scope.**

When the planner creates the `test-infrastructure-setup` change:
1. Extract the testing section from spec content (by header matching)
2. If testing section exists and describes specific infrastructure (fixtures, selectors, mock approach), include those in the change's scope text
3. If no testing section, fall back to generic scope (current behavior)

This is a small change to `render_flat_prompt()` and `render_domain_decompose_prompt()` — prepend the testing section to the context so the LLM planner can reference it when scoping test-infra-setup.

### Decision 6: Review learnings validation approach

**Choice: Manual trace on an existing E2E run + automated assertions added to the test suite.**

The validation has two parts:
1. **Manual trace** (one-time, during apply): Run through the craftbrew or micro-web scaffold, inspect JSONL files, grep worktree input.md for learnings section, grep review gate output for learnings prefix. Document findings.
2. **Automated guard** (permanent): Add a test in `tests/` that calls `review_learnings_checklist()` with a fixture JSONL and verifies non-empty output. Add a test that verifies `_build_input_content()` includes learnings when `review_learnings` is present in dispatch context.

This is NOT a full integration test — it verifies the wiring at unit level and documents the manual trace results.

## Risks / Trade-offs

**[Risk] Write-spec prompt complexity** — A rich prompt_hint with 6 sub-concerns might overwhelm users or cause the LLM to ask too many questions.
→ Mitigation: Sub-concerns are conditional. The skill asks about mocks only when external APIs are detected, about selectors only when 3+ features exist. Simple projects get 2-3 questions, complex ones get 5-6.

**[Risk] Pre-decompose validation false positives** — Validation might warn about missing test credentials for a project that intentionally has no auth.
→ Mitigation: Validation checks are conditional on detected features (auth → creds, data model → seed, real-time → mocks). If auth is not in scope, no warning about missing test credentials.

**[Risk] Review learnings may have subtle injection bugs** — The pipeline spans 4 files and 3 LLM calls. A bug in any step silently breaks the loop.
→ Mitigation: The manual trace during apply will surface any gaps. Automated unit tests prevent regression.

**[Risk] Spec-driven test-infra scoping depends on spec format** — If the testing section uses unexpected headers or structure, extraction fails.
→ Mitigation: Use fuzzy header matching (case-insensitive, common variants: "E2E Tests", "Testing", "Test Strategy", "Test Infrastructure"). Fall back to generic scope on extraction failure.

## Addendum: Empirical Findings from set-designer v2 Run (2026-05-10)

Investigation of the live set-designer v2 run (phase 3, 4/5 non-fix changes merged) produced these findings that inform implementation:

### Review Learnings Pipeline — Confirmed Working

| Pipeline Stage | Status | Evidence |
|---|---|---|
| JSONL persistence | Working | 15 entries in `review-learnings.jsonl`, proper severity/count |
| Scope-filtered checklist | Working | Both `[project]` and `[template]` sources with count tracking |
| Dispatcher injection | Working | Every worktree's `input.md` has `## Review Learnings Checklist` section |
| Review gate prefix | Working | `verifier.py:3259-3282` constructs and injects `learnings_prefix` |
| LLM evaluation | **WORKING** | 16/16 learnings have matching findings (100% recognition rate) |

**Implication**: The entire pipeline is validated end-to-end. The LLM reviewer actively checks against known patterns. The gap is not in recognition but in fix compliance: 2 learnings marked NOT_FIXED (fix didn't stick or caused regression). This suggests the feedback loop needs a "fix verification" stage, not stronger injection.

### set-designer Spec Testing Coverage (natural, without template)

The v2 spec covers 5/6 sub-concerns naturally, showing that well-written specs already tend toward this structure:

| Sub-concern | Coverage | Spec text |
|---|---|---|
| Test credentials | N/A (no auth) | Correctly absent |
| Test data strategy | Partial | "ephemeral `tmp-e2e-target/`" — no cleanup/reset detail |
| Selector contract | Strong | `data-testid` in 50+ ACs, naming convention, priority order |
| Critical flows | Strong | 57 acceptance criteria with specific assertions |
| Mock strategy | Strong | `tools/mock-claude.mjs` via `SET_DESIGN_CLAUDE_BIN` explicitly |
| Error contracts | Partial | Error codes in ACs (TARGET_NOT_FOUND, etc.) but no dedicated section |

**Implication**: The spec section redesign should formalize what good spec authors already do naturally, not impose an artificial structure. The template should surface sub-concerns as prompts, not as rigid sections that must all be filled.

### Run Outcome Correlation

4 merged, 1 exhausted (websocket-server-and-brain at retry=12), 3 ISS-spawned (1 merged, 2 skipped). The exhausted change had 8 ahead commits — it did substantial work but couldn't pass E2E gates. The spec had mock strategy for Claude (`mock-claude.mjs`) but no guidance on WebSocket test infrastructure — the agent had to discover `routeWebSocket` patterns on its own. This supports the thesis: missing test infra guidance → agent retry exhaustion.

### Review Findings Content Quality

28 review findings in `review-findings.jsonl`. The learnings include specific, actionable patterns like:
- "Playwright `testDir` mismatch — manifest spec will never run" (seen 3x)
- "`handleRetryOpen` silently swallows failure after `init-git`" (seen 5x)

High-count patterns (5x) are genuinely recurring issues, not noise. The persistence and count-tracking work correctly.

### Post-Run Analysis: websocket-server-and-brain Exhaustion Root Cause

The change exhausted at retry=12 because of **5 undocumented test infrastructure classes** the agent had to discover through failure feedback:

| Infrastructure Class | Spec Guidance | Discovery Cost |
|---|---|---|
| Global E2E setup (scaffold git repos, config.json) | "ephemeral tmp-e2e-target/" (one line) | 2 retries |
| WebServer timeout (120s not 60s) | Not mentioned | 2 retries (exit_code=1, empty failures) |
| Test route architecture (20+ `/__test/` routes) | Not mentioned | 3 retries |
| Hydration timing guards (React 19 networkidle) | Not mentioned | 2 retries |
| HMR upgrade forwarding in custom server.ts | "intercept /_ws" (incomplete) | 3 retries |

Each class caused a distinct failure mode that appeared only after the previous one was fixed. The agent DID eventually solve all of them (260 tests pass, 8 commits ahead) but hit the retry=12 ceiling before the final gate pass.

**Implication**: The spec's testing section should describe test infrastructure *patterns* (global setup, route architecture, timing constraints) not just test *requirements* (min test counts, selector conventions). The websocket-server-and-brain would have merged in 2-3 retries instead of 12 if these patterns were documented.

### Post-Run Analysis: Organic Test Infrastructure Quality

Agents built capable test infrastructure but with significant duplication:

| Pattern | Quality | Waste |
|---|---|---|
| `freshTarget()` factory | Excellent API design | Invented 3x independently across spec files |
| WS mock (`routeWebSocket`) | Sophisticated, supports custom handlers + state persistence | Not described in spec, agent had to invent |
| `seedChatWithActivities()` | Good JSONL event construction | Stays inline, not extracted to helpers/ |
| `navigateWithMockWs()` | Clean high-level abstraction | Created by one agent, underutilized by others |
| Test route convention (`/__test/`) | Clear naming | Not described in spec, inconsistently applied |

**Total test infrastructure**: ~6000 lines of E2E across 14 spec files, but ~20% is duplicated code that should have been shared. The spec's `tests/e2e/helpers/README.md` established the convention but agents didn't consistently follow it — they built inline first, extracted later (if at all).

### Decision 7: Test Thoughts vs Concrete Test Cases (New)

**Choice: Introduce a "Test Stories" sub-concern that describes user journeys at narrative level, alongside the concrete infrastructure sub-concerns.**

The set-designer run revealed that the spec's 57 acceptance criteria (concrete: `data-testid='welcome-screen'` is visible) were effective for structural verification but didn't capture the *behavioral flow* — what happens when you type in the chat, what the brain should return, how the preview should update.

A "test story" is a higher-level description of a user journey that the implementing agent elaborates into concrete tests:

```
# Test Story: Chat-to-Preview flow
User types "add a button component" in the chat input and presses Enter.
The brain receives the message via WS, processes it (mock returns a
code change to app/page.tsx), and the chat shows the assistant's
response with a file-changed activity group. The preview iframe
reloads and the new button is visible.

# Test Story: Target dirty state
User opens a target, the brain makes a code change (one file modified).
The status bar shows "1 file changed". User clicks undo — the file
reverts, status bar shows clean state. User makes another change,
then tries to close target — a confirmation dialog appears.
```

This serves three purposes:
1. **Spec completeness**: Captures behavioral intent that acceptance criteria miss
2. **Agent guidance**: More helpful than "min 6 tests" — tells the agent WHAT to test
3. **Reverse engineering input**: For existing systems, describe how it SHOULD work, and the system generates tests from the description. If tests fail, the gap between description and reality is the specification of needed changes.

The write-spec skill should include "Test Stories" as a sub-concern (phase 6, alongside critical flows). The stories get included in the agent's input.md and inform test-plan.json generation. They are NOT converted to concrete test code at spec time — that happens during implementation.
