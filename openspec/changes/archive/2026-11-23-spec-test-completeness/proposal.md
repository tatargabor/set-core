> **Superseded 2026-11-23 — closed without implementing the open tasks.** This change extends the
> orchestration engine (E2E gates, decompose/planner, fix-iss, the web project template and the
> run dashboards), which `fleet-era-consolidation` retires (stages 4-5: `retire-orchestration-cli`,
> `retire-orchestration-engine`). Archived with `--skip-specs` semantics: no delta reached
> `openspec/specs/`. Tasks ticked here were shipped; unticked ones were not.

## Why

The write-spec skill's `test_strategy` section is a single optional prompt ("Critical flows? Test credentials?") at phase 9 — the last section, easily skipped. Mature specs like the craftbrew scaffold have 5x more testing context (selector contracts, data isolation, mock strategy, adversarial fixtures, error code contracts) and consistently produce 14/14 merged changes. Meanwhile, minimal specs produce agents that invent test infrastructure ad-hoc, causing first-change floundering and cross-change inconsistency. The gap is upstream: 8 active e2e openspec changes address execution-level problems (discovery, scaffolding, enforcement, recovery) but all compensate for specs that never described test infrastructure requirements in the first place.

Additionally, the review_learnings pipeline is assumed to work end-to-end (learnings → injection → agent context → evaluation) but has never been validated on a real run. If learnings don't actually reach agents or don't influence behavior, the entire feedback loop is broken silently.

## What Changes

### 1. Spec test infrastructure section redesign

Replace the single `test_strategy` SpecSection in the web module with a structured, multi-concern testing section. The new section covers: test credentials, test data/seed strategy, selector contracts (data-testid registry), critical flows, mock/fixture strategy, and error code contracts. Make it `required=True` for web projects and move it earlier in phase order (alongside pages_routes, phase 5) so it shapes decompose input rather than being an afterthought.

Enhance the write-spec skill's prompt flow to guide users through each sub-concern with targeted questions. The skill adapts based on detected project features: auth in scope → ask about test users; data model present → ask about seed/reset strategy; real-time features → ask about mock approach.

### 2. Pre-decompose spec validation

Add a lightweight spec completeness check in the planner that runs before decompose. Profile-driven: `validate_spec_testing(spec_content) -> list[str]` returns non-blocking warnings when testing context is missing proportional to spec complexity. Examples: "Spec has auth requirements but no test credentials defined", "Spec has 5+ entities but no seed/reset strategy described", "Spec has WebSocket features but no mock strategy".

The planner logs these warnings and optionally surfaces them to the user (via sentinel findings or decompose output) but does NOT block decomposition.

### 3. Review learnings pipeline validation

Add concrete validation tasks that trace the review_learnings pipeline end-to-end on a real E2E run:
- Verify learnings JSONL files exist and contain entries after a run
- Verify `review_learnings_checklist()` returns non-empty content for relevant scopes
- Verify the dispatcher actually injects learnings into agent input.md (grep the worktree)
- Verify the review gate prompt includes learnings prefix
- Document any gaps found and fix them

### 4. Spec-driven test-infra-setup scoping

When the planner creates `test-infrastructure-setup`, it reads the spec's testing section to scope the change specifically (e.g., "create auth fixture with customer1/admin users, seed data reset utility, shared selectors.ts with 15 registered testids") instead of the generic "set up Playwright, config, global-setup" it produces today.

## Capabilities

### New Capabilities
- `spec-test-completeness`: Defines the enhanced testing section contract for spec writing, pre-decompose validation logic, and spec-driven test-infra scoping. Covers the SpecSection redesign, profile methods for validation, and planner integration.

### Modified Capabilities
- `review-learnings`: Add end-to-end validation requirements — learnings must demonstrably reach agent context and review gate prompts on real runs.

## Impact

### Core (`lib/set_orch/`)
- `profile_types.py` — SpecSection remains unchanged structurally, but CoreProfile gains `validate_spec_testing()` method with default no-op
- `planner.py` — calls `profile.validate_spec_testing()` before decompose, logs warnings; reads testing section for test-infra-setup scope assembly
- `templates.py` — test-infra-setup scope text becomes spec-driven when testing section is present
- `dispatcher.py` — no changes (already injects test infra context)
- `verifier.py` — review gate learnings injection verified (may need fixes if gaps found)

### Web module (`modules/web/`)
- `project_type.py` — `spec_sections()` replaces single `test_strategy` with expanded testing section(s); implements `validate_spec_testing()` with web-specific checks (auth → creds, data model → seed, real-time → mocks)

### Skills
- `.claude/skills/set/write-spec/SKILL.md` — enhanced testing section flow with sub-concern prompts and adaptive questioning based on detected features

### Docs
- `docs/guide/writing-specs.md` — expanded "E2E Test Expectations" section with examples from craftbrew-level completeness

### Validation
- E2E run with enhanced spec to verify testing section flows through decompose → dispatch → agent
- Review learnings pipeline trace on existing or new run
