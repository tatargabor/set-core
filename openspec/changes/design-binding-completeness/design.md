## Context

The `v0-only-design-pipeline` change (~50% complete, foundation deployed) established the design pipeline architecture: profile-based design source detection (`detect_design_source`), per-scaffold `docs/design-manifest.yaml`, decompose route binding (`design_routes`), per-change `design-source/` slice, fidelity gate skeleton check. This works in production today (`craftbrew-run-20260423-2223`).

What it does NOT do, evidenced by the same run:
1. **Plan does not bind components** — only routes. Planner has no way to enforce "use the existing `search-palette.tsx`".
2. **Manifest `shared:` is undersized** — 4 entries; 15+ shell components in `v0-export/components/` are NOT classified, so they get re-implemented per change.
3. **Specs leak design** — visual descriptors in spec.md override design source, agent picks the spec text.
4. **No quality scanner** — design-source bugs (header inconsistency, MOCK arrays, hardcoded strings) propagate silently into every run.

This change closes those four gaps without rebuilding the pipeline. Each gap maps to a specific extension point that the foundation already exposes.

Stakeholders: framework operators (consistent runs), agents (clear scope), design-source maintainers (actionable hygiene reports).

## Goals / Non-Goals

**Goals:**
- Manifest `shared:` list reflects actual usage (auto-detect ≥2 importer rule).
- Plan binds components (not just routes); planner Focus files autopopulate from binding.
- Spec ↔ design entity binding via explicit marker syntax (`@component:`, `@route:`).
- Hygiene scanner detects 9 quality rules pre-run; per-project checklist generated for operator.
- Fidelity gate adds shell-shadow detection (negative-space check for parallel implementations).
- Strengthened write-spec anti-pattern detector blocks visual descriptors.

**Non-Goals:**
- No rebuild of `v0-only-design-pipeline` foundation — extends, does not replace.
- No frozen-shell adoption (byte-match enforcement of v0 → consumer copy) — separate future change if needed.
- No automatic design source repository fixes — operator fixes in design source repo (Mac side); framework only detects and reports.
- No new design tool (Claude Design, Figma) integration — interface is ready (provider abstraction), implementation deferred until sample artifacts available.
- No migration of existing specs — legacy specs grandfathered with `# design-discipline-exempt` comment.

## Decisions

### D1. Auto-detect shell components via page-import scan
**Choice:** `_collect_shared_files()` in `v0_manifest.py` scans every `app/**/page.tsx` for static `import` statements pointing to `@/components/<name>` (or relative `../components/<name>`). Component appears in ≥2 distinct pages → added to `manifest.shared`.

**Rationale:** Project-independent heuristic. Catches `search-palette`, `product-filters`, `product-card`, `cart-item` etc. without project-specific lists. Hardcoded `SHARED_GLOBS` baseline (header, footer, layout, globals) remains as fallback.

**Alternatives considered:**
- *Operator-curated shared list*: too manual; project owner has to maintain.
- *Threshold ≥3 importers*: too restrictive; many shells used by 2 pages only.
- *AST-based dynamic-import detection*: phase 2 if `React.lazy`/`next/dynamic` patterns prove material.

### D2. `design_components` is additive to `design_routes`
**Choice:** Plan output includes BOTH `design_routes` (existing — paths) and `design_components` (new — TSX file paths). They are computed independently:
- `design_routes` from spec scope keywords + manifest route entries (existing decompose-design-binding logic)
- `design_components` = union of (a) `component_deps` of each `design_routes` route + (b) `manifest.shared` (auto-expanded) + (c) explicit `@component:` markers in the change's spec subset

**Rationale:** Routes stay route-shaped; components stay component-shaped. They reinforce each other rather than collapsing into a single flat list.

**Alternatives considered:**
- *Replace `design_routes` with `design_components` only*: backward-compat break with in-progress `decompose-design-binding` spec; rejected.
- *Single flat `design_artifacts: list[str]`*: loses semantic distinction useful for the dispatcher's design-source slice copy.

