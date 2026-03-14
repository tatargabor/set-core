"""Safe structured text generation for orchestration prompts and proposals.

Replaces unquoted bash heredocs with Python f-strings and explicit escaping,
preventing variable expansion bugs ($, backtick, EOF markers).
"""

from __future__ import annotations

import re

# Maximum diff size before truncation
MAX_DIFF_CHARS = 50_000


def escape_for_prompt(text: str) -> str:
    """Neutralize characters that would break shell heredoc expansion.

    Handles: $ (variable expansion), ` (command substitution), EOF markers.
    Plain text passes through unchanged.
    """
    if not text:
        return text

    # In Python templates, these characters are harmless — they're just strings.
    # This function exists for the bash→python transition: if the rendered output
    # is ever passed back through a shell heredoc, these would need escaping.
    # For now, we pass through unchanged since Python renders directly to stdout.
    return text


def _truncate(text: str, max_chars: int, label: str = "content") -> str:
    """Truncate text with a marker if it exceeds max_chars."""
    if len(text) <= max_chars:
        return text
    return text[:max_chars] + f"\n\n... {label} truncated at {max_chars} characters ..."


def _optional_section(header: str, content: str) -> str:
    """Render a section only if content is non-empty."""
    if not content or not content.strip():
        return ""
    return f"\n{header}\n{content}"


# ─── Proposal Template ─────────────────────────────────────────────────


def render_proposal(
    change_name: str,
    scope: str,
    roadmap_item: str,
    memory_ctx: str = "",
    spec_ref: str = "",
) -> str:
    """Render proposal.md content for a new change.

    Replaces the 3 concatenated heredocs in dispatcher.sh:
    PROPOSAL_EOF + MEMORY_EOF + SPECREF_EOF
    """
    parts = [f"""## Why

{roadmap_item}

## What Changes

{scope}

## Capabilities

### New Capabilities
- `{change_name}`: {roadmap_item}

### Modified Capabilities

## Impact

To be determined during design phase."""]

    if memory_ctx and memory_ctx.strip():
        parts.append(f"""

## Context from Memory

{memory_ctx}""")

    if spec_ref and spec_ref.strip():
        parts.append(f"""

## Source Spec
- Path: `{spec_ref}`
- Section: `{roadmap_item}`
- Full spec available via: `cat {spec_ref}`""")

    return "\n".join(parts)


# ─── Review Prompt Template ────────────────────────────────────────────


def render_review_prompt(
    scope: str,
    diff_output: str,
    req_section: str = "",
    design_compliance: str = "",
) -> str:
    """Render code review prompt for Claude.

    Replaces verifier.sh REVIEW_EOF heredoc.
    """
    diff_output = _truncate(diff_output, MAX_DIFF_CHARS, "diff output")

    design_section = f"\n{design_compliance}\n" if design_compliance and design_compliance.strip() else ""

    return f"""You are a senior code reviewer. Review this diff for critical issues.

## Change Scope
{scope}

## Diff
```diff
{diff_output}
```
{req_section}
{design_section}
## Review Criteria
Check for:
1. Security vulnerabilities: SQL injection, XSS, command injection, path traversal
2. Authentication/authorization gaps: missing auth checks, broken access control
3. Tenant isolation: can one user/org access another's data?
4. Data integrity: missing validation, race conditions, data loss risks
5. Error handling: unhandled exceptions that crash the app

For each issue found, classify severity as: CRITICAL, HIGH, MEDIUM, LOW.

Output format:
- If no issues: "REVIEW PASS — no critical issues found"
- If issues found:
  ISSUE: [severity] description
  FILE: path/to/file
  LINE: approximate line number

Only flag real problems — not style preferences."""


# ─── Fix Prompt Templates ──────────────────────────────────────────────


