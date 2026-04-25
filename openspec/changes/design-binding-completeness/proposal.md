## Why

Production runs (most recent: `craftbrew-run-20260423-2223`) consistently produce UI that diverges from the v0 design source — even when the design pipeline is healthy and the fidelity gate passes. The gap is not in the foundation; it's in **enforcement of the design-as-data architecture**:

1. **Planner hallucinates component names** — for `catalog-global-search` the planner wrote scope `src/components/search-bar.tsx` with inline `Popover` dropdown. v0 already had `search-palette.tsx` (CommandDialog modal, 364 lines). The agent followed the planner's hallucinated name, not the existing v0 shell.
2. **Manifest `shared:` list is too narrow** — only 4 entries (`site-header`, `site-footer`, `app/layout`, `globals.css`). Components used by ≥2 pages (`search-palette`, `product-filters`, `product-card`, `cart-item`, `cookie-consent`) are NOT classified as shell, so they get silently re-implemented per change.
3. **No negative-space check** — the existing fidelity gate verifies "v0 file exists in agent worktree" but NOT "agent did not create a parallel implementation" (e.g., agent's `search-bar.tsx` shadowing v0's `search-palette.tsx`). 
4. **Specs leak design** — `catalog-global-search` spec contained "shadcn Command/Popover pattern", "dropdown shows two sections", "between nav and CartBadge" — visual descriptors that contradict the design source. Without strict separation, the LLM picks the shorter/specific path (the spec's prose) over the design's TSX.
5. **Design-source quality issues are invisible** — v0 export has real bugs (header import inconsistency 14/24 pages, `MOCK_PRODUCTS` arrays inline, hardcoded HU strings). These propagate to every consumer run because no scanner detects them pre-run.
6. **No spec ↔ design entity binding** — even the decompose binding stops at `design_routes` (route paths). It does NOT bind `design_components` (TSX files), so the planner cannot mechanically reference v0 components by name.

This change closes the enforcement gap on top of the in-progress `v0-only-design-pipeline` foundation.

## What Changes

### Manifest enhancement (Layer 2 web)
- Auto-detect shell components (used by ≥2 pages) and add them to `manifest.shared` automatically. Hardcoded `SHARED_GLOBS` baseline remains; auto-detected entries appended.
- New `set-design-hygiene` CLI generates per-project `docs/design-source-hygiene-checklist.md` with 9 quality rules (mock data, hardcoded strings, route integrity, locale-prefix consistency, header/shell consistency, action handler stubs, type `any` usage, placeholder URLs, MOCK arrays).

### Engine — design entity binding (Layer 1)
- New `design_components: list[str]` field per change in orchestration plan (extends existing `design_routes`).
- `lib/set_orch/design_manifest.py` (new): canonical Manifest, RouteEntry, ShellComponent, HygieneFinding dataclasses (relocated from `modules/web/set_project_web/v0_manifest.py` for reuse across providers).
- Dispatcher writes `design_components` into agent's `input.md` `Focus files for this change` section (autopopulated).

### Spec entity-reference syntax
- New marker syntax: `@component:NAME` and `@route:/PATH` in spec.md / linked feature specs.
- Decompose extracts these markers; `change.design_components` = union of all marker references in the change's spec subset.
- Write-spec skill's anti-pattern detector strengthened to BLOCK visual descriptors (`modal`, `dropdown`, `sidebar`, `popup`, `dialog`, shadcn primitive names, color literals) and REQUIRE `@component:` or `@route:` reference for any UI feature.
- Optional `set-spec-clean-design` CLI migrates legacy specs by extracting visual descriptions to a separate `docs/design-references.md`.

### Fidelity gate enhancement
- New `shell-shadow` check in `v0_fidelity_gate.py`: detects parallel-implementation of known shell components (e.g., agent's `search-bar.tsx` shadows v0's `search-palette.tsx`). Emits `decomposition-shadow` violation (severity WARN — heuristic-based, not blocking by default).
- Optional Rule 8 fidelity-side route integrity check (against consumer worktree's `<Link href>` references).

### Rules / templates
- `design-bridge.md` gains an explicit "component-mounting rule" — if a shell component for the feature exists in the design source, mount it; do NOT create a parallel implementation.
- New `design-source-hygiene.md` rule documents how operators consume the auto-generated checklist before each run.

## Capabilities

### New Capabilities
- `design-component-binding`: per-change `design_components` field plus the entity-reference marker syntax (`@component:`, `@route:`).
- `design-source-hygiene`: scanner CLI + per-project checklist generation + 9 quality rules.
- `design-shell-shadow-detection`: fidelity-gate negative-space check for parallel-implementation violations.
- `design-shell-autodetect`: heuristic-based auto-population of `manifest.shared` from page-import counts.
- `spec-design-discipline`: strict anti-pattern detection in write-spec, blocking visual descriptors and requiring entity references.

### Modified Capabilities
- `decompose-design-binding` (in-progress): ADDED requirement — `design_components` field per change (extends existing `design_routes`).
- `design-dispatch-injection` (in-progress): ADDED requirement — `design_components` listed in agent's `Focus files` section of `input.md`.
- `v0-design-source` (in-progress): ADDED requirements — provider implements `scan_design_hygiene`, `get_shell_components`.
- `design-bridge` (in-progress): ADDED requirement — explicit shell-mounting rule with examples.
- `v0-export-import` (in-progress): ADDED requirement — `--with-hygiene` flag on `set-design-import` runs hygiene scan.
- `design-fidelity-gate` (in-progress): ADDED requirement — `shell-shadow` check phase.
- `profile-hooks` (in-progress): ADDED requirement — new ABC methods `scan_design_hygiene()`, `get_shell_components()`.

## Impact

**Code:**
- `lib/set_orch/design_manifest.py` (new) — Layer 1 dataclasses
- `lib/set_orch/profile_types.py` — extend ABC with two methods
- `lib/set_orch/dispatcher.py` — input.md Focus files extension
- `lib/set_orch/spec_parser.py` (new) — entity-reference extraction
- `modules/web/set_project_web/v0_manifest.py` — shell auto-detect heuristic
- `modules/web/set_project_web/v0_fidelity_gate.py` — shell-shadow check phase
- `modules/web/set_project_web/v0_hygiene_scanner.py` (new) — 9 quality rules
- `modules/web/set_project_web/v0_design_source.py` (new) — provider class consolidating v0 design source logic
- `modules/web/set_project_web/design_hygiene_cli.py` (new) — CLI
- `modules/web/set_project_web/design_import_cli.py` — `--with-hygiene` flag
- `modules/web/set_project_web/spec_clean_cli.py` (new, optional) — migration CLI

**CLIs (web module):**
- `modules/web/bin/set-design-hygiene` (new)
- `modules/web/bin/set-spec-clean-design` (new, optional)
- `modules/web/pyproject.toml` — register console scripts

**Templates / rules:**
- `templates/core/rules/design-bridge.md` — add component-mounting rule
- `templates/core/rules/design-source-hygiene.md` (new) — operator-facing rule

**Skills:**
- `.claude/skills/set/decompose/SKILL.md` — extract entity references, populate `design_components`
- `.claude/skills/set/write-spec/SKILL.md` — strengthen anti-pattern detector + entity-reference prompts

**Tests:**
- `modules/web/tests/test_v0_shell_autodetect.py` (new)
- `modules/web/tests/test_v0_hygiene_scanner.py` (new)
- `modules/web/tests/test_v0_shell_shadow_gate.py` (new)
- `modules/web/tests/test_v0_design_source_provider.py` (extend)
- `tests/unit/test_design_manifest_dataclasses.py` (new)
- `tests/unit/test_dispatcher_focus_injection.py` (new)
- `tests/unit/test_spec_entity_parser.py` (new)

**Generic vs source-specific:**
- 14 of 15 implementation areas are generic (work for any TSX-producing design source); only `V0DesignSourceProvider` is v0-specific (and is interface-cleanly cross-replaceable when Claude Design or Figma providers are added later).

**Risk surface:**
- Shell auto-detect heuristic could over-classify components (false positive shell tagging). Mitigation: severity WARN on shell-shadow violation, not BLOCK.
- Hygiene scanner produces noisy output for design sources with intentional patterns (e.g., placeholder URLs in styleguide pages). Mitigation: severity tiering (CRITICAL/WARN/INFO), operator triages.
- Entity-reference syntax is breaking for new specs — existing specs grandfathered with `# design-discipline-exempt` comment, no migration forced.

**Out of scope (deferred):**
- Frozen shell + adapter pattern (full v0-export adoption with byte-match enforcement) — only if 6-fix doesn't reach 90% fidelity.
- Claude Design provider implementation — interface-ready, awaits real handoff bundle sample.
- Pixel-diff fidelity activation (already exists optional in fidelity gate, not changed here).
- I18n string-extraction tooling at design-source-fix time — operator-side work in design source repo.
- v0-design specific bug fixes (header inconsistency, MOCK_PRODUCTS removal, hardcoded string propification) — auto-detected and listed in hygiene checklist; operator fixes in design source repo (Mac side), framework only flags.
- Spec-level enforcement of implementation-side route integrity (consumer worktree `<Link href>` validation) — partial F7 ext suggestion, deferred.