### D3. Spec entity-reference syntax: `@component:NAME` and `@route:/PATH`
**Choice:** Inline markers within spec.md / linked feature spec body. Parser is regex-based: `@component:([a-z][a-z0-9-]+)` and `@route:(/\S+)`. Validator checks each reference exists in the manifest.

**Rationale:** Lightweight, parseable from any markdown text without LLM call. Familiar pattern (analogous to `@mention` in social tools, `@user/repo` in GitHub). Doesn't require structural spec format change.

**Validation:** Decompose-time check — if a `@component:` references a name not in `manifest.shared`, emit `design_gap` ambiguity (operator must add the component to v0 OR remove the marker). This is the equivalent of the existing `design-route-coverage` validation, applied to components.

**Alternatives considered:**
- *YAML front-matter declaration*: requires structural change, doesn't co-locate with the prose discussing the feature.
- *Markdown link syntax `[search-palette](manifest:component)`*: more verbose, harder to extract.

### D4. Hygiene scanner produces severity-tiered findings, not blocking
**Choice:** `set-design-hygiene` outputs CRITICAL / WARN / INFO findings to a markdown checklist. Exit code 1 if any CRITICAL finding exists. The CLI does NOT modify the design source — operator manually fixes in the design source repo.

**Rationale:** The framework cannot edit the design source repo (separate location, possibly different git provider). The right division: framework detects and reports, operator fixes. CRITICAL findings represent issues that meaningfully degrade run quality (broken routes, header inconsistency); WARN are i18n-leakage / mock-data flags; INFO are nice-to-fix.

**Operator workflow:**
1. Run `set-design-import --with-hygiene` (or `set-design-hygiene` standalone).
2. Open `docs/design-source-hygiene-checklist.md`.
3. For each CRITICAL: fix in design source repo (e.g., v0-design on Mac).
4. Re-run `set-design-import --with-hygiene` until 0 CRITICAL.
5. Start orchestration run.

### D5. Shell-shadow gate is heuristic, severity WARN
**Choice:** New gate phase in `v0_fidelity_gate.py::run_skeleton_check`: for each manifest shell component, check if agent worktree has a similarly-named-or-purposed file that's NOT the shell. Heuristic match: filename token-overlap + similar shadcn primitive imports. Violation severity WARN (not BLOCK) because false positives are likely.

**Rationale:** Negative-space check is genuinely heuristic — there is no perfect "this re-implements that" match. Severity WARN gives operator visibility without blocking legitimate variants.

**Operator escalation path:** if WARN-severity shadow detection fires repeatedly across runs for legitimate cases, operator can add an alias to `manifest.shared_aliases` (existing field) to whitelist the variant.

### D6. Generic-first architecture; v0-specifics are isolated
**Choice:** `lib/set_orch/design_manifest.py` (new) hosts the canonical dataclasses (`Manifest`, `RouteEntry`, `ShellComponent`, `HygieneFinding`). `modules/web/set_project_web/v0_manifest.py` re-exports these for backward compatibility AND implements the v0-specific generation logic.

The hygiene scanner (`v0_hygiene_scanner.py`) is generic at the rule level (TSX antipatterns are tech-agnostic) but lives in the web module because the rules apply to TSX-producing sources. When Claude Design or Figma providers arrive, they reuse the same scanner if their output is TSX, or implement their own scanner if not.

**Rationale:** Reuse over duplication; clean Layer 1/2 boundary preserved.

### D7. Spec migration is opt-in via separate CLI
**Choice:** `set-spec-clean-design` (LLM-powered, Haiku for cost) extracts visual descriptions from existing specs and rewrites with entity-reference markers. Default OFF; operator runs it when ready. Existing specs without migration are grandfathered (write-spec lint warns but does not block).

**Rationale:** Forced migration breaks all in-progress projects. The opt-in path lets each project migrate at its own pace, and the lint signals which specs benefit most.

### D8. `--with-hygiene` flag on `set-design-import`
**Choice:** When importing a design (re-clone or re-extract), the CLI optionally runs the hygiene scanner as a post-import step (after manifest regeneration). Flag is opt-in to keep the default import fast.