def render_fix_prompt(
    change_name: str,
    scope: str,
    output_tail: str,
    smoke_cmd: str,
    modified_files: str = "",
    multi_change_context: str = "",
    variant: str = "smoke",
) -> str:
    """Render smoke/e2e fix prompt for Claude.

    Replaces merger.sh SMOKE_FIX_EOF and verifier.sh SCOPED_FIX_EOF heredocs.
    variant="smoke" for merger.sh style, variant="scoped" for verifier.sh style.
    """
    if variant == "scoped":
        return f"""Post-merge smoke/e2e tests failed on main after merging "{change_name}".

## Change scope
{scope}

## Files modified by this change
{modified_files}
{multi_change_context}

## Smoke command
{smoke_cmd}

## Smoke output
{output_tail}

## Constraints
- MAY ONLY modify files that were part of this change (listed above)
- MUST NOT delete or weaken existing test assertions
- MUST NOT modify files outside the change scope
- Fix the root cause — either implementation code or test expectations

## Steps
1. Analyze the smoke test failures
2. Fix the root cause in the modified files
3. Commit with message: "fix: repair smoke after {change_name} merge\""""

    # Default: smoke variant (merger.sh style)
    return f"""Post-merge smoke/e2e tests failed on main after merging {change_name}.
Fix the code or tests so smoke tests pass again.
{multi_change_context}
Smoke command: {smoke_cmd}
Smoke output (last 2000 chars):
{output_tail[-2000:] if len(output_tail) > 2000 else output_tail}

Instructions:
1. Analyze the smoke test failures above
2. Fix the root cause — either the implementation code or the test expectations
3. Run: {smoke_cmd} — confirm it passes
4. Commit the fix with message: "fix: repair smoke tests after {change_name} merge"

Do NOT create a worktree — fix directly in the current directory."""


# ─── Build Fix Prompt ──────────────────────────────────────────────────


def render_build_fix_prompt(
    pm: str,
    build_cmd: str,
    build_output: str,
) -> str:
    """Render build error fix prompt. Replaces builder.sh FIX_EOF heredoc."""
    return f"""The main branch has build errors that are blocking all worktree builds.
Fix these TypeScript/build errors directly on the main branch.

Build command: {pm} run {build_cmd}
Build output (last 3000 chars):
{build_output[-3000:] if len(build_output) > 3000 else build_output}

Instructions:
1. Analyze the build errors above carefully
2. Fix the root cause (type errors, missing imports, missing @types packages, schema mismatches, etc.)
3. Run: {pm} run {build_cmd} — confirm it passes
4. Commit the fix with message: "fix: repair main branch build errors"

Do NOT create a worktree — fix directly in the current directory."""


# ─── Planning Prompt Templates ─────────────────────────────────────────

