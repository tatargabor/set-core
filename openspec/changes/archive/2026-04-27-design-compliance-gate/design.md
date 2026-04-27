# Design: design-compliance-gate

## Current state

```
Gate pipeline (web project type):
  dep_install → build → test → e2e → scope_check → test_files → review → rules → spec_verify

After e2e passes:
  Screenshots sit in .playwright/screenshots/ or test-results/
  Agent never reviews them
  Review gate reads code text, not rendered pixels
  Merge happens → broken UI ships

Observed failure modes:
  - globals.css import missing → browser-default CSS, all tests pass
  - Hardcoded hex colors instead of design tokens → invisible drift
  - shadcn components bypassed in favor of plain <button>/<input> → style mismatch
  - Admin pages use entirely different design language than storefront
```

## New state

```
Gate pipeline (web project type):
  dep_install → build → test → e2e → design_compliance → scope_check → ...

design_compliance gate:
  1. Precondition check:
     - e2e gate result == "pass"
     - design-brief.md OR design-system.md exists in project root docs/
     - At least 1 PNG in test-results/**/*.png
     → If any missing: SKIP (log INFO, non-blocking)

  2. Collect screenshots (sampling):
     - Walk test-results/ recursively
     - Group by parent dir (= test file name)
     - Pick 1 most recent PNG per group
     - Cap at max_screenshots (default 8)
     - Prefer post-action (higher file timestamp) over initial-load

  3. Build review prompt:
     - Load design-system.md tokens (colors/fonts/spacing)
     - Load design-brief.md (per-page descriptions)
     - Build prompt:
       """
       Review these screenshots for design system compliance.
       Design tokens: <...>
       Per-page descriptions: <...>
       For each screenshot answer: PASS / WARN / FAIL
       If WARN or FAIL, give 1-3 specific findings (max 1 line each).
       Output format: JSON { screenshot, verdict, findings[] }
       """
     - Attach screenshots as image_url inputs (if supported) or base64

  4. Call Claude (vision model):
     - run_claude_logged(prompt, purpose="design_compliance",
                         model=config.model, images=paths, timeout=300)
     - Parse JSON response

  5. Aggregate result:
     - Any FAIL → gate FAIL (if fail_on=major or any)
     - Only WARN → gate PASS with findings logged
     - All PASS → gate PASS

  6. Persist findings:
     - Write to .set/gates/design_compliance_findings.jsonl
     - Expose in state.extras.design_findings for web dashboard
     - On FAIL: attach to retry_context for next agent pass
```

## Architectural decisions

### AD-1: Plugin gate, not core gate

**Why**: design_compliance is fundamentally web-specific (needs rendered pages, Playwright screenshots, visual design tokens). Putting it in core would leak web concepts into Layer 1.

**How**: extend `ProjectType` ABC with an `extra_gates()` method that returns `list[GateDefinition]`. The core `verifier.py` pipeline assembly merges core gates + profile gates.

```python
# lib/set_orch/profile_types.py
class ProjectType(ABC):
    def extra_gates(self) -> list[GateDefinition]:
        """Return plugin-specific gates to append to the pipeline."""
        return []

# modules/web/set_project_web/project_type.py
class WebProjectType(CoreProfile):
    def extra_gates(self) -> list[GateDefinition]:
        from .gates.design_compliance import execute_design_compliance_gate
        return [
            GateDefinition(
                "design_compliance",
                execute_design_compliance_gate,
                position="after:e2e",
                retry_counter="design",   # dedicated counter, not shared with verify
                extra_retries=3,            # default max; config.design_compliance.max_retries overrides
                result_fields=("design_compliance_result", "gate_design_compliance_ms"),
            ),
        ]
```

The `retry_counter` field is a new capability on `GateDefinition`. Existing gates use the default shared counter (`verify_retry_count`). Named counters let plugin gates have their own retry budget without interfering with core gate retries.

### AD-2: Non-blocking by default

**Why**: LLM vision review is probabilistic and can produce false positives. Breaking the pipeline on a WARN-level signal would be disruptive. Start as informational, let users opt-in to strict blocking.

**Config knob**: `design_compliance.fail_on`:
- `"any"` — WARN or FAIL both fail the gate (strict)
- `"major"` — only FAIL fails the gate (default, lenient)
- `"never"` — never fails, always informational

### AD-3: Sampling, not full coverage

**Why**: E2E suites can have 50+ screenshots. Feeding all to a vision model is expensive and slow. 8 well-chosen screenshots give a good signal.

**Algorithm**:
1. Walk `test-results/**/*.png`
2. Group by immediate parent directory (= test name)
3. For each group: pick the file with the **highest mtime** (= last action in test)
4. Sort groups by directory name, take first N (deterministic)
5. If <N groups: take all

This ensures coverage across different test files rather than 8 screenshots from the same test.

### AD-4: Single multi-image Claude call, not N calls

**Why**: LLM providers charge per request. Sending 8 images in one call costs 1 request instead of 8. Also produces a coherent review ("page X uses design tokens but page Y doesn't") rather than isolated per-page verdicts.

**Tradeoff**: larger context window. Claude Opus 4.6 has 1M context — 8 images (~500KB each base64) well within limits.

### AD-5: Reuse existing screenshot capture

**Why**: the web module's playwright.config.ts template already has `screenshot: "on"`. No new Playwright config needed.

**Assumption**: screenshots land in `test-results/` (Playwright default) OR `.playwright/screenshots/`. The gate must walk both.

## Risks

### R1: Claude vision model availability
The Claude CLI (`claude -p`) may not support image attachments in stdin mode. Need to verify before implementation — if not supported, fall back to base64-in-markdown which may waste tokens.

**Mitigation**: Task 1 is a spike to verify Claude CLI image support. If unavailable, drop the gate entirely or use the Anthropic SDK directly (requires API key handling).

### R2: LLM hallucination on verdicts
Model might call a correct page "unstyled" or miss actual issues. Test with 3-5 known-good and known-bad screenshots before shipping.

**Mitigation**: The `never` fail_on mode lets users run the gate as pure signal without blocking. Iterate on the prompt based on false positive rate.

### R3: Cost
At ~$3 per million input tokens (sonnet), 8 screenshots × ~100K tokens = ~$0.80 per gate run. At 10 changes × 3 retry cycles = $24 per orchestration run.

**Mitigation**: `max_screenshots` config, default 8 (not more). `fail_on: major` to avoid triggering retries cheaply. Skip gate entirely if no design files.

### R4: Screenshot path drift
Playwright versions changed default screenshot locations. Need to check current Playwright output path.

**Mitigation**: config key `design_compliance.screenshot_dirs: ["test-results", ".playwright/screenshots"]` with sensible defaults.
