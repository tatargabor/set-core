# Tasks: v0-only Design Pipeline

> **Atomic BREAKING change.** No feature flag, no parallel pipelines. Strict task ordering avoids broken intermediate states. Within a section, tasks are roughly parallel; between sections, complete the earlier section first.

## 1. Layer 1 — Core ABC additions and removals (must come first; non-breaking until callers updated)

- [x] 1.1 Add `detect_design_source(self, project_path: Path) -> str` abstract method to `ProjectType` in `lib/set_orch/profile_types.py`. Return type is plain `str` (not `Literal`) for forward-compat with future plugins. [REQ: profile-shall-expose-design-source-provider-methods]
- [x] 1.2 Add `copy_design_source_slice(self, change_name: str, scope: str, dest_dir: Path) -> list[Path]` abstract method to `ProjectType`. The dispatcher computes `dest_dir`; the profile uses `change_name` for logging/error messages. [REQ: profile-shall-expose-design-source-provider-methods]
- [x] 1.3 Add `get_design_dispatch_context(self, change_name: str, scope: str, project_path: Path) -> str` abstract method to `ProjectType`. The `change_name` parameter is REQUIRED so the returned markdown can reference the exact change directory. [REQ: profile-shall-expose-design-source-provider-methods]
- [x] 1.4 Implement default `"none"` returns + no-op behaviors in `NullProfile` and `CoreProfile` for the three new methods [REQ: profile-shall-expose-design-source-provider-methods]
- [x] 1.5 REMOVE legacy methods from `ProjectType` ABC and all profile implementations: `build_per_change_design`, `build_design_review_section`, the old-signature `get_design_dispatch_context(scope, snapshot_dir)`. Update `NullProfile`, `CoreProfile`, `WebProjectType`, and any test stubs. [REQ: removal-of-legacy-design-provider-methods]
- [x] 1.6 Update `lib/set_orch/dispatcher.py` to call the three new methods when building per-change input.md. Remove the inline Figma detection / brief-checking block at `dispatcher.py:2144-2158` and the `build_per_change_design` call path at `dispatcher.py:2176-2203`. [REQ: dispatcher-uses-design-source-provider-methods]
- [x] 1.7 Remove `design_snapshot_dir` parameter from `dispatch_change()` (`dispatcher.py:1868`). Update the function body to not pass it through. [REQ: design-context-injected-into-agent-input]
- [x] 1.8 Remove `design_snapshot_dir` parameter from `dispatch_ready_changes()` and update all engine call sites: `engine.py:1542, 1630, 2838, 2975`. [REQ: design-context-injected-into-agent-input]
- [x] 1.9 Remove `design_snapshot_dir` parameter from CLI call sites: `cli.py:584, 599, 748, 767`. [REQ: design-context-injected-into-agent-input]
- [x] 1.10 Add unit test verifying `lib/set_orch/` contains zero `import` references to v0-specific modules (Layer 1 abstraction guard) [REQ: layer-1-has-no-v0-references]
- [x] 1.11 Add unit test verifying removed legacy methods are absent from ABC and all profiles (catches regression) [REQ: removal-of-legacy-design-provider-methods]

> **Note**: removal of `design_snapshot_dir` from verifier call sites (`verifier.py:1392, 2707, 3502`) is deferred to **task 7.10** because verifier still references the inline `_dp.build_design_review_section` call until task 7.1 lands.

## 2. Layer 2 — Web module v0 importer