# Shared rules block used by both spec-mode and brief-mode
_PLANNING_RULES = """Rules:
- Each change should be completable in 1 Ralph loop session (not too large, not too granular)
- Use kebab-case names (e.g., add-user-auth, refactor-payment-flow)
- Define dependencies: if change B needs code from change A, list A in depends_on
- Changes with no dependencies can run in parallel
- Complexity: S (< 8 tasks, preferred), M (8-15 tasks, maximum). L (15+ tasks) is NOT ALLOWED — split into smaller changes.
- Max 6 requirements per change. If a feature domain has more than 6 requirements, split it into sub-domain changes.
- Scope text should be 800-1500 chars. If you need more than 2000 chars to describe a change, it is too large — split it.
- Skip already-active changes listed above
- Every change scope MUST include specific test requirements (happy path, error cases, security boundaries)
- For security-related changes: include tenant isolation tests, auth guard tests
- If no test infrastructure exists, the FIRST change MUST be "test-infrastructure-setup" setting up the test framework, config, helpers, and an example test. ALL other changes MUST depend on it.
- If test infrastructure exists, follow existing test patterns (framework and naming conventions noted above)
- NEVER create a standalone "e2e-consolidation", "playwright-e2e", or "e2e-tests" change that only writes E2E tests. This anti-pattern overloads one agent with all cross-feature tests and wastes tokens. Each feature change MUST include its OWN E2E tests inline.

Sub-domain dependency chaining:
- When splitting a large feature domain into multiple changes, those changes MUST form a depends_on chain (sequential execution within the domain)
- Different domain chains can still run in parallel with each other
- Example: splitting "product-catalog" (22 reqs) into product-list → product-detail → product-search — each depends_on the previous, but all can run in parallel with an unrelated "user-auth" chain

Split heuristics for common patterns:
- List page + detail page → split into separate changes if combined requirements exceed 6
- CRUD operations → separate from read-only views when the domain is large
- Search/filtering with its own API routes → separate change
- Auth + profile + password management → split auth/login from profile/account management

Dependency ordering heuristics — classify each change by type and apply ordering:
- Classify each change as one of: infrastructure (test/build setup, CI), schema (DB migrations, model changes), foundational (auth, shared types, base components), feature (new functionality), cleanup-before (refactor/rename/reorganize existing code), cleanup-after (dead code removal, cosmetic fixes)
- infrastructure changes run first — all others depend on them
- schema/migration changes run before data-layer or API changes that use those tables
- foundational changes (auth, shared types) run before features that consume them
- cleanup-before/refactor changes run before feature changes that touch the same area (e.g., a UI cleanup should complete before new UI features are built on that code)
- cleanup-after changes run last — they depend on the features they clean up around
- If the spec contains explicit dependency hints (e.g., "depends_on: X", "requires X", "after X is complete"), preserve them in the output depends_on array

Shared resource awareness:
- If 2+ parallel changes would likely modify the same shared file (conventions docs, shared types, config files, common UI components), chain them via depends_on to prevent merge conflicts
- Prefer serialization over parallel execution when shared files are involved
- Common shared resources: design/convention docs, shared type definitions, package.json, layout components

Test-per-change requirement:
- Each change that adds a user-facing route, feature, or API endpoint MUST include its own tests. Do NOT defer all testing to a final "e2e" change.
- The quality gate BLOCKS changes without test files for feature/infrastructure types.
- Explicitly list test files in scope (e.g., "Tests: Create orders.test.ts").

Playwright E2E test planning (when e2e_command is configured):
- The infrastructure/foundation change (first in dependency order) MUST set up Playwright alongside Jest:
  * Create playwright.config.ts with PW_PORT env var support and webServer auto-start
  * Add testPathIgnorePatterns: ["/node_modules/", "/tests/e2e/"] to jest.config (Jest crashes on Playwright .spec.ts imports in jsdom)
  * Add @playwright/test to devDependencies + run npx playwright install chromium
  * Create tests/e2e/global-setup.ts: prisma generate → prisma db push --force-reset → prisma db seed
- Each subsequent feature change creating a user-facing route MUST create tests/e2e/<feature>.spec.ts as an explicit file deliverable in scope (e.g., "Create tests/e2e/cart.spec.ts")
- Include CONCRETE test scenarios per feature:
  * Page URL to visit
  * User interactions: what to click, what data to type, what to select
  * Expected outcomes: visible text, redirects, error messages
  * Auth scenarios: verify protected routes redirect unauthenticated users
  * Error scenarios: invalid form input, missing required fields
  * COLD-VISIT test: navigate directly to the page as the FIRST action (no prior login, no add-to-cart, no session cookie). This catches Server Component cookie/session bugs where cookies().set() crashes outside a Server Action.
- Example scope:
  Create tests/e2e/orders.spec.ts:
  - Cold visit: go to /cart directly (no prior actions) → should show empty state, NOT crash
  - Visit /products → click "Add to Cart" on first product → cart badge shows "1"
  - Visit /cart → verify product name and price → click "Checkout" → fill form → verify redirect to /orders/[id]
  - Visit /admin/orders without login → verify redirect to /admin/login
- Do NOT defer all E2E tests to a consolidation change — this overloads a single agent. Each feature change owns its tests.
- Do NOT just list "Functional test scenarios:" as descriptions — create actual test files.
- E2E tests run pre-merge in the worktree via e2e_command against an auto-started dev server with isolated port and DB.

Phase assignment — group changes into execution phases for milestone checkpoints:
- Assign a phase integer (1..N, max 5) to each change
- Phase 1: infrastructure, schema, foundational changes
- Phases 2..N-1: features grouped by domain coherence (related features in same phase)
- Last phase: cleanup-after, polish
- For specs with fewer than 4 changes, assign all to phase 1
- Changes within a phase can run in parallel; phases execute sequentially
- Dependencies across phases are respected regardless of phase assignment

Model selection — suggest a model per change based on task nature:
- "opus" for ALL changes that write functional code (features, bug fixes, refactors, cleanup, tests)
- "sonnet" ONLY for doc-only changes (doc sync, doc audit, README updates) — zero code writing
- Sonnet cannot follow OpenSpec workflows, make architecture decisions, or write quality code
- When in doubt, always use "opus"

Manual tasks — flag changes that require human intervention:
- Set "has_manual_tasks": true when a change involves: external API keys/secrets (Stripe, AWS, Firebase), third-party account/project creation, OAuth app registration, DNS configuration, webhook setup, or any step that cannot be automated
- Examples: "integrate Stripe payments" (needs API key), "set up Firebase auth" (needs project creation), "configure custom domain" (needs DNS records)
- When false or omitted, all tasks are assumed automatable

CRITICAL — Output size constraint:
- Your ENTIRE JSON response MUST fit in a SINGLE message. You will NOT get a second turn.
- MAX 15 changes. If the spec requires more, merge related changes aggressively.
- Keep scope text concise (800-1500 chars). Do NOT pad with implementation details.
- Keep reasoning to 2-3 sentences. Keep phase_detected to 1 sentence.
- Do NOT split your response across messages."""

