## Context

The E2E gate in `modules/web/set_project_web/gates.py` has two distinct failure paths: (1) Playwright produces a per-test failure list (`_extract_e2e_failure_ids` returns non-empty) — the gate cites the failing tests; the agent has actionable context. (2) Playwright crashes before completion — `_extract_e2e_failure_ids` returns empty — the gate produces a generic "check the worktree for stack traces" message but does NOT include the actual stdout/stderr that contains the crash. The agent receives a prompt with no concrete error and spends a session reading trace ZIPs in `test-results/` to diagnose.

The diagnostic data already exists in the `e2e_output` string the gate has in scope. The fix is to inline a useful subset of it into `retry_context` rather than discarding it.

## Goals / Non-Goals

**Goals:**
- Agents receive an actionable error tail in their first iteration on the unparseable-failure path.
- Crash markers (`Error:`, `Traceback`, `webServer`, `Killed`, `OOM`, `assert`) are extracted regardless of whether they fall inside the tail window — single most-likely lines survive any truncation.
- Cap controls context bloat; configurable for projects with long startup banners.

**Non-Goals:**
- Modifying the parseable-failure-list path. When Playwright reports per-test fails, the existing logic is correct and untouched.
- Adding gate retry budget or changing classification.
- Surfacing tails for other gates — out of scope; build/test/smoke produce their own context.

## Decisions

### Decision 1: Append tail under a clearly-labeled heading, do not interleave with orientation

**Choice:** Build `retry_context` as `<existing orientation paragraph>\n\n[<self-heal suffix if any>\n\n]## Crash markers detected\n<lines>\n\n## Stdout/stderr tail (last N lines)\n<lines>`. The orientation paragraph stays as the first thing the agent reads; the new content is structurally separate.

**Why?** Agents and operators reading the prompt need to know what to focus on. Mixing the existing message with raw stdout would obscure both. Clear headings let the agent skim the orientation, then dive into markers, then the tail if needed.

### Decision 2: Crash-marker scan runs the FULL output, tail uses last N

**Choice:** Two passes over `e2e_output` — one collects marker lines from anywhere with their original line numbers (formatted `L<n>: <line>`), the other slices the trailing N lines. Combined into the two sections.

**Why?** A `webServer failed to start` message often appears early in stdout (lines 5-30) before hundreds of unrelated lines from healthcheck retries fill the rest. Tail-only would miss the actual cause. Marker-only would miss whatever crashed silently after a marker. Both passes together cover both shapes.

### Decision 3: N defaults to 80, configurable via existing `gate_overrides`

**Choice:** Default to 80 lines (≈3-5 KB). Override via `gate_overrides.e2e.failure_tail_lines` (operator can raise to 200 for projects with long banners).

**Why 80?** Empirically large enough to capture the failing test's stack trace + a few lines of context, small enough to avoid flooding the LLM context. Overrideable so projects with verbose webServer startup or long Playwright config dumps can extend.

### Decision 4: Helper function in gates.py, not in core

**Choice:** Add `_build_failure_tail(e2e_output: str, max_lines: int = 80) -> str` as a private helper in `modules/web/set_project_web/gates.py`. Do NOT promote to Layer 1.

**Why?** The marker list (`Error:`, `Traceback`, `webServer`, `Killed`, `OOM`, `assert`) is a heuristic tuned for Playwright + Next.js webServer crash patterns. Other profiles' E2E gates may use different markers. Keep the heuristic with the profile. If a similar pattern emerges elsewhere, extract later.

## Risks / Trade-offs

- **[Risk] Tail may include sensitive data (env vars, secrets) printed by Next.js / Playwright.** → Mitigation: the same data is already being captured in `e2e_output` and journaled. This change moves it from disk-only (where the agent must read a file) to retry_context (where the agent sees it directly). No new exposure surface.

- **[Trade-off] Larger retry_context payloads on crash paths.** → Acceptable: only fires on the unparseable-failure path, and even then capped at 80 lines (~3-5 KB). The retry-policy cache already coalesces identical contexts; the larger size is one-time per crash kind.

- **[Risk] Configurable cap could be set absurdly high and bloat context.** → Mitigation: document recommended range (40-200) in the spec; the gate code SHOULD clamp to a sane upper bound (suggestion: 500 lines hard cap, even if `gate_overrides` requests more).

## Open Questions

- Should the crash-marker list be configurable too (so a profile that uses a different runner can extend it)? Probably yes via a class constant on the executor closure, but defer until a concrete use case appears. Tasks pin this.
