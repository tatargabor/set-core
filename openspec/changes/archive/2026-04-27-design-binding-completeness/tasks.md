## 1. Phase 1 — Layer 1 dataclass relocation (no behavior change)

- [x] 1.1 Created `lib/set_orch/design_manifest.py` with dataclasses: `Manifest`, `RouteEntry`, `ShellComponent`, `HygieneFinding` + `HygieneSeverity` enum (CRITICAL/WARN/INFO), `ManifestError`, `NoMatchingRouteError` [REQ: per-change-design_components-binding]
- [x] 1.2 Replaced inline class defs in `modules/web/set_project_web/v0_manifest.py` with re-export from `set_orch.design_manifest` (backward-compat preserved for all existing imports) [REQ: per-change-design_components-binding]
- [x] 1.3 No call site updates needed — the re-export shim transparently satisfies existing imports in v0_fidelity_gate.py + design_import_cli.py [REQ: per-change-design_components-binding]
- [x] 1.4 Verified: `Manifest is design_manifest.Manifest` returns True; web module test suite passes 128/128 [REQ: per-change-design_components-binding]

## 2. Phase 2 — Profile ABC extension

- [x] 2.1 Added `scan_design_hygiene(project_path) -> list` method to `ProjectType` ABC (default `return []`) [REQ: provider-exposes-scan_design_hygiene-method]
- [x] 2.2 Added `get_shell_components(project_path) -> list[str]` method to `ProjectType` ABC (default `return []`) [REQ: provider-exposes-get_shell_components-method]
- [x] 2.3 `WebProjectType` overrides both: `scan_design_hygiene` delegates to `V0DesignSourceProvider().scan_hygiene()` when v0-export/ exists; `get_shell_components` reads `manifest.shared` from `docs/design-manifest.yaml`. Both fail-safely on errors (warn + empty list) [REQ: provider-exposes-scan_design_hygiene-method]

## 3. Phase 3 — V0DesignSourceProvider class

- [x] 3.1 Create `modules/web/set_project_web/v0_design_source.py` with `V0DesignSourceProvider` class implementing: `detect()`, `extract_manifest()`, `scan_hygiene()`, `get_shell_components()` [REQ: v0designsourceprovider-implements-scan_hygiene]
- [x] 3.2 Move v0-specific delegation from `WebProjectType` direct calls into `V0DesignSourceProvider` consolidation [REQ: v0designsourceprovider-implements-scan_hygiene]
- [x] 3.3 Update existing `modules/web/tests/test_v0_design_source_provider.py` to test the new class [REQ: v0designsourceprovider-implements-get_shell_components]

## 4. Phase 4 — Shell auto-detect heuristic

- [x] 4.1 Modify `_collect_shared_files()` in `modules/web/set_project_web/v0_manifest.py` to scan `app/**/page.tsx` and `app/**/layout.tsx` for static `import` statements pointing to `@/components/<name>` (or relative `../components/<name>`) [REQ: shell-auto-detect-via-page-import-scan]
- [x] 4.2 Build per-component importer-set; components with ≥2 distinct importer pages added to `manifest.shared` [REQ: shell-auto-detect-via-page-import-scan]
- [x] 4.3 Preserve hardcoded `SHARED_GLOBS` baseline (always shared, regardless of import count) [REQ: shell-auto-detect-via-page-import-scan]
- [x] 4.4 Preserve `manifest.shared_aliases` and `manifest.deferred_design_routes` across regenerations [REQ: re-running-set-design-import-refreshes-shared-list]
- [x] 4.5 Create `modules/web/tests/test_v0_shell_autodetect.py` with fixtures: (a) 5-page importer detected, (b) single-importer NOT detected, (c) baseline preserved [REQ: shell-auto-detect-via-page-import-scan]

## 5. Phase 5 — Hygiene scanner (9 rules)

