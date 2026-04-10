# Change: design-compliance-gate

## Why

Agents implement UI code but sometimes ship it without applying the design system — missing Tailwind imports, forgotten shadcn components, ignored design tokens. Current gates catch code-level bugs (build, test, lint, review, spec_verify) but **NOTHING checks whether the rendered UI actually looks like the design**. Real examples from craftbrew runs:

1. **craftbrew-run-20260408**: admin-panel used hardcoded hex values (`text-[#78350F]`) instead of semantic tokens — worked visually but not sustainable
2. **craftbrew-run-20260409**: root `src/app/layout.tsx` missed `import "./globals.css"` — all `/admin/*` routes rendered with browser defaults (no Tailwind, no fonts, no cards). Tests PASSED because they only checked data-testids, not visual output. Only caught when user opened the screenshot viewer manually
3. **Gate gap**: review gate reviews CODE, not PIXELS. An agent can pass review with `className="bg-primary"` but the stylesheet is never loaded, so the pixel output is unstyled

We have Playwright screenshots from every E2E run (`screenshot: "on"` in config) — they're sitting on disk unused after the E2E gate passes. This is a missed opportunity: an LLM can look at those screenshots and answer "does this page match the design system?" in one call.

## What Changes

### 1. New gate: `design_compliance` — runs after E2E passes

Web-only gate (registered via web module's gate registry hook). Position: `after:e2e`. Only runs if:
- E2E gate passed
- E2E artifacts directory exists with ≥1 PNG screenshot
- `design-brief.md` OR `design-system.md` exists in the project

If any condition missing → gate SKIPPED (non-blocking, logs INFO).

### 2. Gate logic: LLM screenshot review via Claude vision

For each screenshot (or a sampled subset if >N):
- Load the screenshot as base64 data URL
- Build a prompt with:
  - The design tokens from `design-system.md` (colors, fonts, spacing)
  - The page's visual description from `design-brief.md` (if matched by filename)
  - The screenshot image
- Ask Claude: "Does this page apply the design system? Rate PASS/WARN/FAIL with 1-3 specific findings."
- Aggregate results across all screenshots

PASS = all screenshots compliant. WARN = minor issues (hardcoded colors, slight spacing drift). FAIL = major (unstyled browser defaults, missing theme, broken layout).

Gate result: PASS/WARN → gate passes, findings logged. FAIL → gate fails, findings attached to retry_context so the agent gets actionable feedback.

### 3. Sampling strategy to control cost

Large test suites can have 50+ screenshots. Sample strategy:
- Take at most N screenshots per gate run (config: `design_compliance_max_screenshots`, default 8)
- Prioritize: 1 from each unique test file, prefer post-action shots over initial loads
- Reuse a single Claude vision call with multiple image attachments (cheaper than N calls)

### 4. Config in orchestration.yaml

```yaml
design_compliance:
  enabled: true          # default: true if design files present
  model: sonnet          # vision-capable model
  max_screenshots: 8
  fail_on: major         # "major" | "any" — WARN threshold
  timeout: 300
```

### 5. Web dashboard: Design gate icon + findings view

Add `D` gate icon to GateBar.tsx alongside B/T/E/R/S. Click → show LLM findings with screenshot thumbnails (similar to review findings view).

## Impact

### Layer separation
- **Core (`lib/set_orch/`)**: NO changes. The gate definition is registered via `ProjectType.extra_gates()` hook (new ABC method if it doesn't exist).
- **Web module (`modules/web/set_project_web/`)**: adds `gates/design_compliance.py` with the LLM logic. Registers via `extra_gates()` return.
- **Core gate runner**: already iterates over registered gates, no changes needed.

### Files
- `modules/web/set_project_web/gates/design_compliance.py` (new)
- `modules/web/set_project_web/project_type.py` (add `extra_gates()` return)
- `lib/set_orch/profile_types.py` (add `extra_gates()` abstract method if missing)
- `lib/set_orch/verifier.py` (register plugin gates in pipeline assembly)
- `web/src/components/GateBar.tsx` (add D icon)
- `web/src/components/issues/DesignFindingsView.tsx` (new, optional)
- `modules/web/set_project_web/templates/nextjs/set/orchestration/config.yaml` (add design_compliance section)

### Deps
- Uses existing `run_claude_logged` for LLM call (vision models supported via `-p` with image input — verify Claude CLI capability)
- Screenshots already captured by existing playwright config

## Non-Goals

- **Not pixel-diffing** (no reference images, no Chromatic-style visual regression). This is semantic "does it look right" review, not pixel-exact comparison.
- **Not blocking by default** — starts as a WARN-level signal that agents can use; user can enable strict blocking via `fail_on: any`.
- **Not retroactive** — only runs after E2E passes, can't help if E2E never ran.
- **Not for non-web projects** — gate is registered only by the web module.