_DIGEST_FIELDS = """Digest-mode additional requirements:
- Each change MUST include "spec_files": an array of raw spec file paths (relative to spec base dir) that this change needs for implementation. These files will be copied into the worktree.
- Each change MUST include "requirements": an array of REQ-* IDs from the digest that this change owns and implements.
- If a change must incorporate a cross-cutting requirement owned by another change, list it in "also_affects_reqs" (not in "requirements").
- Every non-removed REQ-* ID in the digest MUST appear in exactly one change's "requirements" array. Cross-cutting requirements appear in one change's "requirements" (primary owner) and other changes' "also_affects_reqs"."""

_SPEC_OUTPUT_JSON = """{
  "phase_detected": "Description of which phase/section was selected and why",
  "reasoning": "Brief explanation of the decomposition choices",
  "changes": [
    {
      "name": "change-name",
      "scope": "Detailed description...",
      "complexity": "S|M|L",
      "change_type": "infrastructure|schema|foundational|feature|cleanup-before|cleanup-after",
      "model": "opus|sonnet",
      "has_manual_tasks": false,
      "depends_on": ["other-change-name"],
      "phase": 1,
      "roadmap_item": "The spec section/item this implements"
    }
  ]
}"""

_SPEC_OUTPUT_JSON_DIGEST = """{
  "phase_detected": "Description of which phase/section was selected and why",
  "reasoning": "Brief explanation of the decomposition choices",
  "changes": [
    {
      "name": "change-name",
      "scope": "Detailed description...",
      "complexity": "S|M|L",
      "change_type": "infrastructure|schema|foundational|feature|cleanup-before|cleanup-after",
      "model": "opus|sonnet",
      "has_manual_tasks": false,
      "depends_on": ["other-change-name"],
      "phase": 1,
      "roadmap_item": "The spec section/item this implements",
      "spec_files": ["path/relative/to/spec-base-dir.md"],
      "requirements": ["REQ-DOMAIN-001"],
      "also_affects_reqs": ["REQ-CROSS-001"],
      "resolved_ambiguities": [{"id": "AMB-001", "resolution_note": "Decision rationale"}]
    }
  ]
}"""

_BRIEF_OUTPUT_JSON = """{
  "changes": [
    {
      "name": "change-name",
      "scope": "Detailed description...",
      "complexity": "S|M|L",
      "change_type": "infrastructure|schema|foundational|feature|cleanup-before|cleanup-after",
      "model": "opus|sonnet",
      "has_manual_tasks": false,
      "depends_on": ["other-change-name"],
      "phase": 1,
      "roadmap_item": "The exact Next bullet this implements"
    }
  ]
}"""