- [x] 5.1 Create `modules/web/set_project_web/v0_hygiene_scanner.py` with TSX parser entry point `scan_v0_export(path: Path) -> list[HygieneFinding]` [REQ: 9-hygiene-rules-detect-common-design-source-antipatterns]
- [x] 5.2 Implement Rule 1: MOCK arrays inline (`const MOCK_*`/`FAKE_*`/`STUB_*`) → CRITICAL [REQ: 9-hygiene-rules-detect-common-design-source-antipatterns]
- [x] 5.3 Implement Rule 2: Hardcoded UI strings (≥3 alphabetic chars in JSX body, NOT aria/data attrs) → WARN [REQ: 9-hygiene-rules-detect-common-design-source-antipatterns]
- [x] 5.4 Implement Rule 3: Placeholder action handlers (TODO/FIXME/implement comments in event handlers) → WARN [REQ: 9-hygiene-rules-detect-common-design-source-antipatterns]
- [x] 5.5 Implement Rule 4: Inconsistent shell adoption (≥70% pages import shell, others don't) → CRITICAL [REQ: 9-hygiene-rules-detect-common-design-source-antipatterns]
- [x] 5.6 Implement Rule 5: Mock URL images (unsplash/picsum/placeholder.com) → INFO [REQ: 9-hygiene-rules-detect-common-design-source-antipatterns]
- [x] 5.7 Implement Rule 6: Inline lambda action handlers (≥3 line body) → INFO [REQ: 9-hygiene-rules-detect-common-design-source-antipatterns]
- [x] 5.8 Implement Rule 7: TypeScript `any` usage in `.tsx` → WARN [REQ: 9-hygiene-rules-detect-common-design-source-antipatterns]
- [x] 5.9 Implement Rule 8: Broken route references (`<Link href>` not in manifest.routes) → CRITICAL [REQ: 9-hygiene-rules-detect-common-design-source-antipatterns]
- [x] 5.10 Implement Rule 9: Locale-prefix inconsistency (HU page → EN-only path or vice versa) → WARN [REQ: 9-hygiene-rules-detect-common-design-source-antipatterns]
- [x] 5.11 Markdown checklist generator: severity-tiered output to `docs/design-source-hygiene-checklist.md` [REQ: markdown-checklist-output]
- [x] 5.12 Create `modules/web/tests/test_v0_hygiene_scanner.py` with one test fixture per rule (positive + negative case) [REQ: 9-hygiene-rules-detect-common-design-source-antipatterns]

## 6. Phase 6 — set-design-hygiene CLI

- [x] 6.1 Create `modules/web/set_project_web/design_hygiene_cli.py` (analog `design_import_cli.py`) with argparse: `--scaffold`, `--output`, `--ignore-critical` [REQ: markdown-checklist-output]
- [x] 6.2 Create `modules/web/bin/set-design-hygiene` (thin launcher) [REQ: markdown-checklist-output]
- [x] 6.3 Add console_script entry to `modules/web/pyproject.toml`: `set-design-hygiene = "set_project_web.design_hygiene_cli:main"` [REQ: markdown-checklist-output]
- [x] 6.4 CLI exits 1 if ≥1 CRITICAL finding (unless `--ignore-critical`) [REQ: critical-findings-cause-non-zero-exit]
- [x] 6.5 Verify CLI works on craftbrew-run-20260423-2223's `v0-export/` — output should include the known issues (header inconsistency, MOCK_PRODUCTS) [REQ: 9-hygiene-rules-detect-common-design-source-antipatterns]

## 7. Phase 7 — set-design-import --with-hygiene flag

- [x] 7.1 Add `--with-hygiene` flag to argparse in `design_import_cli.py` [REQ: --with-hygiene-flag-triggers-post-import-scan]
- [x] 7.2 In `main()` after manifest regeneration, if `--with-hygiene`: call `V0DesignSourceProvider.scan_hygiene()` and write checklist [REQ: --with-hygiene-flag-triggers-post-import-scan]
- [x] 7.3 Add `--ignore-critical` flag for force-bypass [REQ: --with-hygiene-flag-triggers-post-import-scan]
- [x] 7.4 Exit code 1 on CRITICAL unless ignored [REQ: --with-hygiene-flag-triggers-post-import-scan]

## 8. Phase 8 — Spec entity-reference parser

- [x] 8.1 Create `lib/set_orch/spec_parser.py` with `extract_design_references(spec_text: str) -> list[EntityRef]` using regex `@component:([a-z][a-z0-9-]+)` and `@route:(/\S+)` [REQ: spec-entity-reference-marker-syntax]
- [x] 8.2 Add validator: `validate_references(refs, manifest) -> list[ValidationError]` checking each reference exists in manifest [REQ: spec-entity-reference-marker-syntax]
- [x] 8.3 Create `tests/unit/test_spec_entity_parser.py` with fixtures for marker extraction, multi-reference, validation errors [REQ: spec-entity-reference-marker-syntax]

## 9. Phase 9 — Decompose plumbing for design_components

- [x] 9.1 Update `.claude/skills/set/decompose/SKILL.md` step 6 ("Bind design-manifest routes to changes") to extract `@component:` and `@route:` markers from each change's spec subset [REQ: plan-output-includes-design_components-per-change]
- [x] 9.2 Compute `design_components` per change as union of: route's `component_deps` ∪ `manifest.shared` ∪ resolved entity-marker components [REQ: plan-output-includes-design_components-per-change]
- [x] 9.3 Emit `design_gap` ambiguity if `@component:NAME` reference does not exist in manifest [REQ: spec-entity-reference-marker-syntax]
- [x] 9.4 Update plan output schema to include `design_components: list[str]` per change [REQ: per-change-design_components-binding]

## 10. Phase 10 — Dispatcher input.md Focus injection

- [x] 10.1 Identify the `input.md` writing function in `lib/set_orch/dispatcher.py` (search for "wrote input.md") [REQ: dispatcher-injects-design_components-into-input.md]
- [x] 10.2 Add `design_components` paths to the `## Focus files for this change` section, prefixed with directive line: "**Mount these components from the design source. DO NOT create parallel implementations under different names.**" [REQ: dispatcher-injects-design_components-into-input.md]
- [x] 10.3 Deduplicate paths if `design_components` overlaps with existing Focus entries [REQ: design_components-autopopulated-into-focus-files]
- [x] 10.4 Create `tests/unit/test_dispatcher_focus_injection.py` with fixture: change with `design_components` → input.md contains directive line + paths [REQ: dispatcher-injects-design_components-into-input.md]

## 11. Phase 11 — Shell-shadow gate

- [x] 11.1 In `modules/web/set_project_web/v0_fidelity_gate.py::run_skeleton_check`, add new phase after the existing `manifest.shared` existence check [REQ: shell-shadow-check-phase]
- [x] 11.2 For each shell, scan agent's `src/components/**/*.tsx` (and `src/components/_shell/`) for filename token-overlap (kebab-case split, ≥1 shared token) [REQ: shell-shadow-check-phase]
- [x] 11.3 For each filename match, parse imports and compare with shell's shadcn primitive imports — ≥2 shared → confirmed shadow [REQ: shell-shadow-check-phase]
- [x] 11.4 Emit `decomposition-shadow` violation severity WARN; respect `manifest.shared_aliases` whitelist [REQ: shell-shadow-check-phase]
- [x] 11.5 Read `gate_overrides.design-fidelity.shell_shadow_severity` directive — promote to CRITICAL if set [REQ: shell-shadow-severity-is-configurable]
- [x] 11.6 Add `decomposition-shadow` to `_FAIL_VIOLATION_STATUSES` only when severity is critical [REQ: shell-shadow-severity-is-configurable]
- [x] 11.7 Create `modules/web/tests/test_v0_shell_shadow_gate.py` with fixtures: (a) shadow detected, (b) no overlap → no violation, (c) alias whitelisted [REQ: shell-shadow-check-phase]

## 12. Phase 12 — Write-spec strict anti-pattern detector

- [x] 12.1 Update `.claude/skills/set/write-spec/SKILL.md` "Anti-Pattern Detection" table — add: hex/rgb/oklch literals → BLOCK; shadcn primitive name (`<Button>`, `<Card>` etc.) → BLOCK; PascalCase component name → WARN; layout descriptor (modal/dropdown/sidebar) → WARN; tailwind className (`bg-primary` etc.) → BLOCK; `.tsx`/`src/`/`components/` path → BLOCK; UI feature without entity ref → WARN [REQ: strict-anti-pattern-detection-in-write-spec]
- [x] 12.2 Add `<!-- design-discipline-exempt -->` HTML comment as opt-out [REQ: operator-can-override-with-grandfather-comment]
- [x] 12.3 Add prompt in skill: when feature mentions UI, suggest `@component:` or `@route:` from manifest [REQ: spec-entity-reference-marker-syntax]

## 13. Phase 13 — Optional spec migration CLI

- [x] 13.1 Create `modules/web/set_project_web/spec_clean_cli.py` (LLM-based, Haiku) — extracts visual descriptions from spec.md, proposes diff [REQ: optional-spec-migration-via-set-spec-clean-design-cli]
- [x] 13.2 Create `modules/web/bin/set-spec-clean-design` thin launcher [REQ: optional-spec-migration-via-set-spec-clean-design-cli]
- [x] 13.3 Register console_script in `modules/web/pyproject.toml` [REQ: optional-spec-migration-via-set-spec-clean-design-cli]
- [x] 13.4 Output: cleaned spec + `docs/design-references.md` archive [REQ: optional-spec-migration-via-set-spec-clean-design-cli]

## 14. Phase 14 — Templates / rules

- [x] 14.1 Update `templates/core/rules/design-bridge.md` — add component-mounting rule with bad/good example pair (search-bar.tsx vs search-palette.tsx) [REQ: component-mounting-rule]
- [x] 14.2 Add entity-reference recognition note to `design-bridge.md` (`@component:`, `@route:` markers are mandatory references) [REQ: entity-reference-recognition]
- [x] 14.3 Create `templates/core/rules/design-source-hygiene.md` (operator-facing rule about hygiene checklist workflow) [REQ: --with-hygiene-flag-triggers-post-import-scan]

## 15. Phase 15 — Validation

- [x] 15.1 Run full pytest on set-core; all phases green [REQ: per-change-design_components-binding]
- [x] 15.2 Re-run `set-design-import --regenerate-manifest --with-hygiene` on craftbrew-run-20260423-2223; verify the manifest's `shared` list now contains `search-palette`, `product-filters`, `product-card`, `cart-item`, `cookie-consent` [REQ: shell-auto-detect-via-page-import-scan]
- [x] 15.3 Verify the hygiene checklist for craftbrew-run lists the known issues: header inconsistency 14/24 pages CRITICAL, MOCK_PRODUCTS in search-palette CRITICAL [REQ: 9-hygiene-rules-detect-common-design-source-antipatterns]
- [x] 15.4 Smoke E2E orchestration on micro-web template — verify `design_components` is populated in the plan AND appears in agent's `input.md` Focus files [REQ: dispatcher-injects-design_components-into-input.md]
- [x] 15.5 Add a test that intentionally creates a `search-bar.tsx` parallel to a manifest shell `search-palette.tsx` — verify the fidelity gate emits `decomposition-shadow` WARN [REQ: shell-shadow-check-phase]

## 16. Phase 16 — Documentation

- [x] 16.1 Update `docs/design-pipeline.md` with the new flow: shell auto-detect → hygiene check → entity-reference markers → design_components binding [REQ: per-change-design_components-binding]
- [x] 16.2 Add example workflow in operator guide: design re-import → hygiene check → fix in design source repo → re-run [REQ: markdown-checklist-output]

## Acceptance Criteria (from spec scenarios)

### design-component-binding

- [x] AC-1: WHEN decompose generates plan AND change has `@component:search-palette` AND manifest has search-palette in shared THEN change's `design_components` contains `v0-export/components/search-palette.tsx` [REQ: per-change-design_components-binding, scenario: field-populated-from-manifest-+-entity-refs]
- [x] AC-2: WHEN change has `design_routes: [/kereses]` AND manifest's `/kereses.component_deps` has `product-card.tsx` THEN `design_components` includes the path [REQ: per-change-design_components-binding, scenario: field-populated-from-route-component_deps]
- [x] AC-3: WHEN older plan lacks `design_components` THEN dispatcher reads as `[]` and proceeds [REQ: per-change-design_components-binding, scenario: backward-compat-—-empty-field]
- [x] AC-4: WHEN spec section contains `@component:search-palette` THEN parser yields `("component", "search-palette")` [REQ: spec-entity-reference-marker-syntax, scenario: marker-extraction-from-spec]
- [x] AC-5: WHEN decompose extracts `@component:search-foo` AND manifest lacks `search-foo` THEN `design_gap` ambiguity emitted [REQ: spec-entity-reference-marker-syntax, scenario: manifest-validation]
- [x] AC-6: WHEN spec has 2 component refs + 1 route ref THEN both populate respective fields [REQ: spec-entity-reference-marker-syntax, scenario: multiple-references-in-one-spec]
- [x] AC-7: WHEN dispatcher writes input.md with 2 design_components THEN both paths appear under Focus files with directive line [REQ: dispatcher-injects-design_components-into-input.md, scenario: focus-files-contain-bound-components]
- [x] AC-8: WHEN change has empty design_components THEN no design Focus mention in input.md [REQ: dispatcher-injects-design_components-into-input.md, scenario: empty-design_components-produces-no-focus-mention]

### design-source-hygiene

- [x] AC-9: WHEN `MOCK_PRODUCTS` array exists in TSX THEN scanner emits CRITICAL with file:line [REQ: 9-hygiene-rules-detect-common-design-source-antipatterns, scenario: mock-array-detected]
- [x] AC-10: WHEN 14/24 pages lack SiteHeader import (10 have it) THEN CRITICAL header inconsistency finding [REQ: 9-hygiene-rules-detect-common-design-source-antipatterns, scenario: header-inconsistency-detected]
- [x] AC-11: WHEN `<Link href="/loginnn">` exists AND manifest lacks `/loginnn` THEN CRITICAL with closest match suggestion [REQ: 9-hygiene-rules-detect-common-design-source-antipatterns, scenario: broken-route-detected]
- [x] AC-12: WHEN `<Button>Kosárba</Button>` literal exists THEN WARN with file:line [REQ: 9-hygiene-rules-detect-common-design-source-antipatterns, scenario: hardcoded-hu-string-detected]
- [x] AC-13: WHEN `set-design-hygiene` runs THEN writes to `docs/design-source-hygiene-checklist.md` by default [REQ: markdown-checklist-output, scenario: output-file-location]
- [x] AC-14: WHEN any CRITICAL findings present THEN CLI exits 1 [REQ: critical-findings-cause-non-zero-exit, scenario: critical-findings-cause-non-zero-exit]
- [x] AC-15: WHEN `set-design-import --with-hygiene` runs on clean source THEN exit 0, INFO/WARN only in checklist [REQ: --with-hygiene-flag-triggers-post-import-scan, scenario: combined-import-+-hygiene-with-no-findings]
- [x] AC-16: WHEN `--with-hygiene` finds CRITICAL THEN exit 1, checklist still written [REQ: --with-hygiene-flag-triggers-post-import-scan, scenario: hygiene-finds-critical-—-exit-non-zero]
- [x] AC-17: WHEN `--with-hygiene --ignore-critical` AND CRITICAL exists THEN exit 0 [REQ: --with-hygiene-flag-triggers-post-import-scan, scenario: operator-force-bypass]
- [x] AC-18: WHEN `set-design-import` runs without flag THEN no scan performed [REQ: --with-hygiene-flag-triggers-post-import-scan, scenario: default-omits-hygiene]

### design-shell-shadow-detection

- [x] AC-19: WHEN agent's search-bar.tsx imports CommandDialog/CommandInput AND manifest has search-palette.tsx with same imports THEN `decomposition-shadow` WARN emitted naming both files [REQ: shell-shadow-check-phase, scenario: shadow-detected-on-parallel-implementation]
- [x] AC-20: WHEN agent's header.tsx imports Sheet primitives (no overlap with search-palette) THEN no violation [REQ: shell-shadow-check-phase, scenario: no-shadow-without-heuristic-match]
- [x] AC-21: WHEN `manifest.shared_aliases: {search-mini.tsx: search-palette.tsx}` THEN no violation for `search-mini.tsx` [REQ: shell-shadow-check-phase, scenario: shared-aliases-whitelist-legitimate-variants]
- [x] AC-22: WHEN gate emits `decomposition-shadow` WARN AND other phases pass THEN gate result "PASSED with warnings" AND merge proceeds [REQ: shell-shadow-severity-is-configurable, scenario: default-warn-does-not-block-merge]
- [x] AC-23: WHEN `gate_overrides.design-fidelity.shell_shadow_severity: critical` is set AND shadow detected THEN merge blocked [REQ: shell-shadow-severity-is-configurable, scenario: override-to-critical-blocks-merge]

### design-shell-autodetect

- [x] AC-24: WHEN 5 pages import SearchPalette from `@/components/search-palette` THEN `manifest.shared` contains `search-palette.tsx` [REQ: shell-auto-detect-via-page-import-scan, scenario: search-palette-appears-in-5-pages]
- [x] AC-25: WHEN only 1 page imports OrderSummary THEN `manifest.shared` does NOT contain it [REQ: shell-auto-detect-via-page-import-scan, scenario: single-importer-component-is-not-shared]
- [x] AC-26: WHEN auto-detect runs THEN `app/layout.tsx` and `app/globals.css` remain in shared (baseline) [REQ: shell-auto-detect-via-page-import-scan, scenario: hardcoded-shared_globs-baseline-preserved]
- [x] AC-27: WHEN component is dynamically imported via `next/dynamic` THEN NOT detected as imported (v1 limitation; INFO logged) [REQ: shell-auto-detect-via-page-import-scan, scenario: both-static-and-dynamic-only-patterns]
- [x] AC-28: WHEN new shell added in v0 source AND used by 3 pages AND `set-design-import --regenerate-manifest` runs THEN manifest's shared includes it [REQ: re-running-set-design-import-refreshes-shared-list, scenario: new-shell-added-in-v0-source]
- [x] AC-29: WHEN regenerate runs THEN `manifest.shared_aliases` preserved verbatim [REQ: re-running-set-design-import-refreshes-shared-list, scenario: shared-aliases-preserved]

### spec-design-discipline

- [x] AC-30: WHEN spec requirement contains color literal `#78350F` THEN write-spec blocks save with line ref + token suggestion [REQ: strict-anti-pattern-detection-in-write-spec, scenario: color-literal-blocks-spec-save]
- [x] AC-31: WHEN requirement contains `<Button variant="ghost">` THEN save blocked with `@component:NAME` suggestion [REQ: strict-anti-pattern-detection-in-write-spec, scenario: shadcn-primitive-in-requirement-blocks-save]
- [x] AC-32: WHEN UI feature requirement lacks `@component:` or `@route:` THEN WARN about missing entity reference [REQ: strict-anti-pattern-detection-in-write-spec, scenario: ui-feature-without-entity-reference-triggers-warn]
- [x] AC-33: WHEN `<!-- design-discipline-exempt -->` HTML comment present on offending line THEN lint silent [REQ: strict-anti-pattern-detection-in-write-spec, scenario: operator-can-override-with-grandfather-comment]
- [x] AC-34: WHEN `set-spec-clean-design <spec.md>` runs on legacy spec with visual content THEN proposes cleaned spec + `docs/design-references.md` diff for review [REQ: optional-spec-migration-via-set-spec-clean-design-cli, scenario: migrate-a-legacy-spec]
- [x] AC-35: WHEN new project scaffolded via `set-project init` THEN migration CLI not auto-invoked AND lint defaults strict [REQ: optional-spec-migration-via-set-spec-clean-design-cli, scenario: default-off-in-scaffolds]

### profile-hooks (delta)

- [x] AC-36: WHEN `WebProjectType.scan_design_hygiene(path)` called AND v0 detected THEN delegates to `V0DesignSourceProvider.scan_hygiene` [REQ: provider-exposes-scan_design_hygiene-method, scenario: web-profile-delegates-to-v0-provider]
- [x] AC-37: WHEN non-web profile asked THEN returns `[]` without error [REQ: provider-exposes-scan_design_hygiene-method, scenario: non-web-profile-returns-empty]
- [x] AC-38: WHEN `WebProjectType.get_shell_components(path)` called AND manifest has shared THEN returns paths [REQ: provider-exposes-get_shell_components-method, scenario: reads-shared-from-manifest]

### v0-design-source (delta)

- [x] AC-39: WHEN `V0DesignSourceProvider.scan_hygiene` called AND MOCK arrays present THEN finding rule `mock-arrays-inline` severity `critical` [REQ: v0designsourceprovider-implements-scan_hygiene, scenario: provider-returns-scanner-findings]
- [x] AC-40: WHEN `V0DesignSourceProvider.get_shell_components` called THEN returns manifest's shared paths verbatim [REQ: v0designsourceprovider-implements-get_shell_components, scenario: provider-returns-shared-list]

### design-bridge (delta)

- [x] AC-41: WHEN agent reads design-bridge.md THEN finds the bad example "agent creates search-bar.tsx while v0 has search-palette.tsx" with explanation [REQ: component-mounting-rule, scenario: bad-pattern-named-in-rule]
- [x] AC-42: WHEN agent reads design-bridge.md THEN finds the good example: import SearchPalette from @/components/search-palette + adapt with useQuery [REQ: component-mounting-rule, scenario: good-pattern-named-in-rule]
- [x] AC-43: WHEN spec contains `@component:search-palette` THEN agent imports SearchPalette + does NOT create parallel [REQ: entity-reference-recognition, scenario: agent-encounters-@component-marker-in-spec]