**Rationale:** Hygiene scan is most useful right after re-import (before agents run); coupling them gives operators a single command for the design refresh workflow.

## Risks / Trade-offs

**Risk:** Shell auto-detect overshoots — pulls in too many components as shared, broadening the `shell-shadow` check too much, producing many false-positive WARN.
**Mitigation:** D5 — WARN severity, not BLOCK. Plus `manifest.shared_aliases` allows whitelisting.

**Risk:** Spec entity-reference markers (`@component:NAME`) drift from manifest — agent reads `@component:search-palette` but manifest doesn't have it (e.g., manifest stale).
**Mitigation:** Decompose-time validation emits `design_gap` ambiguity. Operator forced to either re-import design or fix the marker.

**Risk:** Hygiene scanner is slow on large design sources (every TSX file parsed).
**Mitigation:** Single-threaded today; can parallelize per-file in phase 2 if it becomes a bottleneck. Default operation is opt-in, not on every dispatch.

**Risk:** `design_components` field in plan output breaks downstream consumers reading old plan format.
**Mitigation:** Field is additive (default empty list). Dispatcher reads with `change.design_components or []`. Backward-compat preserved.

**Risk:** Strict write-spec anti-pattern blocking visual descriptors frustrates spec authors.
**Mitigation:** BLOCK only on the most concrete leakage (color literals, shadcn primitive names); WARN on softer descriptors (`modal`, `dropdown`) so authors can opt to keep with `# design-discipline-exempt` comment.

**Risk:** Layer 1 `design_manifest.py` is a moving target during `v0-only-design-pipeline` finalization (50% remaining).
**Mitigation:** Coordinate with the in-progress change's owner; if the manifest schema changes upstream, the dataclasses adapt.

## Migration Plan

**Phase 1 — Manifest infrastructure** (no behavior change):
- Move dataclasses to `lib/set_orch/design_manifest.py` with re-export shim in `v0_manifest.py`.
- Add ABC method stubs (`scan_design_hygiene`, `get_shell_components`) returning empty lists by default.

**Phase 2 — Shell auto-detect**:
- Implement page-import scan in `_collect_shared_files()`.
- Run on craftbrew-run-20260423-2223 manifest, verify expected shells appear (search-palette, product-filters, product-card, etc.).

**Phase 3 — Hygiene scanner**:
- Implement 9 rules in `v0_hygiene_scanner.py`.
- Generate first checklist for craftbrew-run, validate findings match the issues we already know about (header inconsistency, MOCK arrays).

**Phase 4 — Fidelity gate shell-shadow**:
- Add new phase to `v0_fidelity_gate.py::run_skeleton_check`.
- Test fixture: agent creates `search-bar.tsx` while `search-palette.tsx` exists → gate emits WARN.

**Phase 5 — Decompose + planner integration**:
- Decompose extracts `@component:` markers, populates `design_components`.
- Dispatcher writes `design_components` into input.md Focus files.

**Phase 6 — Spec discipline**:
- Strengthen write-spec anti-pattern detector (BLOCK color literals, shadcn primitive names).
- Add prompts for entity-references when feature has UI.
- (Optional) `set-spec-clean-design` migration CLI.

**Rollback:** Each phase is independently revertable. No state-file migration. Existing manifests are forward-compatible (auto-detect adds entries; never removes).

## Open Questions

- Should the hygiene scanner CRITICAL findings cause `set-design-import --with-hygiene` to exit non-zero (forcing operator action before run starts)? **Decision:** YES — operator should consciously bypass with `--ignore-hygiene` flag if needed.
- Should `design_components` ALSO include shadcn primitives (`Button`, `Card`)? **Decision:** NO — shadcn UI is provided by `components/ui/**`, already shared transitively. Keep the list focused on shell components from `components/*.tsx`.
- The `@route:/PATH` marker validation against manifest — does it need to handle template-literal route patterns (`/kavek/[slug]`)? **Decision:** YES, validator normalizes both sides via the same Next.js path conventions before comparison.