- [x] 2.1 Create `modules/web/set_project_web/v0_importer.py` with `import_v0_zip(source, scaffold, force=False)` function [REQ: set-design-import-cli]
- [x] 2.2 Implement v0 export structure validation (App Router, components/ui/, package.json, globals.css) with clear error messages [REQ: v0-export-structure-validation]
- [x] 2.3 Implement globals.css sync from v0-export to `<scaffold>/shadcn/globals.css` (overwrite without prompt) [REQ: globalscss-sync-to-scaffold]
- [x] 2.4 Implement idempotent re-import: clean removal of previous `v0-export/` before extraction when `--force` is passed [REQ: idempotent-re-import]
- [x] 2.5 Create `modules/web/set_project_web/v0_manifest.py` with `generate_manifest_from_tree(v0_export_path)` function. Output path: `<scaffold>/docs/design-manifest.yaml`. Same path convention applies after runner deploys to consumer: `<project>/docs/design-manifest.yaml`. [REQ: manifest-auto-generation]
- [x] 2.6 Implement App Router route detection (recursive `app/**/page.tsx` scan with route segment derivation) [REQ: manifest-auto-generation]
- [x] 2.7 Implement transitive import-graph traversal to populate `component_deps` per route [REQ: manifest-auto-generation]
- [x] 2.8 Derive `scope_keywords` per route from URL segments + first H1 in page (lowercased, kebab-cased, deduplicated) [REQ: manifest-auto-generation]
- [x] 2.9 Detect shared files (components/ui/**, header.tsx, footer.tsx, app/layout.tsx, globals.css) and place under `shared:` key [REQ: manifest-auto-generation]
- [x] 2.10 Implement manual override preservation: parse existing manifest, retain lines marked `# manual` across regeneration [REQ: manifest-auto-generation]
- [x] 2.11 Implement scope-keyword collision detection: warn on duplicate keywords across routes; ERROR on identical keyword lists across routes [REQ: scope-keyword-collision-detection]
- [x] 2.12 Handle `--regenerate-manifest` with no existing file: generate fresh, no error [REQ: manifest-auto-generation]
- [x] 2.13 Create `modules/web/bin/set-design-import` CLI entry point with `--git`, `--ref`, `--source`, `--scaffold`, `--force`, `--regenerate-manifest` flags. `--git` and `--source` are mutually exclusive. When neither is passed, read source from `<scaffold>/scaffold.yaml` `design_source` block. [REQ: set-design-import-cli-source-modes]
- [x] 2.13a Implement git source mode: invoke system `git clone` (or `git fetch` + checkout on cache hit). Delegate ALL auth to system git — no framework auth code. Use partial clone (`--no-tags --filter=blob:none`) for speed. [REQ: git-source-mode-behavior]
- [x] 2.13b Implement ref resolution: branch / tag / commit SHA all valid; record resolved SHA in success summary; warn if ref points to non-tip commit on a moving branch. Default `main` if no ref given. [REQ: git-source-mode-behavior]
- [x] 2.13c Implement clone caching at `~/.cache/set-orch/v0-clones/<sha256-of-url>/`. URL hashed (not raw) so credentials in URLs don't leak via cache directory names. LRU prune at 5 entries. [REQ: clone-caching]
- [x] 2.13d Implement materialization: copy cache contents to `<scaffold>/v0-export/`, exclude `.git/` directory (scaffold's v0-export is gitignored). [REQ: clone-caching]
- [x] 2.13e Implement actionable auth-failure error: on `git clone` exit code 128, name the URL + list auth options (SSH agent, GITHUB_TOKEN, deploy key, credential helper) + point to docs. [REQ: git-source-mode-behavior]
- [x] 2.13f Parse `scaffold.yaml` `design_source` block (types: `v0-git`, `v0-zip`); error clearly when block missing and CLI run without flags; warn on embedded credentials in repo URL. [REQ: scaffoldyaml-design-source-schema]
- [x] 2.14 Wire the CLI into `modules/web/pyproject.toml` console_scripts so `pip install -e modules/web` exposes the binary [REQ: set-design-import-cli]
- [x] 2.15 Unit tests for v0_importer: valid ZIP, missing app/, missing globals.css, missing components/ui/, malformed package.json [REQ: v0-export-structure-validation]
- [x] 2.16 Unit tests for v0_manifest: simple route, nested route, dynamic route `[slug]`, route group `(group)`, manual override preservation, scope-keyword collision (warn + error variants), --regenerate-manifest with no file, **shared_aliases byte-for-byte preservation across --regenerate-manifest** [REQ: manifest-auto-generation]
- [x] 2.17 Unit tests for git source mode: public HTTPS clone, ref=branch / tag / SHA resolution, cache hit reuses local repo, materialization excludes .git/, mutual exclusion with --source flag [REQ: git-source-mode-behavior]
- [x] 2.18 Integration test for git source mode (uses public test fixture repo, real `git clone` — skipped in offline CI) [REQ: git-source-mode-behavior]
- [x] 2.19 Unit tests for cache: first-clone populates, cache hit reuses, URL hashed (raw URL not in dir name), LRU prune at 5 entries [REQ: clone-caching]

## 3. Layer 2 — Web module design-source provider

- [x] 3.1 Implement `WebProjectType.detect_design_source(project_path)` returning `"v0"` when `<project_path>/v0-export/` exists, else `"none"` [REQ: webprojecttype-implements-design-source-provider-methods]
- [x] 3.2 Implement `WebProjectType.copy_design_source_slice(change_name, scope, dest)` using v0_manifest scope-keyword matcher. Reads manifest from `<project_path>/docs/design-manifest.yaml`. [REQ: webprojecttype-implements-design-source-provider-methods]
- [x] 3.3 Implement scope-keyword substring matching against manifest route `scope_keywords` lists [REQ: scope-keyword-matching-against-manifest]
- [x] 3.4 Always include `shared:` files in every slice; flag missing shared files as ERROR (manifest broken) [REQ: per-change-design-source-directory-population]
- [x] 3.5 Clean stale `dest/` before repopulation (retry-safe) [REQ: per-change-design-source-directory-population]
- [x] 3.6 Implement `WebProjectType.get_design_dispatch_context(change_name, scope, project_path)` returning markdown block with file list + token quick-reference; the block's directory pointer uses `change_name` (not a placeholder) [REQ: agent-dispatch-context-references-design-source]
- [x] 3.7 Implement token extraction from `<project_path>/shadcn/globals.css` (or fallback `<project_path>/v0-export/app/globals.css`) parsing `:root { --foo: ... }` declarations [REQ: token-extraction-from-synced-globalscss]
- [x] 3.8 Enforce 200-line cap on dispatch context block (file list + tokens, NOT TSX content) [REQ: agent-dispatch-context-references-design-source]
- [x] 3.9 Unit tests for scope matching: single route match, multi-route match, no-match fallback to shared-only [REQ: scope-keyword-matching-against-manifest]
- [x] 3.10 Integration test: WebProjectType end-to-end populates per-change design-source/ from a sample manifest + v0-export fixture [REQ: webprojecttype-implements-design-source-provider-methods]

## 4. Layer 2 — Fixture renderer (v0-fixture-renderer)

- [x] 4.1 Create `modules/web/set_project_web/v0_renderer.py` with `render_v0_with_fixtures(v0_export, fixtures, output_temp)` function [REQ: headless-build-of-fixture-substituted-copy]
- [x] 4.2 Define `content-fixtures.yaml` schema (string_replacements, mock_data, data_imports, language). Authored at `<scaffold>/docs/content-fixtures.yaml`; deployed by runner to `<project>/.set-orch/v0-fixtures.yaml`. [REQ: content-fixturesyaml-format]
- [x] 4.3 Implement string substitution across all `.tsx`, `.ts`, `.jsx`, `.js` files in temp copy (preserve original v0-export) [REQ: placeholder-string-substitution]
- [x] 4.4 Implement mock data file injection (data_imports → write fixture content to target paths in temp copy) [REQ: mock-data-layer-injection]
- [x] 4.5 Implement headless build sequence: `pnpm install --frozen-lockfile && pnpm build && pnpm start` with port allocation [REQ: headless-build-of-fixture-substituted-copy]
- [x] 4.6 Implement server health-check (HTTP 200 on `/` within 30s timeout) before returning base URL [REQ: headless-build-of-fixture-substituted-copy]
- [x] 4.7 Implement server cleanup (SIGTERM → 5s → SIGKILL) on success and error paths [REQ: headless-build-of-fixture-substituted-copy]
- [x] 4.8 Implement node_modules cache: hash pnpm-lock.yaml; on cache hit, COPY (with `cp --reflink=auto` on Linux) from cache — DO NOT symlink. Cache treated as read-only during gate runs. LRU pruning keeps last 3 hashes per scaffold. [REQ: caching-of-pnpm-install-layer]
- [x] 4.9 Implement concurrent-safe temp dir + port allocation (uuid-based temp path, free-port range scanner). Verify two simultaneous gate runs do NOT corrupt each other's `node_modules`. [REQ: idempotent-and-concurrent-safe]
- [x] 4.10 Unit tests: substitution with single match, multiple matches, zero matches (warn-only), mock data injection [REQ: placeholder-string-substitution]
- [x] 4.11 Integration test: render craftbrew v0-export with HU fixtures end-to-end, capture homepage URL [REQ: headless-build-of-fixture-substituted-copy]
- [x] 4.12 Concurrency test: two `render_v0_with_fixtures` calls in parallel; both succeed, neither corrupts the cache [REQ: caching-of-pnpm-install-layer]

## 5. Layer 2 — Design fidelity gate

- [x] 5.1 Create `modules/web/set_project_web/v0_fidelity_gate.py` implementing the gate runner [REQ: fidelity-gate-registered-in-gate-registry]
- [x] 5.2 Register `design-fidelity` gate in web module's gate registry at `post-build, pre-merge` stage [REQ: fidelity-gate-registered-in-gate-registry]
- [x] 5.3 Implement skip behavior when `detect_design_source() != "v0"` [REQ: fidelity-gate-registered-in-gate-registry]
- [x] 5.4 Implement working-directory resolution: call `worktree_manager.get_worktree_path(change_name) -> Path` (same API used by `set-list` and dispatcher), then `cd` into the returned path. Fail fast with status `worktree-path-unknown` if the API returns None or raises. [REQ: headless-build-with-shared-fixtures]
- [x] 5.5 Implement Playwright screenshot capture across 3 viewports (1440x900, 768x1024, 375x667) for every manifest route [REQ: screenshot-capture-at-three-viewports]
- [x] 5.6 Inject `prefers-reduced-motion: reduce` + wait for `networkidle` and `document.fonts.ready` before each capture [REQ: screenshot-capture-at-three-viewports]
- [x] 5.7 Implement pixelmatch diff with default 1.5% threshold + 200px absolute floor [REQ: pixel-diff-with-configurable-threshold]
- [x] 5.8 Support per-route threshold override from `design-manifest.yaml` (`fidelity_threshold` field per route) [REQ: pixel-diff-with-configurable-threshold]
- [x] 5.9 Save failure artifacts: agent.png, reference.png, diff.png to `<gate-results>/design-fidelity/<route>/<viewport>/` [REQ: pixel-diff-with-configurable-threshold]
- [x] 5.10 Implement gate-results retention policy: cleanup screenshots from gate runs older than N days (default 7) to prevent storage growth [REQ: pixel-diff-with-configurable-threshold]
- [x] 5.11 Emit gate result schema: `{status, checked_routes, max_diff_pct, failed_routes, diff_images_dir}` [REQ: gate-result-reporting]
- [x] 5.12 Implement build failure handling: agent-build-failed (blocks merge), reference-build-failed (does NOT block merge) [REQ: headless-build-with-shared-fixtures]
- [x] 5.13 Implement single retry on transient build failure [REQ: retry-behavior]
- [x] 5.14 Implement `warn_only: true` config flag (downgrades fail to warn, merge proceeds) [REQ: warn-only-mode-for-emergency-mitigation]
- [x] 5.15 Implement fail-loud per design D8: missing manifest, missing fixtures, reference build failure all FAIL the gate when `detect_design_source==v0` (NO auto-warn-only fallback). The single explicit override is `gates.design-fidelity.warn_only: true` config flag. [REQ: warn-only-mode-single-explicit-override]
- [x] 5.15a Implement INFO logging on every gate run when `warn_only` is true: full list of downgraded failures + reminder to disable when underlying issue is fixed (so override doesn't silently persist) [REQ: warn-only-mode-single-explicit-override]
- [x] 5.16 Inject failed-routes + diff image paths into agent retry context (next iteration's input.md) [REQ: gate-result-reporting]
- [x] 5.17 Unit tests: threshold pass, threshold fail, per-route override, warn_only mode, missing-fixtures auto-warn [REQ: pixel-diff-with-configurable-threshold]
- [x] 5.18 Integration test: deliberate className change in agent worktree triggers gate failure [REQ: gate-result-reporting]

## 6. Layer 2 — WebProjectType integration

- [x] 6.1 Update `modules/web/set_project_web/project_type.py` to register `design-fidelity` gate when WebProjectType is loaded [REQ: webprojecttype-registers-design-fidelity-gate]
- [x] 6.2 Wire WebProjectType to use v0_manifest, v0_renderer, v0_fidelity_gate modules [REQ: webprojecttype-implements-design-source-provider-methods]
- [x] 6.3 Add WebProjectType test suite verifying all three new ABC overrides work end-to-end [REQ: webprojecttype-implements-design-source-provider-methods]

## 7. Removals — Figma pipeline (BREAKING; ordered to avoid broken-import window)

> **Ordering invariant**: each numbered task in this section is a single commit. Earlier tasks must land before later ones because deletions cascade.

- [x] 7.1 In a single commit: remove inline design compliance section from `lib/set_orch/verifier.py` (lines ~1392-1418, the `_dp.build_design_review_section` call block) AND remove the `_dp` import statement at the top of `verifier.py`. [REQ: design-compliance-section-in-code-review]
- [x] 7.2 Remove the now-orphaned design compliance call sites elsewhere in verifier (search `verifier.py` for any other reference to `design_parser` / `_dp`). [REQ: design-compliance-section-in-code-review]
- [x] 7.3 Delete `lib/set_orch/design_parser.py` (MakeParser + DesignParser base + dataclasses). REQUIRES 7.1+7.2 to be merged first. [REQ: req-make-parse-parse-make-files-into-structured-design-systemmd]
- [x] 7.4 Delete `lib/design/fetcher.py` (Figma MCP client). [REQ: snapshot-caching-in-state-directory]
- [x] 7.5 Remove Figma-specific functions from `lib/design/bridge.sh`: `fetch_design_snapshot`, Figma URL extraction, `design_sources_for_dispatch` (figma-raw scanning), `design_brief_for_dispatch`, alias-match layer, stem-match layer. Remove `_DESIGN_BRIEF_ALIASES` array and `DESIGN_BRIEF_ALIASES_FILE` env var support. [REQ: design-context-extraction-for-dispatch]
- [x] 7.6 Delete `bin/set-design-sync` CLI [REQ: req-make-cli-cli-interface]
- [x] 7.7 Remove or skip tests targeting deleted modules; ensure no test imports surviving [REQ: req-make-parse-parse-make-files-into-structured-design-systemmd]
- [x] 7.8 Remove Figma URL field handling from `orchestration.yaml` parser; log DEBUG when stale field present [REQ: design-context-extraction-for-dispatch]
- [x] 7.9 Run full unit test suite + import-time smoke (`python -c "import lib.set_orch.dispatcher"`) on each commit in this section to catch broken-import regressions [REQ: design-compliance-section-in-code-review]
- [x] 7.10 Remove `design_snapshot_dir` parameter from verifier call sites: `verifier.py:1392, 2707, 3502`. REQUIRES 7.1 to be merged first (verifier no longer references the design parser). [REQ: design-context-injected-into-agent-input]

## 7b. Layer 2 — v0 quality validator (Gap C)

- [x] 7b.1 Create `modules/web/set_project_web/v0_validator.py` with a `validate_v0_export(path) -> ValidationReport` function [REQ: v0-template-quality-validation]
- [x] 7b.2 Implement TypeScript type-check via `npx tsc --noEmit` (uses v0's tsconfig.json); errors collected, non-blocking by default, blocking with `--strict` flag [REQ: v0-template-quality-validation]
- [x] 7b.3 Implement build smoke test via `pnpm install --frozen-lockfile && pnpm build`; failure is BLOCKING; stderr captured; skippable with `--no-build-check` flag [REQ: v0-template-quality-validation]
- [x] 7b.4 Implement component naming consistency check (lowercase + token-similarity heuristic groups similar names); report under "Naming Inconsistencies", non-blocking [REQ: v0-template-quality-validation]
- [x] 7b.5 Implement navigation link integrity check: scan every `<Link href="...">` and `router.push(...)`, verify destination route exists; broken links + orphan pages reported under separate sections; BLOCKING by default; overridable with `--ignore-navigation` flag [REQ: v0-template-quality-validation]
- [x] 7b.6 Implement variant coverage check (detect state variants in shared components, flag if some pages use them but not others); report under "Variant Coverage Gaps", NON-BLOCKING [REQ: v0-template-quality-validation]
- [x] 7b.7 Implement shadcn primitive usage consistency check (count shadcn vs raw HTML for similar concepts); report under "shadcn Consistency", NON-BLOCKING [REQ: v0-template-quality-validation]
- [x] 7b.8 Generate `<scaffold>/docs/v0-import-report.md`: grouped by severity (Errors / Warnings / Info), summary counts, source URL/SHA recorded, timestamp [REQ: v0-template-quality-validation]
- [x] 7b.9 Hard fail-fast on BLOCKING issue (build fail, broken navigation by default, --strict type errors): importer exits non-zero with report path + one-line summary [REQ: v0-template-quality-validation]
- [x] 7b.10 Wire validator into `set-design-import` flow: runs after extraction/clone, before manifest generation [REQ: v0-template-quality-validation]
- [x] 7b.11 Add CLI flags: `--strict`, `--no-build-check`, `--ignore-navigation`, `--strict-quality` (last promotes ALL warnings to blocking errors) [REQ: v0-template-quality-validation]
- [x] 7b.12 Unit tests: each validator individually (tsc fail, build fail, broken link, orphan page, naming inconsistency, variant gap), report generation [REQ: v0-template-quality-validation]
- [x] 7b.13 Integration test: deliberately craft a v0-export fixture with known issues (broken link, type error), verify validator catches them and report contains expected sections [REQ: v0-template-quality-validation]

## 7c. Layer 2 — Skeleton fidelity check (Gap A) — extends design-fidelity-gate

- [x] 7c.1 In `v0_fidelity_gate.py`, add `run_skeleton_check(agent_worktree, v0_export, manifest)` function that runs BEFORE build/screenshot [REQ: structural-skeleton-check-runs-before-screenshot-capture]
- [x] 7c.2 Implement route inventory diff: enumerate `app/**/page.tsx` in both worktrees; compute set difference; report `missing-route` and `extra-route` [REQ: structural-skeleton-check-runs-before-screenshot-capture]
- [x] 7c.3 Implement shared layout file existence check against manifest `shared:` list; report `missing-shared-file` for inlined components [REQ: structural-skeleton-check-runs-before-screenshot-capture]
- [x] 7c.4 Implement component decomposition check via TS AST parser (verify shared components remain discrete file exports); report `decomposition-collapsed` [REQ: structural-skeleton-check-runs-before-screenshot-capture]
- [x] 7c.5 Implement manifest `shared_aliases` field support (per-scaffold rename tolerance); skip violations matching aliases [REQ: structural-skeleton-check-runs-before-screenshot-capture]
- [x] 7c.6 Wire skeleton check FIRST in gate sequence: emit `{status: "skeleton-mismatch", failures: [...]}` and exit before build/screenshot if any mismatch [REQ: structural-skeleton-check-runs-before-screenshot-capture]
- [x] 7c.7 Inject failed-skeleton items into agent retry context with concrete fix instructions [REQ: structural-skeleton-check-runs-before-screenshot-capture]
- [x] 7c.8 Unit tests: route diff (match, missing, extra), shared file inline detection, component decomposition collapse detection, alias tolerance [REQ: structural-skeleton-check-runs-before-screenshot-capture]
- [x] 7c.9 Integration test: deliberately delete a route from agent worktree, verify gate fails with `missing-route` BEFORE attempting any screenshot [REQ: structural-skeleton-check-runs-before-screenshot-capture]

## 7d. Decompose ↔ design-manifest binding (Gap B)

> **Ordering invariant**: tasks 7d.1–7d.5 (skill update) MUST NOT be committed until 7d.6–7d.9 are complete. A decompose run with the new skill but old `validate_plan_design_coverage` would produce unvalidated plans that the dispatcher then rejects mid-flight. Land Layer 1/2 changes first; flip the skill last.

- [x] 7d.6 Add new ABC method to `ProjectType` in `lib/set_orch/profile_types.py`: `validate_plan_design_coverage(self, plan: dict, project_path: Path) -> list[str]` — returns list of violation messages (empty = OK). Default impl returns `[]` (no design awareness). [REQ: manifest-coverage-validation]
- [x] 7d.7 Update `validate_plan()` in `lib/set_orch/planner.py` (existing function around line 288): after existing checks, call `profile.validate_plan_design_coverage(plan, project_path)` and append violations to the result. Layer 1 stays manifest-agnostic — it just orchestrates the call. [REQ: manifest-coverage-validation]
- [x] 7d.8 Implement `WebProjectType.validate_plan_design_coverage` in `modules/web/set_project_web/project_type.py`: read `<project_path>/docs/design-manifest.yaml`; check opt-in trigger (any change has non-empty `design_routes` OR plan has `deferred_design_routes[]`); if not triggered, return `[]`; if triggered, enforce route coverage rule; return list of violations. [REQ: manifest-coverage-validation]
- [x] 7d.9 Update dispatcher in `lib/set_orch/dispatcher.py`: when computing slice, pass change's `design_routes` from plan to `profile.copy_design_source_slice` via a NEW typed kwarg `design_routes: list[str] | None` (do NOT overload the existing `scope` parameter — that would silently break scope-keyword fallback for old plans). Layer 1 doesn't interpret the value, just forwards it. [REQ: dispatcher-prefers-explicit-design-routes-over-scope-keyword-matching]
- [x] 7d.10 Web module: `WebProjectType.copy_design_source_slice` accepts an optional `design_routes` kwarg (typed `list[str] | None`); when non-empty, looks up exact route paths in manifest; falls back to scope-keyword matching when `None` or `[]`. [REQ: dispatcher-prefers-explicit-design-routes-over-scope-keyword-matching]
- [x] 7d.11 Web module: error clearly when `design_routes` references a route absent from manifest (`"design_route /sajto not found in manifest. Plan stale or manifest changed; regenerate plan."`) [REQ: dispatcher-prefers-explicit-design-routes-over-scope-keyword-matching]
- [x] 7d.1 Update `.claude/skills/set/decompose/SKILL.md`: add Step 2b "Read design-manifest.yaml" (after existing Step 2 project-context discovery). DEFERRED until 7d.6-7d.9 complete. [REQ: decompose-skill-instructs-planner-agent-on-design-awareness]
- [x] 7d.2 Update SKILL.md plan schema: add `design_routes: list[str]` per change AND top-level `deferred_design_routes: [{route, reason}]`. DEFERRED until 7d.6-7d.9 complete. [REQ: per-change-explicit-route-binding]
- [x] 7d.3 Update SKILL.md instructions: planner MUST map every manifest route to either a change's `design_routes` OR `deferred_design_routes`. DEFERRED until 7d.6-7d.9 complete. [REQ: manifest-coverage-validation]
- [x] 7d.4 Update SKILL.md: planner emits `design_route_map` debug section in plan reasoning; flags spec ↔ manifest gaps as `design_gap` ambiguities. DEFERRED until 7d.6-7d.9 complete. [REQ: decompose-skill-instructs-planner-agent-on-design-awareness]
- [x] 7d.5 Replace existing Step 6 ("Check for design tool" — Figma-oriented) with the new manifest-aware approach. DEFERRED until 7d.6-7d.9 complete. [REQ: decompose-skill-reads-design-manifestyaml]
- [x] 7d.12 Decompose graceful degradation: when no `design-manifest.yaml` exists, skill proceeds with existing spec-only logic + INFO log [REQ: decompose-skill-reads-design-manifestyaml]
- [x] 7d.13 Unit tests: validate_plan_design_coverage opt-in trigger (legacy plan skipped, design-aware plan enforced); rejects unaccounted route, rejects multi-assigned route, accepts deferred route with reason [REQ: manifest-coverage-validation]
- [x] 7d.14 Integration test: full decompose run on a spec + manifest pair, verify plan has `design_routes` per change AND coverage is complete; run again on a legacy plan to confirm graceful skip [REQ: manifest-coverage-validation]

## 8. Templates and rules

- [x] 8.1 Rewrite `templates/core/rules/design-bridge.md` for v0-only model: design-source/ as truth, refactor policy (allowed vs forbidden), aria-only safe vs `<span class="sr-only">` flagged, gate-as-contract. Replace ALL existing Figma / .make / design-snapshot references in this file. [REQ: design-bridge-rule-for-agents]
- [x] 8.2 Document design context source priority (v0 > globals.css tokens > none) in the rule [REQ: design-context-source-priority]
- [x] 8.3 Add `## Design Vibe Notes (non-authoritative)` template section pattern (used when scaffold ships an optional brief) [REQ: design-context-source-priority]
- [x] 8.4 Document the no-design-source fallback in the rule: agent uses project shadcn/ui defaults, does not invent custom variants [REQ: design-context-source-priority]

## 9. Scaffold migration — craftbrew (must complete before Section 14 E2E)

- [x] 9.1 Update `tests/e2e/scaffolds/craftbrew/scaffold.yaml` to add `design_source` block: `type: v0-git`, `repo: https://github.com/tatargabor/v0-craftbrew-e-commerce-design.git`, `ref: main`. Add `v0-export/` to scaffold's `.gitignore`. [REQ: scaffoldyaml-design-source-schema]
- [x] 9.2 Generate craftbrew design in v0.app using `docs/v0-prompts.md` and push to GitHub via v0's "Push to GitHub" feature (manual, scaffold author task — already done as `https://github.com/tatargabor/v0-craftbrew-e-commerce-design`). PREREQUISITE for Section 14. [REQ: set-design-import-cli-source-modes]
- [x] 9.3 Run `set-design-import --scaffold tests/e2e/scaffolds/craftbrew` (source resolved from scaffold.yaml) to materialize v0-export/ + manifest. PREREQUISITE for Section 14. [REQ: set-design-import-cli-source-modes]
- [x] 9.4 Author `tests/e2e/scaffolds/craftbrew/docs/content-fixtures.yaml` with HU placeholder substitutions + product/story fixtures. Note: if v0 prompts already produced HU copy directly, fixtures may only need mock data injection (no string replacements). PREREQUISITE for Section 14. [REQ: content-fixturesyaml-format]
- [x] 9.5 Hand-edit `design-manifest.yaml` to add manual scope_keyword overrides where auto-generation is insufficient (mark with `# manual`); resolve any collision warnings from the importer [REQ: scope-keyword-collision-detection]
- [x] 9.6 Delete legacy files from craftbrew scaffold: `docs/design.make`, `docs/design-system.md`, `docs/design-brief-aliases.txt` [REQ: req-make-format-design-systemmd-output-format]
- [x] 9.7 Reduce or rewrite `docs/design-brief.md` to non-authoritative vibe notes only (or remove if not needed) [REQ: design-context-source-priority]

## 10. Runner updates

- [x] 10.1 Update `tests/e2e/runners/run-craftbrew.sh` to remove `set-design-sync` step and Figma URL extraction [REQ: req-make-cli-cli-interface]
- [x] 10.2 Add validation/materialize step: runner runs `set-design-import --scaffold <scaffold>` BEFORE deploy if scaffold.yaml has a `design_source` block AND `<scaffold>/v0-export/` is empty/missing. Fail fast if `set-design-import` fails (auth, network, missing source). After this step, both `v0-export/` and `docs/design-manifest.yaml` must exist in scaffold. [REQ: set-design-import-cli-source-modes]
- [x] 10.3 Add deploy step: runner copies `<scaffold>/docs/content-fixtures.yaml` → `<project>/.set-orch/v0-fixtures.yaml` AND `<scaffold>/docs/design-manifest.yaml` → `<project>/docs/design-manifest.yaml` [REQ: content-fixturesyaml-format]
- [x] 10.4 Add deploy step: runner copies materialized `<scaffold>/v0-export/` → `<project>/v0-export/` (the consumer needs the actual v0 files for the fidelity gate's reference render). Note: scaffold's v0-export/ is gitignored locally; the runner re-materializes it from git/ZIP source on every fresh run. [REQ: set-design-import-cli-source-modes]
- [x] 10.5 Apply same updates to other consumer runners that referenced design-sync (`run-minishop.sh`, `run-micro-web.sh` if applicable) [REQ: req-make-cli-cli-interface]

## 11. Removed-spec cleanup

- [x] 11.1 Delete `openspec/specs/design-make-parser/` after archive [REQ: req-make-parse-parse-make-files-into-structured-design-systemmd]
- [x] 11.2 Delete `openspec/specs/design-snapshot/` after archive [REQ: snapshot-caching-in-state-directory]
- [x] 11.3 Delete `openspec/specs/design-spec-sync/` after archive [REQ: req-spec-sync-inject-design-references-into-spec-files]
- [x] 11.4 Delete `openspec/specs/design-brief-parser/` after archive [REQ: parse-figma-make-prompt-files]
- [x] 11.5 Delete `openspec/specs/design-brief-stem-match/` after archive [REQ: stem-bidirectional-matching]

## 12. Documentation

- [x] 12.1 Create `docs/design-pipeline.md` documenting the v0-only workflow (scaffold author → set-design-import → manifest → orchestration) [REQ: set-design-import-cli]
- [x] 12.2 Add a "Migration from Figma" section to docs explaining the BREAKING removal and how to re-author in v0 [REQ: req-make-parse-parse-make-files-into-structured-design-systemmd]
- [x] 12.3 Update `CLAUDE.md` to remove references to Figma Make / design.make and add v0 workflow pointers [REQ: design-bridge-rule-for-agents]
- [x] 12.4 Update `set-project init` (consumer-facing) to detect `.make` files and emit a clear migration error pointing to docs [REQ: req-make-parse-parse-make-files-into-structured-design-systemmd]
- [x] 12.5 Audit existing deployed `templates/core/rules/design-bridge.md` content (currently references Figma MCP and design-snapshot.md) and replace it as part of task 8.1 — verify `set-project init` no longer ships old Figma-aware rule [REQ: design-bridge-rule-for-agents]
- [x] 12.6 Add `docs/design-pipeline.md` § "Authentication for private design repos" — covers SSH agent setup, GITHUB_TOKEN env var (PAT), GitHub deploy keys, GitLab/Bitbucket equivalents, troubleshooting auth failures. Linked from set-design-import error messages. [REQ: git-source-mode-behavior]

## 13. Archive in-progress predecessor change

- [x] 13.1 Move `openspec/changes/v0-design-pipeline/v0-prompts.md` and any other durable artifacts into this change's `docs/` directory before archiving [REQ: set-design-import-cli]
- [x] 13.2 Mark `v0-design-pipeline` change as superseded with a note pointing to `v0-only-design-pipeline` [REQ: set-design-import-cli]
- [x] 13.3 Run `openspec archive v0-design-pipeline` once this change's proposal is approved [REQ: set-design-import-cli]

## 14. End-to-end validation (BLOCKED-BY: 9.2, 9.3, 9.4 must complete first)

- [ ] 14.1 Run `tests/e2e/runners/run-craftbrew.sh` and verify dispatch populates `openspec/changes/<change>/design-source/` for each change [REQ: per-change-design-source-directory-population]
- [ ] 14.2 Verify agent input.md contains `## Design Source` section pointing to the slice [REQ: design-context-injected-into-agent-input]
- [ ] 14.3 Verify design-fidelity gate runs at merge time and reports pass on a faithful agent implementation [REQ: gate-result-reporting]
- [ ] 14.4 Deliberately introduce a className change in an agent worktree, verify the gate blocks merge and emits diff images [REQ: pixel-diff-with-configurable-threshold]
- [x] 14.5 Verify removed Figma functions / files cause no test failures (clean break) [REQ: req-make-parse-parse-make-files-into-structured-design-systemmd]
- [x] 14.6 Verify Layer 1 abstraction guard test passes (no v0 imports in `lib/set_orch/`) [REQ: layer-1-has-no-v0-references]
- [x] 14.7 Verify legacy ABC method removal test passes (no `build_per_change_design` etc. on any profile) [REQ: removal-of-legacy-design-provider-methods]
- [ ] 14.8 Verify the runner-level fail-fast added in task 10.2 actually fires when v0-export is missing — without it, the gate would silently skip (per AC-26) and produce a false-green E2E run. This task is the regression test for the chain `runner check (10.2) → fail loud → gate never starts`. [REQ: set-design-import-cli]

## Acceptance Criteria (from spec scenarios)

> **Numbering convention**: ACs from the original 22-prompt scope use sequential numbers (AC-1 through AC-77 + AC-G1..AC-G19 for git-mode). ACs from gap additions use letter prefixes for traceability:
> - **AC-S** = Skeleton fidelity (Gap A)
> - **AC-V** = v0 quality validation + agent fix policy (Gap C)
> - **AC-B** = Decompose ↔ design-manifest binding (Gap B)
>
> Future gap additions should continue with new letters (AC-D, AC-E, ...) rather than re-using number ranges.

### v0-export-import

- [ ] AC-G1: WHEN `set-design-import --git <url> --ref main --scaffold <dir>` runs THEN repo cloned/fetched into <dir>/v0-export/ + commit SHA in summary [REQ: set-design-import-cli-source-modes, scenario: import-from-git-repo-preferred-mode]
- [ ] AC-G2: WHEN `set-design-import --scaffold <dir>` runs AND scaffold.yaml has design_source git block THEN CLI uses that source [REQ: set-design-import-cli-source-modes, scenario: import-from-scaffoldyaml-declared-source]
- [ ] AC-G3: WHEN both `--git` and `--source` passed THEN CLI exits non-zero with mutual-exclusion error [REQ: set-design-import-cli-source-modes, scenario: conflicting-source-flags]
- [ ] AC-G4: WHEN public HTTPS repo URL THEN clone succeeds without auth config [REQ: git-source-mode-behavior, scenario: public-repo-over-https]
- [ ] AC-G5: WHEN private repo via SSH AND key in agent THEN clone succeeds transparently [REQ: git-source-mode-behavior, scenario: private-repo-via-ssh]
- [ ] AC-G6: WHEN GITHUB_TOKEN env var set AND HTTPS repo THEN credential helper picks up token [REQ: git-source-mode-behavior, scenario: private-repo-via-https-with-token]
- [ ] AC-G7: WHEN git clone exits 128 THEN CLI error names URL + lists auth options + points to docs [REQ: git-source-mode-behavior, scenario: auth-failure-produces-actionable-error]
- [ ] AC-G8: WHEN URL is GitLab/Bitbucket/self-hosted THEN treated identically to GitHub [REQ: git-source-mode-behavior, scenario: provider-agnostic-url-acceptance]
- [ ] AC-G9: WHEN ref is branch THEN tip checked out + SHA in summary; WHEN ref is tag/SHA THEN immutable checkout [REQ: git-source-mode-behavior, scenario: ref-resolution]
- [ ] AC-G10: WHEN no --ref given AND scaffold.yaml lacks ref THEN default `main` + INFO log [REQ: git-source-mode-behavior, scenario: default-ref]
- [ ] AC-G11: WHEN URL has no cache entry THEN partial clone runs + .set-orch-meta written [REQ: clone-caching, scenario: first-clone-populates-cache]
- [ ] AC-G12: WHEN URL has cache entry THEN git fetch refreshes + ref checked out (no re-clone) [REQ: clone-caching, scenario: cache-hit-reuses-local-repo]
- [ ] AC-G13: WHEN cache key computed THEN URL hashed (SHA-256, 16 hex chars); raw URLs not in dir names [REQ: clone-caching, scenario: cache-key-hashes-the-url]
- [ ] AC-G14: WHEN ref checked out THEN cache contents copied to scaffold/v0-export/ excluding .git/ [REQ: clone-caching, scenario: materialization-to-scaffold]
- [ ] AC-G15: WHEN cache exceeds 5 entries THEN LRU prune + INFO log [REQ: clone-caching, scenario: cache-pruning]
- [ ] AC-G16: GIVEN scaffold.yaml v0-git block THEN set-design-import + runner both consult it [REQ: scaffoldyaml-design-source-schema, scenario: git-source-declaration]
- [ ] AC-G17: GIVEN scaffold.yaml v0-zip block THEN extracts from relative path [REQ: scaffoldyaml-design-source-schema, scenario: zip-source-declaration]
- [ ] AC-G18: WHEN scaffold.yaml has no design_source AND CLI run without flags THEN clear error [REQ: scaffoldyaml-design-source-schema, scenario: missing-design-source-block]
- [ ] AC-G19: GIVEN repo URL has embedded credentials THEN WARNING logged but import proceeds [REQ: scaffoldyaml-design-source-schema, scenario: auth-credentials-in-url-discouraged]
- [ ] AC-1: WHEN `set-design-import --source craftbrew-v0.zip --scaffold tests/e2e/scaffolds/craftbrew` runs (ZIP fallback mode) THEN ZIP is extracted to scaffolds/craftbrew/v0-export/ and exit 0 with summary [REQ: set-design-import-cli-source-modes, scenario: import-from-zip-fallback-mode]
- [ ] AC-2: WHEN `set-design-import --source craftbrew-v0.zip` runs inside a scaffold dir THEN scaffold defaults to cwd [REQ: set-design-import-cli-source-modes, scenario: import-without-scaffold-flag-uses-cwd]
- [ ] AC-3: WHEN `--source` path missing OR git URL not found THEN CLI exits non-zero with clear error [REQ: set-design-import-cli-source-modes, scenario: source-missing]
- [ ] AC-4: WHEN ZIP has app/, components/ui/, package.json, globals.css THEN validation passes silently [REQ: v0-export-structure-validation, scenario: valid-v0-export]
- [ ] AC-5: WHEN ZIP missing app/ THEN exits non-zero with App Router error [REQ: v0-export-structure-validation, scenario: missing-app-router]
- [ ] AC-6a: WHEN ZIP missing components/ui/ AND scaffold ui_library==shadcn THEN importer EXITS non-zero (broken export) [REQ: v0-export-structure-validation, scenario: missing-shadcn-ui-primitives-hard-fail]
- [ ] AC-6b: WHEN ZIP missing components/ui/ AND scaffold ui_library!=shadcn THEN missing dir is acceptable; importer continues [REQ: v0-export-structure-validation, scenario: missing-componentsui-when-scaffold-does-not-use-shadcn]
- [ ] AC-7: WHEN ZIP missing globals.css THEN exits non-zero with token error [REQ: v0-export-structure-validation, scenario: missing-globalscss]
- [ ] AC-8: WHEN auto-gen runs against tree with /, /kavek, /kavek/[slug] THEN manifest entries created with files + deps + scope_keywords [REQ: manifest-auto-generation, scenario: generate-manifest-from-app-router-tree]
- [ ] AC-9: WHEN manifest generated THEN components/ui/**, header.tsx, footer.tsx, app/layout.tsx, app/globals.css listed under shared: [REQ: manifest-auto-generation, scenario: shared-components-captured-under-shared]
- [ ] AC-10: WHEN existing manifest line marked `# manual` AND `--regenerate-manifest` runs THEN line preserved [REQ: manifest-auto-generation, scenario: manual-override-preserved-across-regeneration]
- [ ] AC-10b: WHEN `--regenerate-manifest` runs with no existing file THEN fresh manifest generated, no error [REQ: manifest-auto-generation, scenario: regenerate-manifest-with-no-existing-file]
- [ ] AC-11: WHEN importer completes THEN scaffold/shadcn/globals.css byte-identical to v0-export/app/globals.css [REQ: globalscss-sync-to-scaffold, scenario: globalscss-synced-after-import]
- [ ] AC-12: WHEN re-import runs with --force THEN previous v0-export/ removed before extraction; no stale files [REQ: idempotent-re-import, scenario: re-import-replaces-v0-export-entirely]
- [ ] AC-12b: WHEN duplicate keyword across routes THEN WARNING with conflicting routes; manifest still written [REQ: scope-keyword-collision-detection, scenario: duplicate-keyword-across-routes-warned]
- [ ] AC-12c: WHEN identical scope_keywords lists across routes THEN ERROR exit non-zero [REQ: scope-keyword-collision-detection, scenario: hard-failure-on-identical-scope-keywords-lists]

### v0-design-source

- [ ] AC-13: GIVEN v0-export/ exists THEN WebProjectType.detect_design_source returns "v0" [REQ: webprojecttype-implements-design-source-provider-methods, scenario: webprojecttypedetect-design-source-returns-v0-when-v0-export-exists]
- [ ] AC-14: GIVEN no v0-export/ THEN WebProjectType.detect_design_source returns "none" [REQ: webprojecttype-implements-design-source-provider-methods, scenario: webprojecttypedetect-design-source-returns-none-otherwise]
- [ ] AC-15: GIVEN manifest /kavek with scope_keywords [catalog, products, ...] AND scope mentions "catalog" THEN /kavek route selected [REQ: scope-keyword-matching-against-manifest, scenario: match-by-scope-keyword-substring]
- [ ] AC-16: WHEN scope spans multiple matching routes THEN all selected and deduplicated [REQ: scope-keyword-matching-against-manifest, scenario: multiple-routes-match]
- [ ] AC-17a: WHEN no route matches AND scope is non-UI (no UI keywords) THEN shared-only slice + INFO log (graceful) [REQ: scope-keyword-matching-against-manifest, scenario: no-route-matches-when-change-scope-is-non-ui-graceful]
- [ ] AC-17b: WHEN no route matches AND scope IS UI-bound (contains page/view/component/screen/render/layout/form/modal/dialog/manifest-segment) THEN raise NoMatchingRouteError; dispatcher fails with `design-route-unmatched`; remediation hint includes 3 fix options [REQ: scope-keyword-matching-against-manifest, scenario: no-route-matches-when-change-scope-is-ui-bound-hard-fail]
- [ ] AC-18: WHEN per-change population runs THEN matched files copied preserving structure [REQ: per-change-design-source-directory-population, scenario: copy-matched-files-preserving-structure]
- [ ] AC-19: WHEN any per-change populated THEN all shared:** files copied; missing shared = ERROR [REQ: per-change-design-source-directory-population, scenario: shared-files-always-included]
- [ ] AC-20: WHEN re-population runs THEN existing dest_dir removed first [REQ: per-change-design-source-directory-population, scenario: stale-design-source-removed-before-re-population]
- [ ] AC-21: WHEN token extraction runs on globals.css THEN :root --foo declarations parsed into structured dict [REQ: token-extraction-from-synced-globalscss, scenario: extract-css-custom-properties]
- [ ] AC-22: WHEN globals.css missing THEN empty token set + WARNING logged [REQ: token-extraction-from-synced-globalscss, scenario: globalscss-missing]
- [ ] AC-23: WHEN dispatch context built for v0 source THEN block contains directory pointer (using change_name) + file list + tokens + rule reference [REQ: agent-dispatch-context-references-design-source, scenario: context-block-structure]
- [ ] AC-24: WHEN context block built THEN ≤200 lines (excluding TSX content) [REQ: agent-dispatch-context-references-design-source, scenario: context-size-budget]

### design-fidelity-gate

- [ ] AC-25: WHEN WebProjectType loaded THEN design-fidelity gate registered post-build pre-merge [REQ: fidelity-gate-registered-in-gate-registry, scenario: gate-registration]
- [ ] AC-26: WHEN no v0-export/ exists THEN gate skipped at runtime; merge proceeds [REQ: fidelity-gate-registered-in-gate-registry, scenario: gate-disabled-when-no-v0-source]
- [ ] AC-27: WHEN gate runs THEN gate cd's into consumer project worktree path; pnpm install --frozen-lockfile && pnpm build runs there [REQ: headless-build-with-shared-fixtures, scenario: build-agent-worktree-correct-working-directory]
- [ ] AC-27b: WHEN worktree path unresolvable THEN gate fails fast with status worktree-path-unknown [REQ: headless-build-with-shared-fixtures, scenario: build-agent-worktree-correct-working-directory]
- [ ] AC-28: WHEN gate runs THEN v0-export copied to temp + fixtures from `<project>/.set-orch/v0-fixtures.yaml` applied + built [REQ: headless-build-with-shared-fixtures, scenario: build-v0-reference-with-fixtures-in-temp-dir]
- [ ] AC-28b: GIVEN detect_design_source==v0 AND fixtures missing THEN gate FAILS with `fixtures-missing` status; merge BLOCKED; remediation message points to scaffold + runner [REQ: headless-build-with-shared-fixtures, scenario: fixtures-missing-when-design-declared-hard-fail]
- [ ] AC-28c: GIVEN detect_design_source==v0 AND v0 reference build fails THEN gate FAILS with `reference-build-failed`; stderr saved; design URL+SHA in failure msg [REQ: headless-build-with-shared-fixtures, scenario: v0-reference-build-fails-when-design-declared-hard-fail]
- [ ] AC-28d: GIVEN detect_design_source==none THEN fixtures presence/absence irrelevant; gate skipped with `skipped-no-design-source` (existing behavior) [REQ: headless-build-with-shared-fixtures, scenario: fixtures-absent-when-design-absent-graceful-no-op]
- [ ] AC-29: WHEN screenshots captured THEN 3 viewports (1440x900, 768x1024, 375x667) per route + animations disabled + fonts ready [REQ: screenshot-capture-at-three-viewports, scenario: viewport-set]
- [ ] AC-30: WHEN gate runs THEN every manifest route captured; render failures reported [REQ: screenshot-capture-at-three-viewports, scenario: routes-covered]
- [ ] AC-31: GIVEN diff 0.8% AND threshold 1.5% THEN route passes [REQ: pixel-diff-with-configurable-threshold, scenario: diff-under-threshold]
- [ ] AC-32: GIVEN diff 3.2% AND threshold 1.5% THEN route fails + diff/agent/reference images saved [REQ: pixel-diff-with-configurable-threshold, scenario: diff-exceeds-threshold]
- [ ] AC-33: GIVEN per-route fidelity_threshold 3.0 THEN per-route override used [REQ: pixel-diff-with-configurable-threshold, scenario: per-route-threshold-override]
- [ ] AC-34: WHEN no threshold configured THEN default 1.5% + 200px floor [REQ: pixel-diff-with-configurable-threshold, scenario: default-threshold]
- [ ] AC-35: WHEN all routes pass THEN gate emits pass result + merge proceeds [REQ: gate-result-reporting, scenario: pass-result]
- [ ] AC-36: WHEN any route fails THEN gate emits fail + merge blocked + retry context populated [REQ: gate-result-reporting, scenario: fail-result-with-diffs]
- [ ] AC-37: GIVEN agent build fails first attempt THEN single retry; if succeeds, gate proceeds [REQ: retry-behavior, scenario: transient-build-retry]
- [ ] AC-38: GIVEN agent build fails twice THEN gate fails with build-failed-agent + stderr [REQ: retry-behavior, scenario: persistent-failure]
- [ ] AC-39: GIVEN warn_only true AND failures detected (any status) THEN gate emits pass with all failures listed; INFO log on EVERY run includes downgraded-failure list + reminder to disable [REQ: warn-only-mode-single-explicit-override, scenario: warn-only-enabled]
- [ ] AC-39b: WHEN any auto-graceful condition (missing manifest/fixtures, ref build fail) detected AND warn_only NOT explicitly true THEN gate FAILS; no other override mechanism exists [REQ: warn-only-mode-single-explicit-override, scenario: warn-only-is-the-only-override-mechanism]

### v0-fixture-renderer

- [ ] AC-40: GIVEN fixtures file at `<project>/.set-orch/v0-fixtures.yaml` THEN file conforms to schema [REQ: content-fixturesyaml-format, scenario: fixturesyaml-structure]
- [ ] AC-41: GIVEN detect_design_source==v0 AND no fixtures file THEN renderer raises FixturesMissingError; gate translates to fixtures-missing fail status; no auto-warn-only [REQ: content-fixturesyaml-format, scenario: missing-fixtures-file-when-design-declared-hard-fail]
- [ ] AC-41b: GIVEN detect_design_source==none THEN renderer no-ops gracefully (defensive code path) [REQ: content-fixturesyaml-format, scenario: missing-fixtures-file-when-design-absent-graceful]
- [ ] AC-42: GIVEN file with `<h1>Sample Coffee</h1>` AND fixture replace THEN temp copy contains `<h1>Ethiopia Yirgacheffe</h1>`; original unchanged [REQ: placeholder-string-substitution, scenario: substitute-string-in-tsx]
- [ ] AC-43: GIVEN 3 instances of `Lorem ipsum` THEN all 3 replaced [REQ: placeholder-string-substitution, scenario: multiple-matches-in-same-file]
- [ ] AC-44: GIVEN fixture entry with no occurrences THEN DEBUG log notes count 0; no failure [REQ: placeholder-string-substitution, scenario: no-match-logged-at-debug]
- [ ] AC-45: GIVEN data_imports target lib/mock-products.ts THEN temp copy file replaced with default-export of products.json [REQ: mock-data-layer-injection, scenario: inject-products-fixture]
- [ ] AC-46: GIVEN data_imports target missing in v0-export THEN file created at target path + INFO log [REQ: mock-data-layer-injection, scenario: target-file-does-not-exist-in-v0-export]
- [ ] AC-47: WHEN build succeeds THEN pnpm start launched + healthcheck (HTTP 200 on /, 30s timeout) + base URL returned [REQ: headless-build-of-fixture-substituted-copy, scenario: build-succeeds-server-starts]
- [ ] AC-48: WHEN pnpm build exits non-zero THEN ReferenceBuildError raised with stderr [REQ: headless-build-of-fixture-substituted-copy, scenario: build-fails]
- [ ] AC-49: WHEN screenshot capture finishes/errors THEN server SIGTERM → 5s → SIGKILL + temp dir removed [REQ: headless-build-of-fixture-substituted-copy, scenario: server-cleanup]
- [ ] AC-50: WHEN two gate runs start simultaneously THEN distinct temp dirs + ports; no interference [REQ: idempotent-and-concurrent-safe, scenario: concurrent-invocations]
- [ ] AC-51: GIVEN cached node_modules with matching lockfile hash THEN cache COPIED (cp --reflink=auto on Linux), NOT symlinked; pnpm install --prefer-offline runs [REQ: caching-of-pnpm-install-layer, scenario: cache-hit-copy-on-write-semantics]
- [ ] AC-51b: GIVEN two simultaneous gate runs with same hash THEN each gets own copy; cache treated as read-only [REQ: caching-of-pnpm-install-layer, scenario: concurrent-gate-runs-do-not-corrupt-cache]
- [ ] AC-52: GIVEN cached lockfile hash differs THEN cache invalidated atomically; fresh install + LRU prune to last 3 hashes [REQ: caching-of-pnpm-install-layer, scenario: cache-miss-invalidates-and-rebuilds]

### profile-hooks (modified)

- [ ] AC-53: WHEN NullProfile().detect_design_source called THEN returns "none"; copy_design_source_slice returns []; get_design_dispatch_context returns "" [REQ: profile-shall-expose-design-source-provider-methods, scenario: nullprofile-design-source-defaults]
- [ ] AC-54: WHEN CoreProfile().detect_design_source called THEN returns "none" (subclasses override) [REQ: profile-shall-expose-design-source-provider-methods, scenario: coreprofile-inherits-nullprofile-design-source-defaults]
- [ ] AC-55: WHEN lib/set_orch/ grepped for "v0" THEN no production imports of v0-specific helpers [REQ: profile-shall-expose-design-source-provider-methods, scenario: layer-1-has-no-v0-references]
- [ ] AC-55b: WHEN future plugin returns "figma-v2" or "storybook" THEN ABC accepts it (str type, not Literal) [REQ: profile-shall-expose-design-source-provider-methods, scenario: detect-design-source-returns-plain-str-for-forward-compat]
- [ ] AC-55c: WHEN ProjectType ABC inspected after change THEN build_per_change_design / build_design_review_section / old get_design_dispatch_context not present [REQ: removal-of-legacy-design-provider-methods, scenario: old-methods-removed-from-abc]
- [ ] AC-55d: WHEN concrete profiles inspected THEN none implement removed methods [REQ: removal-of-legacy-design-provider-methods, scenario: concrete-profiles-do-not-retain-old-methods]
- [ ] AC-55e: WHEN dispatcher code grepped THEN no calls to removed methods remain [REQ: removal-of-legacy-design-provider-methods, scenario: dispatcher-does-not-call-removed-methods]
- [ ] AC-56: WHEN dispatch_change runs AND profile has non-none design source THEN dispatcher computes dest = openspec/changes/<change_name>/design-source/, calls slice + context with change_name; markdown to input.md [REQ: dispatcher-uses-design-source-provider-methods, scenario: dispatcher-orchestrates-design-source-population]
- [ ] AC-57: GIVEN detect_design_source == "none" THEN dispatcher does NOT call slice/context methods; dispatch proceeds [REQ: dispatcher-uses-design-source-provider-methods, scenario: dispatcher-gracefully-handles-none]
- [ ] AC-58: GIVEN detect_design_source!=none AND profile method raises THEN ERROR logged + dispatch FAILS change with reason `design-provider-error` (no silent continue) [REQ: profile-shall-expose-design-source-provider-methods, scenario: profile-method-exception-when-design-declared-hard-fail]
- [ ] AC-58b: GIVEN detect_design_source==none AND defensive code path raises THEN DEBUG log; dispatch proceeds (no design content was expected) [REQ: profile-shall-expose-design-source-provider-methods, scenario: profile-method-exception-when-design-absent-graceful]

### design-bridge (modified)

- [ ] AC-59: WHEN agent session starts for change with design-source/ AND design-bridge.md present THEN rule directs to copy + adapt; allowed/forbidden lists exposed; aria-only safe vs sr-only flagged distinction shown [REQ: design-bridge-rule-for-agents, scenario: agent-with-design-source-in-change-directory]
- [ ] AC-60: WHEN no design-source AND detect_design_source none THEN rule no-op [REQ: design-bridge-rule-for-agents, scenario: agent-without-design-source-no-v0-export-in-project]
- [ ] AC-61: WHEN agent uncertain about visual contract THEN rule directs to preserve + commit + let gate decide [REQ: design-bridge-rule-for-agents, scenario: refactor-policy-ambiguity]
- [ ] AC-62: WHEN building dispatch context AND v0 source detected THEN slice + tokens included; no markdown brief as authoritative [REQ: design-context-source-priority, scenario: v0-design-source-present]
- [ ] AC-63: WHEN none AND globals.css present THEN tokens-only quick-reference; no dispatch block [REQ: design-context-source-priority, scenario: v0-not-present-globalscss-available]
- [ ] AC-63b: WHEN none AND no globals.css THEN dispatch proceeds with "No design source available" message; rule defaults to project shadcn/ui defaults [REQ: design-context-source-priority, scenario: no-design-source-and-no-globalscss]
- [ ] AC-64: WHEN docs/design-brief.md exists AND non-authoritative THEN included as `## Design Vibe Notes (non-authoritative)` only [REQ: design-context-source-priority, scenario: optional-vibe-note]

### design-dispatch-context (modified)

- [ ] AC-65: GIVEN WebProjectType + v0 source THEN profile.get_design_dispatch_context returns markdown referring to design-source/; written to input.md [REQ: design-context-extraction-for-dispatch, scenario: web-profile-with-v0-source]
- [ ] AC-66: GIVEN detect_design_source == "none" THEN profile returns empty/token-only; dispatch not blocked [REQ: design-context-extraction-for-dispatch, scenario: profile-with-no-design-source]
- [ ] AC-67: WHEN bridge layer invoked THEN no reads of design-snapshot.md / design-system.md / figma-raw / design-brief.md; no alias matching; Figma env vars ignored [REQ: design-context-extraction-for-dispatch, scenario: bridge-layer-figma-extraction-removed]

### design-dispatch-injection (modified)

- [ ] AC-68: WHEN dispatching change with non-empty design source THEN design-source/ populated before input.md; `## Design Source` section present [REQ: design-context-injected-into-agent-input, scenario: per-change-design-source-populated]
- [ ] AC-69: WHEN profile reports detect_design_source == "none" THEN no design-source/ created; section omitted [REQ: design-context-injected-into-agent-input, scenario: no-design-source-available]
- [ ] AC-70: WHEN dispatch_change/dispatch_ready_changes called THEN no design_snapshot_dir parameter accepted; all callers updated [REQ: design-context-injected-into-agent-input, scenario: design-snapshot-dir-parameter-removed-from-dispatch-chain]
- [ ] AC-71: GIVEN re-dispatch after verify failure THEN design-source/ repopulated; stale files removed [REQ: design-context-injected-into-agent-input, scenario: retry-preserves-design-source-freshness]
- [ ] AC-72: WHEN `## Design Source` block written THEN ≤200 lines (TSX in files, not embedded) [REQ: design-context-injected-into-agent-input, scenario: context-size-budget]

### profile-loader-builtin (modified)

- [ ] AC-73: GIVEN v0-export/ present THEN WebProjectType.detect_design_source returns "v0" [REQ: webprojecttype-implements-design-source-provider-methods, scenario: webprojecttypedetect-design-source-with-v0-export-present]
- [ ] AC-74: GIVEN no v0-export/ THEN returns "none" + graceful degradation [REQ: webprojecttype-implements-design-source-provider-methods, scenario: webprojecttypedetect-design-source-without-v0-export]
- [ ] AC-75: GIVEN v0 source AND valid manifest at <project>/docs/design-manifest.yaml THEN copy_design_source_slice(change_name, scope, dest) invokes manifest matcher + copies route + shared files [REQ: webprojecttype-implements-design-source-provider-methods, scenario: webprojecttypecopy-design-source-slice-populates-dest]
- [ ] AC-76: WHEN get_design_dispatch_context(change_name, scope, project_path) called THEN markdown contains pointer using change_name + file list + tokens + rule reference [REQ: webprojecttype-implements-design-source-provider-methods, scenario: webprojecttypeget-design-dispatch-context-returns-markdown]
- [ ] AC-77: WHEN WebProjectType loaded THEN design-fidelity gate registered; enabled when v0, skipped otherwise [REQ: webprojecttype-registers-design-fidelity-gate, scenario: webprojecttype-registers-design-fidelity-gate]

### Skeleton fidelity (Gap A)

- [ ] AC-S1: WHEN gate runs skeleton check THEN agent route inventory matches v0 route inventory (set equality after normalization); missing/extra routes blocked before any build [REQ: structural-skeleton-check-runs-before-screenshot-capture, scenario: route-inventory-match]
- [ ] AC-S2: WHEN skeleton check runs THEN every manifest shared file exists in agent worktree; inlined components reported as missing-shared-file [REQ: structural-skeleton-check-runs-before-screenshot-capture, scenario: shared-layout-files-exist]
- [ ] AC-S3: WHEN skeleton check runs THEN shared components remain discrete file exports (AST verified); collapsed decomposition reported [REQ: structural-skeleton-check-runs-before-screenshot-capture, scenario: component-decomposition-preserved]
- [ ] AC-S4: WHEN skeleton mismatch found THEN gate exits with skeleton-mismatch status; build/screenshot NOT attempted [REQ: structural-skeleton-check-runs-before-screenshot-capture, scenario: skeleton-check-fails-fast]
- [ ] AC-S5: GIVEN manifest declares shared_aliases THEN renamed shared component treated as equivalent [REQ: structural-skeleton-check-runs-before-screenshot-capture, scenario: per-scaffold-tolerance-for-renames]
- [ ] AC-S6: GIVEN detect_design_source==v0 AND manifest absent at gate time THEN gate FAILS with `manifest-missing` status; merge BLOCKED; ERROR log with expected path [REQ: structural-skeleton-check-runs-before-screenshot-capture, scenario: manifest-absent-at-gate-time-when-design-declared-hard-fail]
- [ ] AC-G20: GIVEN scaffold author hand-authors shared_aliases block THEN auto-gen never overwrites it; --regenerate-manifest preserves it [REQ: manifest-auto-generation, scenario: shared-aliases-field-for-project-rename-tolerance]
- [ ] AC-G21: WHEN no shared_aliases block present THEN defaults to empty {}; skeleton-check requires exact path equivalence [REQ: manifest-auto-generation, scenario: shared-aliases-default-empty]

### v0 quality validation (Gap C)

- [ ] AC-V1: WHEN validation runs THEN `npx tsc --noEmit` executed in v0-export; errors written to report; non-blocking by default, blocking with --strict [REQ: v0-template-quality-validation, scenario: typescript-type-check]
- [ ] AC-V2: WHEN validation runs AND --no-build-check NOT passed THEN `pnpm install && pnpm build` executed; failure BLOCKING [REQ: v0-template-quality-validation, scenario: build-smoke-test]
- [ ] AC-V3: WHEN validation runs THEN component naming similarity heuristic flags potentially-duplicated concepts; non-blocking [REQ: v0-template-quality-validation, scenario: component-naming-consistency]
- [ ] AC-V4: WHEN validation runs THEN every Link/router.push href verified against routes; broken links + orphan pages reported; BLOCKING by default; overridable with --ignore-navigation [REQ: v0-template-quality-validation, scenario: navigation-link-integrity]
- [ ] AC-V5: WHEN validation runs THEN variant coverage gaps detected per shared component; non-blocking warning [REQ: v0-template-quality-validation, scenario: variant-coverage-consistency]
- [ ] AC-V6: WHEN validation runs THEN shadcn vs raw HTML for similar contexts flagged; non-blocking [REQ: v0-template-quality-validation, scenario: shadcn-primitive-usage-consistency]
- [ ] AC-V7: WHEN validation completes THEN `<scaffold>/docs/v0-import-report.md` written with severity grouping, counts, source URL/SHA, timestamp; path printed to stdout [REQ: v0-template-quality-validation, scenario: report-file-is-the-artifact]
- [ ] AC-V8: WHEN BLOCKING issue found THEN importer exits non-zero with report path + summary [REQ: v0-template-quality-validation, scenario: hard-error-fail-fast]
- [ ] AC-V8b: WHEN report written THEN docs/v0-import-report.md added to scaffold .gitignore (changes per re-import; not committed) [REQ: v0-template-quality-validation, scenario: report-file-is-the-artifact]
- [ ] AC-V8c: WHEN --strict-quality flag passed AND ANY warning-level issue found THEN ALL warnings promoted to BLOCKING errors; importer exits non-zero [REQ: v0-template-quality-validation, scenario: -strict-quality-flag-promotes-all-warnings-to-errors]

### Agent v0-bug-fix policy (Gap C)

- [ ] AC-V9: WHEN agent finds bug in v0 source THEN rule directs fix-preserving-visual + commit prefix v0-fix:; common bug list provided [REQ: design-bridge-rule-for-agents, scenario: agent-encounters-bugs-in-v0-source-code]
- [ ] AC-V10: WHEN agent finds inconsistency between v0 pages THEN rule directs standardize-on-dominant + document; if standardization fails gate, escalate to scaffold author [REQ: design-bridge-rule-for-agents, scenario: agent-encounters-inconsistencies-between-v0-pages]

### Decompose ↔ design-manifest binding (Gap B)

- [ ] AC-B1: WHEN decompose runs AND manifest exists THEN skill reads manifest; routes inform plan; scope_keywords flow into change scope text [REQ: decompose-skill-reads-design-manifestyaml, scenario: decompose-with-v0-manifest-present]
- [ ] AC-B2: WHEN decompose runs AND no manifest THEN graceful fallback + INFO log [REQ: decompose-skill-reads-design-manifestyaml, scenario: decompose-without-manifest-graceful]
- [ ] AC-B3: WHEN plan generated AND manifest present THEN every change has design_routes field (list, may be empty for non-UI) [REQ: per-change-explicit-route-binding, scenario: plan-includes-design-routes-per-change]
- [ ] AC-B4: GIVEN older plan without design_routes THEN dispatcher falls back to scope-keyword matching [REQ: per-change-explicit-route-binding, scenario: backward-compatibility]
- [ ] AC-B5: WHEN plan has at least one non-empty design_routes OR deferred_design_routes (opt-in trigger) THEN coverage check runs: every manifest route in exactly one change or deferred [REQ: manifest-coverage-validation, scenario: coverage-check-at-plan-generation-opt-in-trigger]
- [ ] AC-B5b: GIVEN legacy plan with no design_routes anywhere AND no deferred_design_routes THEN validate_plan_design_coverage returns [] (skipped); INFO log records skip; dispatcher falls back to scope_keyword [REQ: manifest-coverage-validation, scenario: backward-compatibility-old-plans-skip-coverage]
- [ ] AC-B5c: GIVEN mixed plan (some changes have design_routes, others don't) THEN coverage triggers; non-bound changes contribute 0 routes; routes must come from other changes or deferred [REQ: manifest-coverage-validation, scenario: mixed-plan-triggers-coverage-opt-in-is-per-plan-not-per-change]
- [ ] AC-B6: WHEN manifest route in neither change nor deferred THEN ERROR; plan invalid; dispatch blocked [REQ: manifest-coverage-validation, scenario: unaccounted-route-is-a-planning-error]
- [ ] AC-B7: GIVEN deferred_design_routes entry THEN dispatcher skips that route [REQ: manifest-coverage-validation, scenario: deferred-routes-are-explicit]
- [ ] AC-B8: GIVEN route assigned to multiple changes THEN coverage check ERROR; plan invalid [REQ: manifest-coverage-validation, scenario: multi-change-route-assignment-is-an-error]
- [ ] AC-B9: GIVEN explicit design_routes on change THEN dispatcher uses exact route lookup; scope_keywords ignored [REQ: dispatcher-prefers-explicit-design-routes-over-scope-keyword-matching, scenario: explicit-design-routes-used]
- [ ] AC-B10: GIVEN empty/absent design_routes THEN dispatcher falls back to keyword matcher + INFO log [REQ: dispatcher-prefers-explicit-design-routes-over-scope-keyword-matching, scenario: empty-design-routes-falls-back-to-keyword-matching]
- [ ] AC-B11: GIVEN design_routes references missing manifest route THEN dispatcher ERROR for that change; other changes proceed [REQ: dispatcher-prefers-explicit-design-routes-over-scope-keyword-matching, scenario: explicit-route-does-not-exist-in-manifest]
- [ ] AC-B12: WHEN decompose Step 2 reaches project context discovery THEN agent ALSO reads docs/design-manifest.yaml [REQ: decompose-skill-instructs-planner-agent-on-design-awareness, scenario: skill-reads-manifest-as-part-of-project-context-discovery]
- [ ] AC-B13: WHEN agent generates plan THEN plan reasoning contains design_route_map debug section [REQ: decompose-skill-instructs-planner-agent-on-design-awareness, scenario: skill-maps-routes-to-spec-items]
- [ ] AC-B14: WHEN spec mentions UI feature with no manifest route THEN flagged as design_gap with options (regenerate v0 / remove from spec / accept gate skip) [REQ: decompose-skill-instructs-planner-agent-on-design-awareness, scenario: skill-flags-spec-manifest-gaps]
- [ ] AC-B15: WHEN manifest has route with no spec item THEN auto-deferred with reason "manifest-only — no spec item" [REQ: decompose-skill-instructs-planner-agent-on-design-awareness, scenario: skill-flags-manifest-spec-gaps]
