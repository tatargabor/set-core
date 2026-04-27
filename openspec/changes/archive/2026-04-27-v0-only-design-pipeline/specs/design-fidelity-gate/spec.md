# Spec: Design Fidelity Gate (delta)

## ADDED Requirements

**IN SCOPE:** standalone integration gate in merge pipeline; headless build of agent worktree + v0 reference with shared fixtures; Playwright screenshot capture at 3 viewports; pixelmatch diff with configurable threshold; gate result reporting with diff artifacts; registration with gate-registry framework.

**OUT OF SCOPE:** AI-vision arbitration (deferred to v2); real-time visual regression during agent loop (gate-time only); multi-browser testing (Chromium-only in v1); animation timing comparison (animations disabled during capture).

### Requirement: Fidelity gate registered in gate registry

The web module SHALL register a `design-fidelity` gate in its gate registry. The gate runs as part of the merge pipeline (after build, before merge).

#### Scenario: Gate registration
- **WHEN** the WebProjectType is loaded
- **THEN** the `design-fidelity` gate is added to the integration gate registry with stage `post-build, pre-merge`
- **AND** the gate is enabled by default for projects where `detect_design_source() == "v0"`

#### Scenario: Gate disabled when no v0 source
- **WHEN** the project has no `v0-export/` directory
- **THEN** the `design-fidelity` gate is registered but skipped at runtime with status `skipped`
- **AND** the merge pipeline proceeds

### Requirement: Structural skeleton check (runs before screenshot capture)

Visual screenshot diff alone does not catch all design contract violations. An agent could inline a `<Header>` component into the layout (preserving pixels) but lose the v0's component decomposition; or skip a route entirely (page never rendered, so no screenshot to fail). The gate SHALL run a fast AST-level structural check FIRST, before any build or screenshot work, so cheap structural failures don't waste expensive render time.

#### Scenario: Route inventory match
- **WHEN** the gate runs
- **THEN** the gate enumerates `<agent-worktree>/app/**/page.tsx` paths AND `<v0-export>/app/**/page.tsx` paths
- **AND** the two sets MUST be equal (after normalizing route segment names)
- **AND** missing routes are reported as `missing-route: <path>` with `expected from v0-export but absent in agent build`
- **AND** extra routes are reported as `extra-route: <path>` with `agent created but not in v0-export`
- **AND** route mismatches block the gate before any build runs (status `skeleton-mismatch`)

#### Scenario: Shared layout files exist
- **WHEN** the gate runs the skeleton check
- **THEN** every file listed under `shared:` in `design-manifest.yaml` MUST exist in the agent worktree
- **AND** missing shared files are reported as `missing-shared-file: <path>` (e.g. `components/header.tsx` was extracted in v0 but agent inlined it back into `app/layout.tsx`)
- **AND** the check uses logical equivalence: a renamed file (e.g. `components/Header.tsx` → `components/site-header.tsx`) is NOT a violation if the manifest's name-mapping override allows it (see manifest `shared_aliases:` field)

#### Scenario: Component decomposition preserved
- **WHEN** the gate runs the skeleton check
- **THEN** for each shared component in `shared:`, the gate parses both v0's and agent's version with a TS AST parser
- **AND** verifies both export a default React component
- **AND** does NOT verify identical implementation (refactor allowed) — only that the component still EXISTS as a discrete file
- **AND** if a v0 shared component has been inlined into a parent file (no longer a separate export), reports `decomposition-collapsed: <component>`

#### Scenario: Skeleton check fails fast
- **WHEN** any skeleton mismatch is found
- **THEN** the gate emits `{status: "skeleton-mismatch", failures: [...]}`
- **AND** does NOT proceed to build or screenshot capture (saves minutes per failed gate)
- **AND** the agent's retry context lists the structural failures with concrete fix instructions ("add `app/csomagok/page.tsx`", "extract Header from app/layout.tsx into components/header.tsx")

#### Scenario: Per-scaffold tolerance for renames
- **GIVEN** scaffold author has a legitimate reason to rename a shared component (project naming convention)
- **WHEN** `design-manifest.yaml` declares `shared_aliases: {v0-export/components/header.tsx: components/site-header.tsx}`
- **THEN** the skeleton check treats the alias as equivalent
- **AND** rename is NOT a violation

