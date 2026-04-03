# Design: Init Safety and Acceptance Gate

## Context

`set-project init` deploys template files to consumer projects. The flow:
1. `bin/set-project` `cmd_init()` → `deploy_set_tools()` (framework files) → `_deploy_project_templates()` (scaffold/config)
2. `_deploy_project_templates()` calls `profile_deploy.py:deploy_templates()` with `--force` on re-init
3. `deploy_templates()` iterates `manifest.yaml` file list, copies each with `shutil.copy2`

The planner (`templates.py`) generates decomposition prompts for the orchestrator. It currently has a "test-per-change" rule but no directive for cross-feature acceptance tests.

`max_parallel` defaults to 3 in `config.py:DIRECTIVE_DEFAULTS`.

## Goals / Non-Goals

**Goals:**
- Protected scaffold files survive re-init unchanged
- Config.yaml re-init merges additively (new keys added, existing preserved)
- Planner always generates a final acceptance-tests change
- max_parallel defaults to 1

**Non-Goals:**
- Changing the phase-end E2E infrastructure (it works, just not triggered by planner)
- Per-file force/skip override CLI flags
- Automatic detection of "which files are scaffold vs framework" — we use explicit manifest annotation

## Decisions

### D1: Manifest `protected` flag for scaffold files

**Choice:** Add `protected: true` annotation per-file in `manifest.yaml`.

**Alternative considered:** Auto-detect by checking git diff. Rejected because: not all files in the template should be protected (framework rules should always update), and some projects may not have git history.

**How it works:**
- `manifest.yaml` `core` section changes from flat list to list of objects:
  ```yaml
  core:
    - path: .gitignore
    - path: next.config.js
      protected: true
    - path: src/app/globals.css
      protected: true
    - path: set/orchestration/config.yaml
      merge: true
  ```
- `_resolve_file_list()` returns `List[FileEntry]` (dataclass with `path`, `protected`, `merge` fields) instead of `List[str]`
- `deploy_templates()` checks: if `protected` and `force` and file exists and `_file_modified_from_template(dst, src)` → skip
- `_file_modified_from_template()` compares file content hash — if different from template, it's been modified

### D2: Content hash comparison (not git diff)

**Choice:** Compare SHA256 of existing file vs template file.

**Alternative considered:** `git diff HEAD -- <file>` to check modification. Rejected because: requires git, fails in fresh clones, and the real question is "does the file differ from the template?" not "has it been committed."

If the file content matches the template exactly → safe to overwrite (no project changes). If different → protected, skip.

### D3: Additive YAML merge for config files

**Choice:** Files marked `merge: true` in manifest use YAML merge logic instead of overwrite.

**How it works:**
- Load existing YAML, load template YAML
- For each key in template: if key missing in existing → add it
- Never overwrite existing keys
- Write back merged result
- This matches the existing `_migrate_consumer()` pattern in `bin/set-project`

### D4: Planner acceptance-tests directive

**Choice:** Add a section to the decompose prompt in `templates.py` that instructs the planner to always include a final `acceptance-tests` change.

**The directive has two parts:**

**Part 1 — Planner-time (in decompose prompt):** Tells the planner to generate the change + extract journeys from the spec.

```
Acceptance test change (REQUIRED):
- Always include a final change named "acceptance-tests" with type "test"
- This change depends_on ALL other changes (it runs last, in the final phase)
- Analyze the spec domains and identify cross-domain user journeys:
  - Look for data flows where one domain's output feeds another domain's input
  - Look for multi-actor interactions (user creates, admin manages, user sees result)
  - Look for sequential user workflows that span 3+ features
- List each journey by name and the domains it crosses in the scope field
- Target files: tests/e2e/journey-<name>.spec.ts
```

**Part 2 — Agent-time (in the acceptance-tests change scope, injected by planner):** Methodology rules the agent follows when writing the tests. These are generic, project-agnostic patterns.

```
Journey test methodology:
1. ISOLATION: Each journey spec file is self-contained. Set up preconditions
   via API calls in beforeAll, never depend on state from another spec file.
   Use browser.newContext() for fresh cookies/session per journey.

2. SERIAL STEPS: Use test.describe.serial() with a shared Page created in
   beforeAll. Each step builds on the previous (login → browse → cart → checkout).
   Do NOT use the default { page } fixture — it creates a fresh page per test.

3. DATA STRATEGY: Read seed data (prisma/seed.ts or equivalent) to discover
   available entities. Use seed data for reads (products, categories). For writes
   that mutate state (orders, subscriptions), create a fresh test user via the
   registration API to avoid coupling between journeys.

4. THIRD-PARTY SERVICES: If a journey requires an external service (payment,
   email), check for test-mode keys in .env. If available, use test mode
   (e.g., Stripe test cards). If not, test the flow up to the external call
   and verify via API side-effects. Never skip the journey entirely.

5. IDEMPOTENCY: Tests must survive re-runs. Use unique identifiers (timestamps,
   random suffixes), clean up in afterAll, or design assertions that tolerate
   pre-existing data.

6. FIX-UNTIL-PASS: Run tests, fix failures (app code or test code), re-run
   only failed tests. Repeat until all pass or token budget exhausted.

7. COVERAGE: After writing all journeys, verify every testable spec AC has at
   least one journey step covering it. Add tests for gaps. Document non-testable
   ACs (email, background jobs) as exempt.
```

**Layer separation (core vs module):**

The directive has framework-agnostic parts (core) and framework-specific parts (web module):

| Layer | Content | Where |
|-------|---------|-------|
| **Core** (`templates.py`) | Part 1 planner directive: include acceptance-tests change, extract cross-domain journeys | Decompose prompt |
| **Core** (`templates.py`) | Part 2 generic rules: isolation, idempotency, data strategy, third-party handling, fix-until-pass, coverage verification | Scope boilerplate |
| **Web module** (`ProjectType`) | Playwright-specific: `test.describe.serial()` pattern, `browser.newContext()`, `journey-*.spec.ts` naming, `npx playwright test --grep` for re-runs | `acceptance_test_methodology()` method on `WebProjectType` |

The planner calls `profile.acceptance_test_methodology()` and appends the result to the acceptance-tests scope. Non-web project types can return their own test framework patterns (e.g., pytest for Python projects). This follows the existing pattern where `profile.detect_e2e_command()` already provides framework-specific E2E detection.

**Why in the planner and not as a new engine feature:** The existing per-change merge gate already runs the E2E command which will execute the journey tests. No new gate type needed.

### D5: max_parallel: 1 default

**Choice:** Simple — change `DIRECTIVE_DEFAULTS["max_parallel"]` from 3 to 1.

**Rationale:** Sequential execution ensures each change sees all previous changes' work. The performance cost is acceptable because quality is more important than speed at this stage. Projects can override to higher values when their AC gate reliably catches cross-change issues.

## Risks / Trade-offs

- **[Risk] Manifest format change breaks external tooling** → Mitigation: `_resolve_file_list()` handles both old format (plain strings) and new format (objects) for backward compatibility
- **[Risk] Content hash gives false positive** (file modified but happens to match template) → Extremely unlikely and harmless (file gets overwritten with identical content)
- **[Risk] Acceptance-tests change adds wall-clock time** → Mitigation: It only runs after all changes merge, so it doesn't block parallel execution. Typically 5-15 minutes.
- **[Risk] max_parallel: 1 slows orchestration** → Expected. This is the intended trade-off. Can be overridden per-project.

## Open Questions

None — all decisions are straightforward and reversible.