def render_planning_prompt(
    input_content: str,
    specs: str,
    memory: str = "",
    replan_ctx: dict | None = None,
    mode: str = "spec",
    phase_instruction: str = "",
    input_mode: str = "",
    test_infra_context: str = "",
    pk_context: str = "",
    req_context: str = "",
    active_changes: str = "",
    coverage_info: str = "",
    design_context: str = "",
    team_mode: bool = False,
) -> str:
    """Render planning prompt for Claude decomposition.

    Replaces the 200-line spec-mode PROMPT_EOF (planner.sh:882-1074) and the
    127-line brief-mode PROMPT_EOF (planner.sh:1078-1204), including all nested
    heredocs (MEM_CTX, REPLAN_CTX, ORCH_HIST, E2E_CTX).

    Args:
        input_content: The spec or brief content to analyze
        specs: Existing OpenSpec specs summary
        memory: Project memory context
        replan_ctx: Dict with keys: completed, cycle, memory, e2e_failures
        mode: "spec" for spec/digest mode, "brief" for brief mode
        phase_instruction: Phase-specific instruction text
        input_mode: "digest" to include digest-specific fields
        test_infra_context: Test infrastructure description
        pk_context: Project knowledge context
        req_context: Requirements context
        active_changes: Active changes summary
        coverage_info: Coverage status text
        design_context: Design tool prompt section (from design bridge)
        team_mode: If True, add guidance for Agent Teams parallelism
    """
    if replan_ctx is None:
        replan_ctx = {}

    # Build optional sections
    sections = []

    if memory and memory.strip():
        sections.append(f"\n## Project Memory\n{memory}")

    if pk_context and pk_context.strip():
        sections.append(f"\n{pk_context}")

    if req_context and req_context.strip():
        sections.append(f"\n{req_context}")

    if design_context and design_context.strip():
        sections.append(f"\n{design_context}")

    if team_mode:
        sections.append("""
## Agent Teams Mode (ENABLED)
This orchestration uses Agent Teams for intra-change parallelism. Optimize your plan:
- Prefer fewer, larger changes with 5+ independent tasks each over many small changes
- Within each change scope, maximize independent work items (separate components, pages, test files)
- The implementation agent will spawn parallel teammates for independent tasks
- Sequential dependencies between tasks within a change reduce parallelism — minimize them
- Example: 5 independent React components = 5 parallel tasks, not 5 sequential tasks""")

    optional_text = "\n".join(sections)

    # Coverage section (digest mode)
    coverage_section = ""
    if coverage_info and coverage_info.strip():
        coverage_section = f"""

## Coverage Status (from digest)
{coverage_info}
Do NOT re-plan requirements that are already merged or running."""

    # Replan sections
    replan_section = ""
    if replan_ctx.get("completed"):
        cycle = replan_ctx.get("cycle", 1)
        completed = replan_ctx["completed"]
        replan_section += f"""

## IMPORTANT: Already Completed (cycle {cycle})
The following roadmap items have ALREADY been implemented and merged.
Roadmap items: {completed}

CRITICAL INSTRUCTIONS FOR REPLAN:
- DO NOT regenerate changes for any of these completed items
- You MUST advance to the NEXT phase/priority group in the spec
- If Phase/Priority 1 items are all completed, plan Phase/Priority 2 items
- Generate changes with NEW names (not the same names as completed changes)
- If no more phases remain in the spec, return an empty changes array: {{"changes": [], "phase_detected": "all done", "reasoning": "all phases completed"}}"""

    if replan_ctx.get("memory"):
        replan_section += f"""

## Orchestration History
Past operational events from previous cycles — use this to avoid repeating mistakes:
{replan_ctx['memory']}"""

    if replan_ctx.get("e2e_failures"):
        replan_section += f"""

## Phase-End E2E Test Failures
The previous phase's integrated E2E tests (Playwright) failed on main after all changes were merged.
These are integration bugs that individual change tests did not catch.
You MUST include fix changes for these failures in the next phase:

{replan_ctx['e2e_failures']}"""

    if replan_ctx.get("audit_gaps"):
        replan_section += f"""

## Post-Phase Audit Gaps
Post-phase audit found these implementation gaps — prioritize them in the next plan.
Create dedicated changes for each critical gap. Minor gaps may be folded into related changes.

{replan_ctx['audit_gaps']}"""

    if mode == "brief":
        return f"""You are a software architect decomposing a project brief into OpenSpec changes.

## Project Brief
{input_content}

## Existing Specs
{specs}

## Active Changes
{active_changes}
{optional_text}

## {test_infra_context}

## Task
Analyze the "Next" section of the brief and decompose it into concrete, implementable OpenSpec changes.

{_PLANNING_RULES}

Output ONLY valid JSON (no markdown, no explanation):
{_BRIEF_OUTPUT_JSON}"""

    # Spec/digest mode
    digest_section = ""
    if input_mode == "digest":
        digest_section = f"\n{_DIGEST_FIELDS}\n"

    output_json = _SPEC_OUTPUT_JSON_DIGEST if input_mode == "digest" else _SPEC_OUTPUT_JSON

    return f"""You are a software architect analyzing a project specification to plan the next batch of implementation work.

## Project Specification
{input_content}

## Existing OpenSpec Specs
{specs}

## Active Changes (already in progress)
{active_changes}
{optional_text}

## {test_infra_context}
{coverage_section}
{replan_section}

## Task
1. **Analyze the specification** — identify which items are completed (look for status markers: checkboxes, emoji, "done"/"implemented"/"kész"/"ready" text, strikethrough, progress tables) and which are pending. Also consider the "Already Completed" section above if present.
2. **Determine the next batch** — respect explicit phases, priorities, or numbered ordering in the document. Pick the first incomplete phase/priority group.
{phase_instruction}
3. **Decompose** the selected batch into concrete, implementable OpenSpec changes.

{_PLANNING_RULES}
{digest_section}
Output ONLY valid JSON (no markdown, no explanation):
{output_json}"""