#### Scenario: Manifest absent at gate time when design declared (HARD FAIL)
- **GIVEN** `detect_design_source() == "v0"` (project DECLARED v0 design source)
- **AND** `<project>/docs/design-manifest.yaml` is absent at gate execution time
- **WHEN** the skeleton check would normally read the manifest
- **THEN** the gate FAILS with status `manifest-missing` and message: `"design-manifest.yaml not found at <path>. The v0 design is declared but its manifest is not deployed — check runner deploy step (task 10.3) or re-run set-design-import. Merge blocked."`
- **AND** the gate does NOT proceed to build or screenshot
- **AND** the failure is logged at ERROR with the expected manifest path so ops can diagnose
- **RATIONALE** (per design D8): when design IS declared, missing artifacts are deployment bugs, not graceful-skip cases. Soft-failing here would let the merge ship with the wrong design context. To consciously override (emergency only), set `gates.design-fidelity.warn_only: true` in orchestration config.

### Requirement: Headless build with shared fixtures

The fidelity gate SHALL build BOTH the agent worktree and a fixture-substituted copy of `v0-export/` before screenshot capture. The "agent worktree" is the consumer project's worktree directory (the path returned by the orchestration engine's worktree manager) — NOT the set-core repo. The gate SHALL `cd` into that path before invoking pnpm.

#### Scenario: Build agent worktree (correct working directory)
- **WHEN** the gate runs
- **THEN** the gate resolves the worktree path by calling the engine's worktree manager API: `worktree_manager.get_worktree_path(change_name) -> Path` (the same API used by `set-list` and dispatcher)
- **AND** the gate `cd`s into that path (typically `~/.set-orch/worktrees/<change_name>/`)
- **AND** `pnpm install --frozen-lockfile && pnpm build` is executed there
- **AND** if `get_worktree_path` returns None or raises, the gate fails fast with status `worktree-path-unknown`
- **AND** if build fails, the gate reports failure status `build-failed-agent` and skips screenshot capture

#### Scenario: Build v0 reference with fixtures (in temp dir)
- **WHEN** the gate runs
- **THEN** `<project>/v0-export/` is copied to a unique temp directory (`<tmp>/v0-renderer-<uuid>/`)
- **AND** content fixtures from the consumer-project location (`<project>/.set-orch/v0-fixtures.yaml`, deployed by the runner from `<scaffold>/docs/content-fixtures.yaml`) are applied
- **AND** `pnpm install && pnpm build` runs in the temp copy

#### Scenario: v0 reference build fails when design declared (HARD FAIL)
- **GIVEN** `detect_design_source() == "v0"`
- **WHEN** `pnpm build` on the fixture-substituted v0 copy exits non-zero
- **THEN** the gate FAILS with status `reference-build-failed` and BLOCKS merge
- **AND** stderr captured + saved to gate-results
- **AND** the failure message names the v0-export source (URL+SHA from import) so the scaffold author knows where to fix
- **RATIONALE** (per design D8): a broken v0 reference means the design is broken. Shipping the agent's interpretation of broken design = shipping bugs. Override via `warn_only: true` if absolutely necessary.

#### Scenario: Fixtures missing when design declared (HARD FAIL)
- **GIVEN** `detect_design_source() == "v0"`
- **AND** the consumer project has no `<project>/.set-orch/v0-fixtures.yaml`
- **WHEN** the gate runs
- **THEN** the gate FAILS with status `fixtures-missing` and BLOCKS merge
- **AND** the failure message points to: (a) check the scaffold has `docs/content-fixtures.yaml`, (b) check the runner deploy step (task 10.3) ran successfully
- **RATIONALE** (per design D8): without fixtures, the screenshot diff would compare apples to oranges (HU agent vs English v0 placeholders) and produce false positives or false negatives. Either is silent breakage. Override via `warn_only: true`.

#### Scenario: Fixtures absent when design absent (graceful no-op)
- **GIVEN** `detect_design_source() == "none"` (project did NOT declare design source)
- **WHEN** the gate would run
- **THEN** the gate is SKIPPED with status `skipped-no-design-source` (existing behavior)
- **AND** fixtures presence/absence is irrelevant

### Requirement: Screenshot capture at three viewports

The gate SHALL capture screenshots of every route in the manifest at three viewports.

#### Scenario: Viewport set
- **WHEN** screenshots are captured
- **THEN** each route is captured at viewports: `1440x900` (desktop), `768x1024` (tablet), `375x667` (mobile)
- **AND** before each capture, Playwright SHALL `waitForLoadState("networkidle")` AND `waitForFunction(() => document.fonts.ready)`
- **AND** CSS animations SHALL be disabled via `prefers-reduced-motion: reduce` injection

#### Scenario: Routes covered
- **WHEN** the gate runs
- **THEN** every route listed in `design-manifest.yaml` SHALL be captured
- **AND** routes that fail to render in either build are reported as failure status `route-render-failed` with the URL

### Requirement: Pixel diff with configurable threshold

The gate SHALL compute pixel diff between agent and reference screenshots using `pixelmatch` (or equivalent) with route-level threshold configuration.

#### Scenario: Diff under threshold
- **GIVEN** route `/kavek` desktop diff is 0.8% of pixels different
- **AND** the configured threshold is 1.5%
- **WHEN** diff evaluation runs
- **THEN** the route passes
- **AND** diff metrics are logged at INFO level

#### Scenario: Diff exceeds threshold
- **GIVEN** route `/kavek` desktop diff is 3.2% of pixels different
- **AND** the threshold is 1.5%
- **WHEN** diff evaluation runs
- **THEN** the route fails
- **AND** the diff image is saved to `<gate-results-dir>/design-fidelity/<route>/desktop.diff.png`
- **AND** the agent and reference images are saved alongside as `agent.png` and `reference.png`

#### Scenario: Per-route threshold override
- **GIVEN** the manifest contains `routes: - path: /kavek, fidelity_threshold: 3.0`
- **WHEN** diff evaluation runs for `/kavek`
- **THEN** the per-route threshold (3.0%) is used instead of the global default (1.5%)

#### Scenario: Default threshold
- **WHEN** no threshold is configured
- **THEN** the gate uses default 1.5% per-region pixel diff
- **AND** an absolute floor of 200 pixels (small images don't fail on 1px diff)

### Requirement: Gate result reporting

The gate SHALL emit a structured result conforming to the gate-registry result schema.

#### Scenario: Pass result
- **WHEN** all routes pass diff
- **THEN** the gate emits `{status: "pass", checked_routes: <count>, max_diff_pct: <pct>}`
- **AND** the merge pipeline proceeds

#### Scenario: Fail result with diffs
- **WHEN** any route fails diff
- **THEN** the gate emits `{status: "fail", failed_routes: [<list>], diff_images_dir: <path>}`
- **AND** merge is blocked
- **AND** the agent's next iteration receives the failed routes + diff image paths in input.md retry context

### Requirement: Retry behavior

The gate SHALL retry once on transient failures before declaring final fail.

#### Scenario: Transient build retry
- **GIVEN** agent worktree build fails on first attempt with exit code 1
- **WHEN** the gate retries `pnpm install --frozen-lockfile && pnpm build` once
- **AND** the retry succeeds
- **THEN** the gate proceeds with screenshot capture

#### Scenario: Persistent failure
- **GIVEN** agent worktree build fails twice
- **WHEN** retry budget is exhausted
- **THEN** gate reports failure with status `build-failed-agent` and stderr captured

### Requirement: Warn-only mode — single explicit override

The gate SHALL support a `warn_only` config flag that downgrades blocking failures to warnings. This is the **single supported override** for fail-loud behavior (per design D8). Auto-warn-only or per-condition fallbacks SHALL NOT exist — explicit user acknowledgment is required.

#### Scenario: warn_only enabled
- **GIVEN** orchestration config sets `gates.design-fidelity.warn_only: true`
- **WHEN** the gate detects failures (any status: `skeleton-mismatch`, `manifest-missing`, `fixtures-missing`, `reference-build-failed`, `build-failed-agent`, route-render-failed, threshold-exceeded)
- **THEN** the gate emits status `pass` with all failures listed in result metadata
- **AND** merge proceeds
- **AND** an INFO log entry records ALL downgraded failures for human review on EVERY gate run (so the override does not silently persist)
- **AND** the log includes a reminder: `"warn_only: true is enabled — gate is in emergency override mode. Disable when underlying issue is fixed."`

#### Scenario: warn_only is the only override mechanism
- **WHEN** any condition that previously triggered auto-warn-only or graceful-skip is detected (missing fixtures, missing manifest, reference build failure)
- **AND** `warn_only` is NOT explicitly set to true
- **THEN** the gate FAILS (does not auto-degrade)
- **AND** there is NO other config flag, env var, or implicit fallback that downgrades these failures