# ─── Audit Prompt Template ────────────────────────────────────────────

_AUDIT_OUTPUT_JSON = """{
  "audit_result": "gaps_found|clean",
  "gaps": [
    {
      "id": "GAP-1",
      "description": "Feature or requirement that is missing or incomplete",
      "spec_reference": "Section or REQ-ID from the spec",
      "severity": "critical|minor",
      "suggested_scope": "Concrete description of what needs to be implemented"
    }
  ],
  "summary": "N critical gaps, M minor gaps found out of K spec sections"
}"""


def render_audit_prompt(
    spec_text: str = "",
    requirements: list | None = None,
    changes: list | None = None,
    coverage: str = "",
    mode: str = "spec",
) -> str:
    """Render post-phase audit prompt for spec-vs-implementation gap detection.

    Args:
        spec_text: Raw spec/brief text (used in spec mode)
        requirements: List of requirement dicts with id, title, brief (used in digest mode)
        changes: List of change dicts with name, scope, status, file_list
        coverage: Coverage data string (which REQ-IDs are merged/uncovered/failed)
        mode: "digest" for requirements.json mode, "spec" for raw spec mode
    """
    if requirements is None:
        requirements = []
    if changes is None:
        changes = []

    # Build changes section
    changes_text = ""
    if changes:
        change_lines = []
        for c in changes:
            status = c.get("status", "unknown")
            name = c.get("name", "unnamed")
            scope = c.get("scope", "")
            files = c.get("file_list", "")
            entry = f"### {name} (status: {status})\n**Scope:** {scope}"
            if files:
                entry += f"\n**Files changed:**\n{files}"
            change_lines.append(entry)
        changes_text = "\n\n".join(change_lines)

    # Coverage section (digest mode)
    coverage_section = ""
    if coverage and coverage.strip():
        coverage_section = f"""

## Coverage Status
{coverage}"""

    if mode == "digest" and requirements:
        # Digest mode: structured requirements
        req_lines = []
        for r in requirements:
            req_id = r.get("id", "")
            title = r.get("title", "")
            brief = r.get("brief", "")
            req_lines.append(f"- **{req_id}**: {title} — {brief}")
        req_text = "\n".join(req_lines)

        return f"""You are a quality auditor. Compare the input specification requirements against the completed implementation changes. Identify any features, requirements, or acceptance criteria that appear to be MISSING or INCOMPLETE.

## Requirements from Specification
{req_text}
{coverage_section}

## Completed Changes
{changes_text}

## Task
For each requirement, check whether the completed changes provide sufficient implementation evidence (matching scope descriptions and file lists). Flag requirements where:
1. No change covers the requirement at all (critical gap)
2. A change claims to cover it but the file list suggests incomplete implementation (minor gap)
3. The requirement was decomposed across changes but some aspect was missed (critical or minor depending on scope)

Do NOT flag requirements that are clearly covered by a change with matching scope and relevant files.

Output ONLY valid JSON (no markdown, no explanation):
{_AUDIT_OUTPUT_JSON}"""

    # Spec/brief mode: raw text comparison
    spec_text = _truncate(spec_text, 30000, "spec text")

    return f"""You are a quality auditor. Compare the input specification against the completed implementation changes. Identify any features, requirements, or acceptance criteria that appear to be MISSING or INCOMPLETE.

## Input Specification
{spec_text}

## Completed Changes
{changes_text}

## Task
For each section/feature in the specification, check whether the completed changes provide sufficient implementation evidence (matching scope descriptions and file lists). Flag features where:
1. No change covers the feature at all (critical gap)
2. A change claims to cover it but the file list suggests incomplete implementation (minor gap)
3. The feature was split across changes but some aspect was missed (critical or minor depending on scope)

Do NOT flag features that are clearly covered by a change with matching scope and relevant files.

Output ONLY valid JSON (no markdown, no explanation):
{_AUDIT_OUTPUT_JSON}"""
