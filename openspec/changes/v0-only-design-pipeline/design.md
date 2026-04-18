# Design: v0-only Design Pipeline

## Context

set-core has carried a Figma-Make ingestion pipeline (`.make` ZIP → markdown spec → agent re-implements UI) since the initial design-bridge introduction. Empirically, the pipeline has produced unreliable downstream output across multiple consumer runs:

- Token pairs collapsed to identical values (`--muted` == `--muted-foreground`) → invisible UI text on cream backgrounds
- Interactive states absent in the spec → indistinguishable variant selectors
- Agents re-implementing layouts produced subtle drift (different className, swapped shadcn primitives)
- The `.make` binary cannot be diffed or reviewed; bugs hid for hundreds of lines

In parallel, v0.app generates production-grade Next.js + shadcn/ui code that exactly matches set-core's web stack. Its output is React, not a markdown approximation.

This change replaces the entire design pipeline with one that consumes v0 exports as the authoritative source. Agents shift from "designer + implementer" to "integrator": they take v0 components as fixed, and adapt the integration layer (data, copy, types, backend wiring).

The architectural rule remains: **Layer 1 (`lib/set_orch/`) stays abstract**; v0 is web-stack-specific and lives entirely in **Layer 2 (`modules/web/`)**.

## Goals / Non-Goals

### Goals

- A scaffold author runs `set-design-import --source <v0.zip>` once and the framework deploys the design to all subsequent orchestration runs.
- Dispatcher slices the v0 export per change scope and hands the agent the actual TSX files (not a markdown spec).
- A standalone integration gate (`design-fidelity`) blocks merges when the agent's rendered output deviates visually from v0's reference.
- Agents may freely refactor v0's code structure (extract components, rename, retype, add types, wire backend); design integrity (className, JSX structure, shadcn primitive choice, spacing, animations) is enforced by the gate, not by file diff.
- The Figma pipeline is removed entirely — no compatibility shim — so two parallel design pipelines never coexist.
- Layer 1 stays free of v0-specific code; everything plugs in via the `ProjectType` ABC.

### Non-Goals

- Multi-source design (Figma + v0 simultaneously) — explicitly rejected. One source per project.
- Live re-fetching from v0.app via API — out of scope for v1; export ZIP is the input format.
- AI-vision-based fidelity arbitration — designed but deferred to v2 (see Risks).
- Migrating existing Figma-using consumer projects automatically. Consumers re-author their design in v0 and re-import.
- Generating v0 prompts from a spec (the reverse direction). The v0-prompts.md authored manually by a human is the input to v0; the export is the output we consume.

## Decisions

### D1. v0 export sourced from external git repo (default), with ZIP fallback

**Decision:** Scaffolds reference an external git repo as the design source. `v0-export/` is gitignored locally and materialized at deploy time via `git clone` (or `git fetch` + checkout for re-imports). ZIP import is supported as an offline fallback.

**Alternatives:**
- (a) Commit `v0-export/` directly to scaffold git → set-core repo bloat (~1-5MB per scaffold), design history pollutes set-core commit log, no v0-native workflow
- (b) Git submodule → operational complexity (`.gitmodules` discipline, CI init/update steps)
- (c) ZIP-only with manual download/upload → no diff history between iterations, manual reproducibility
- (d) **CHOSEN:** External git repo as primary source, ZIP as fallback, gitignored materialization

**Rationale:**
- v0.app has a native "Push to GitHub" feature → the import workflow becomes one command
- Git history of the v0 repo IS the design change log (diffable across iterations: "v0 chat moved this card from `<Card>` to `<ProductCard>`")
- Pinning by commit SHA gives immutable reproducibility
- Multi-scaffold reuse: one v0 repo can be referenced by multiple scaffolds (or the same repo on different branches for variant designs)
- Private repos work transparently via standard git auth (SSH keys, credential helpers, `GITHUB_TOKEN` env var) — no framework auth code needed
- ZIP fallback covers offline / air-gapped environments

**scaffold.yaml structure:**
```yaml
project_type: web
template: nextjs
ui_library: shadcn
design_source:
  type: v0-git              # or "v0-zip" for fallback
  repo: https://github.com/owner/v0-craftbrew-design.git
  ref: main                 # branch, tag, or commit SHA
```

For private repos:
```yaml
design_source:
  type: v0-git
  repo: git@github.com:owner-org/v0-customer-design.git
  ref: v1.2.0
  # auth: relies on system git config — no fields here
```

**Caching:** Clones cached in `~/.cache/set-orch/v0-clones/<sha256-of-url>/`. Re-import does `git fetch && git checkout <ref>` (fast). URL is hashed for cache key so private repo URLs are not stored cleartext in cache directory names.

**Cost:** Network dependency for first import / new ref pulls. Acceptable for a design-time operation. Cache eliminates repeat-clone cost.

### D2. Manifest is auto-generated, with manual override

**Decision:** `set-design-import` auto-generates `design-manifest.yaml` from the v0 file tree using App Router route conventions and import-graph traversal. The manifest is a regular file and may be hand-edited; subsequent `--regenerate-manifest` runs preserve manual overrides via a `# manual` marker on lines.

**Alternatives:**
- (a) Pure auto-generation, no overrides — too brittle when v0 produces unexpected file names
- (b) Pure manual authoring — defeats "import once, done" UX
- (c) **CHOSEN:** Auto-generated with override support

**Rationale:** v0's output is mostly predictable (App Router conventions). Auto-generation handles 90% of cases. The 10% of edge cases (alternate route groups, custom barrels) need manual touch. The marker-based override preserves human edits across regenerations.

**Manifest structure:**
```yaml
design_source: v0
v0_export_path: v0-export/

routes:
  - path: /
    files: [v0-export/app/page.tsx]
    component_deps: [v0-export/components/hero.tsx, v0-export/components/featured-coffees.tsx]
    scope_keywords: [homepage, hero, featured]    # auto from path + first H1
  - path: /kavek
    files: [v0-export/app/kavek/page.tsx]
    component_deps: [v0-export/components/product-card.tsx]
    scope_keywords: [catalog, kavek, products, coffees]

shared:
  - v0-export/components/ui/**
  - v0-export/components/header.tsx
  - v0-export/components/footer.tsx
  - v0-export/app/layout.tsx
  - v0-export/app/globals.css
```

### D3. Refactor policy: visual contract, not file contract

**Decision:** Agents may refactor v0's code freely (extract components, rename, restructure, add types, wire backend). The contract is **visual fidelity** of the built output, not file-for-file equivalence. The fidelity gate enforces this via screenshot diff.

**Allowed refactors:**
- Extract repeated JSX into reusable component files
- Rename / move files to project convention (kebab-case, directory structure)
- Add TypeScript types where v0 used `any` or omitted
- Convert client→server components where data is server-side (preserve interactivity!)
- Replace mock data with Prisma queries / real API calls
- Add SEO `metadata` exports, Suspense boundaries, error.tsx
- Replace English placeholder copy with HU content from i18n catalog
- Replace placeholder images with seed/CMS image URLs
- Add accessibility attributes (aria-*) — explicitly **encouraged**

**Forbidden changes (caught by fidelity gate):**
- Tailwind className value changes (even "more semantic" alternatives)
- DOM structure changes (added/removed wrappers, sibling reorder)
- shadcn primitive substitution (Button → custom HTML button)
- shadcn variant prop changes (size, variant, etc.)
- Spacing token changes (gap, padding, margin)
- Responsive breakpoint changes
- Animation sequence/duration/easing changes
- Icon library substitution
- `globals.css` modification (synced from v0-export, agent must NOT touch)

**Rationale:** Agents need creative latitude to integrate with the project's data layer and conventions. Locking file structure prevents valid refactors (extracting `<ProductCard>` shared across pages). Locking visual output enforces the actual user-facing contract.

### D4. Fidelity gate uses Standard tier (visual diff with shared fixtures)

**Decision:** The fidelity gate runs Playwright screenshot capture + pixelmatch diff with shared HU fixture data, threshold ~1–2% per region, 3 viewports (desktop 1440, tablet 768, mobile 375). AI-vision arbitration is designed but deferred to v2.

**Tier comparison:**
- (Minimal) Token compliance + manual screenshot review — too lax, drift slips through
- (**CHOSEN: Standard**) Token compliance + pixel diff with shared fixtures
- (Full) + Claude vision arbiter for flagged routes — drift detection sweet spot but expensive/flaky in v1

**Rationale:** Standard tier provides robust drift detection without the operational cost (API spend, latency, non-determinism) of vision-model integration. The hard part — building shared fixture rendering for both v0 reference and agent output — is necessary regardless of tier. AI vision can be added in v2 as a second-opinion layer for flagged routes.

### D5. Build-time content substitution (the v0-fixture-renderer)

**Decision:** Before screenshot capture, the v0-export is copied to a temp directory and patched with HU content from a `content-fixtures.yaml` file (defined in scaffold). The patched copy is built (`pnpm build && pnpm start`) and screenshot-captured. Agent worktree is built and screenshot-captured the same way. Diff happens between the two.

**Patch strategy:**
- Replace English placeholder strings (`Sample Coffee`, `Lorem ipsum`) with HU equivalents from fixtures
- Inject mock data layer that returns the project's seed data (so `<ProductCard>` shows "Ethiopia Yirgacheffe" with the right price)
- No source modification beyond placeholder substitution — preserves v0's structure exactly

**Alternatives:**
- (a) Render v0 as-is and accept higher pixel diff threshold — fails to detect real drift
- (b) Run E2E against shared dev DB — too coupled to backend code
- (c) **CHOSEN:** Static content substitution + mock data layer

**Rationale:** The substitution layer is purely additive (no v0 source mutation). Both renders use identical data, so the diff isolates to actual layout/styling differences. The substitution config lives in the scaffold (next to seed data), so it's reusable across runs.

### D6. Layer 1 stays abstract; everything v0-specific in Layer 2

**Decision:** `lib/set_orch/` (core) gains three new ABC methods:
```python
class ProjectType(ABC):
    @abstractmethod
    def detect_design_source(self, project_path: Path) -> str:
        """Return identifier of the design source for this project, or 'none'.
        Plain str (not Literal) keeps the ABC forward-compatible with future plugins."""

    @abstractmethod
    def copy_design_source_slice(
        self, change_name: str, scope: str, dest_dir: Path
    ) -> list[Path]:
        """Populate dest_dir with scope-matched design files for the named change."""

    @abstractmethod
    def get_design_dispatch_context(
        self, change_name: str, scope: str, project_path: Path
    ) -> str:
        """Return markdown for the agent's input.md Design Source section.
        Receives change_name so the block can reference openspec/changes/<change_name>/design-source/."""
```

Three legacy methods are simultaneously REMOVED from the ABC:
- `build_per_change_design(change_name, scope, wt_path, snapshot_dir) -> bool`
- `build_design_review_section(snapshot_dir) -> str`
- `get_design_dispatch_context(scope, snapshot_dir) -> str` (old two-param signature)

The dispatcher generically calls the new methods. Implementation lives in `WebProjectType` and uses the v0 manifest. Core never knows the file is from v0.

**What stays in Layer 2 (`modules/web/set_project_web/`):**
- `v0_importer.py` — ZIP unpack, validation, manifest generation
- `v0_manifest.py` — manifest parsing and scope keyword matching
- `v0_renderer.py` — content substitution + headless build + screenshot capture
- `v0_fidelity_gate.py` — pixelmatch diff + report generation
- `bin/set-design-import` — CLI (in `modules/web/bin/`)
- `WebProjectType.detect_design_source()`, `WebProjectType.copy_design_source_slice()`, `WebProjectType.get_design_dispatch_context()`

**Rationale:** v0 is fundamentally Next.js + shadcn-shaped. A future Python-CLI plugin or mobile-app plugin would never use v0. The ABC keeps core stack-agnostic; web module gets to be opinionated.

### D8. Fail loud when design is declared; fail silent only when it is absent

**Decision:** Two distinct policies based on whether the project DECLARED a design source:

1. **Design declared** (`detect_design_source() != "none"`, e.g. `v0-export/` exists or scaffold.yaml has `design_source` block): EVERY design-related operation MUST succeed or HARD FAIL. No silent fallbacks, no auto-warn-only, no "graceful degradation." Errors are bugs to fix, not workarounds to absorb.
2. **Design absent** (no design source declared): operations gracefully no-op (empty design context, no slice copy, gate skipped). The project chose to not have a design, the framework respects that.

**Rationale:** Soft-fail semantics in design pipelines silently leak bugs into production. A missing manifest at gate time, a broken v0 reference build, a profile method exception — these are deployment or scaffold bugs. Treating them as "warning, proceed" hides the bug behind a green check, then surprises everyone in production. The `warn_only: true` config flag is the ONE explicit user-acknowledged override (for emergencies); auto-warn-only behaviors are removed.

**Concrete consequences:**
- Manifest absent at gate time AND `detect_design_source==v0` → **FAIL** (deployment bug; the runner should have placed the manifest)
- Fixtures missing AND `detect_design_source==v0` → **FAIL** (config bug; gate cannot produce reliable diff without fixtures)
- v0 reference build fails AND `detect_design_source==v0` → **FAIL** (the design is broken; cannot ship)
- Profile method raises during dispatch AND `detect_design_source!=none` → **FAIL** dispatch (the design subsystem is broken; do not silently proceed)
- v0-export missing `components/ui/` AND scaffold targets shadcn → **FAIL** at import (broken v0 export)
- Scope-keyword fallback finds no match AND change scope is UI-bound → **FAIL** (planning bug; either the manifest is incomplete or the change shouldn't claim to implement UI)
- All importer quality warnings (naming, variant coverage, shadcn consistency) gain `--strict-quality` CLI flag → fail-on-any-warning mode

**Override:** scaffold authors can set `gates.design-fidelity.warn_only: true` in orchestration config for explicit emergency mitigation. This stays as the single supported escape hatch, and is logged at INFO every gate run so it doesn't silently persist.

**Alternatives considered:**
- (a) Status quo: graceful degradation everywhere → silent bug propagation
- (b) Always hard-fail regardless of design declaration → breaks projects that genuinely don't have a design source
- (c) **CHOSEN:** binary policy gated on `detect_design_source()` — fail loud when declared, gracefully no-op when absent

### D7. The fidelity gate is a real integration gate (not a code-review section)

**Decision:** Register `design-fidelity` in the gate registry (web module's `gate_registry.py`). It runs as a standalone integration gate in the merge pipeline (after build, before merge). Currently the design check is a string injected into the code review prompt — that approach is removed.

**Rationale:** Per memory `project_review_gate_not_running.md`, the existing review-pipeline design compliance section never executes (engine bypasses it via direct merge queue). A real gate slots into the existing gate framework, runs blocking, and reports through the standard gate result schema. The web module owns it (because it depends on v0 + Playwright).

## Risks / Trade-offs

[**Risk 1**] Pixel diff false positives from font loading / animation timing → **Mitigation:** Playwright `waitForLoadState("networkidle")` + `waitForFunction(() => document.fonts.ready)` before snapshot; disable CSS animations during capture via `prefers-reduced-motion` injection.

[**Risk 2**] v0 export structure changes between Vercel releases → **Mitigation:** v0_importer validates expected structure (`app/`, `components/ui/`, `globals.css`) and reports actionable errors. Manifest auto-generation has a fallback to "single-page export" mode if App Router detection fails.

[**Risk 3**] Agent decides "this className is wrong" and "fixes" it → fidelity gate fails → agent loops → **Mitigation:** design-bridge.md rule explicitly forbids className changes with examples; fidelity gate report names the failing route and shows the diff image so agent can localize the issue rather than guessing.

[**Risk 4**] Build-time content substitution becomes a maintenance burden as v0 changes its placeholder conventions → **Mitigation:** Substitution config is per-scaffold (not global), so different scaffolds can adapt independently. Use a flexible matcher (regex or AST visitor) rather than exact string replacement.

[**Risk 5**] Repo size growth from committing v0-export/ → **Mitigation:** No longer applicable — D1 changed to external git source with gitignored materialization. Set-core repo size unaffected by design content. The v0 source repo is itself an ordinary git repo and grows naturally with iteration history (acceptable since it lives outside set-core).

[**Risk 5b**] Network dependency for first import / unattended CI runs without auth → **Mitigation:** Clear actionable error messages on `git clone` exit 128 (auth fail): name the URL, list the auth options (SSH agent, `GITHUB_TOKEN`, deploy key), point to docs. ZIP fallback exists for fully air-gapped environments.

[**Risk 5c**] Private repo credentials accidentally committed (e.g., URL with embedded PAT) → **Mitigation:** scaffold.yaml schema documents that auth credentials should NOT be embedded in the URL field. Token-via-URL is supported but discouraged in favor of env vars. The cache key hashes the URL so credentials in URLs would not leak via cache directory naming.

[**Risk 6**] Removing Figma support breaks consumer projects mid-flight → **Mitigation:** This change announces BREAKING in proposal. Migration guide added to docs. set-project init detects projects with `.make` files and prints a migration error (not a silent failure). The change is gated behind explicit user approval — no auto-deploy.

[**Risk 7**] Agents over-refactor (split a v0 single-file page into 8 components) → **Mitigation:** design-bridge.md states the principle ("refactor only when a component is reused, not for aesthetic preference"); reviewer agents can flag over-fragmentation in code review.

[**Risk 8**] Gate flakiness (tests intermittently fail on visual diff) → **Mitigation:** retry policy (2 retries before final fail); diff threshold expressed as percent + absolute pixel count (so small images don't fail on 1px); collect failure screenshots into `gate-results/` for human review.

## Migration Plan

This change ships as **one atomic BREAKING merge** — no transitional feature flag, no parallel pipelines. Implementation follows a strict task ordering to avoid broken intermediate states (see tasks.md).

### Step 1 — Land Layer 1 ABC changes (must come first)
- Add new ABC methods (`detect_design_source`, `copy_design_source_slice(change_name, scope, dest_dir)`, `get_design_dispatch_context(change_name, scope, project_path)`) to `ProjectType`
- REMOVE old ABC methods (`build_per_change_design`, `build_design_review_section`, old `get_design_dispatch_context` signature)
- Update NullProfile + CoreProfile to no-op the new methods (return `"none"` / empty)
- Update dispatcher + engine + cli + verifier callers to remove `design_snapshot_dir` parameter
- After this step, the framework is "no design source" everywhere — Figma path is dormant code, v0 path doesn't exist yet
- Tests: Layer 1 tests pass (existing functionality unchanged); abstraction-guard test confirms no v0 imports in `lib/set_orch/`

### Step 2 — Implement Layer 2 v0 modules (web, isolated)
- Build `v0_importer`, `v0_manifest`, `v0_renderer`, `v0_fidelity_gate` modules under `modules/web/`
- Wire `WebProjectType` to use them; register `design-fidelity` gate
- Tests: unit tests for each module; integration test with a fixture v0-export

### Step 3 — Delete Figma pipeline files (after Layer 2 ready)
- Delete `lib/set_orch/design_parser.py`, `lib/design/fetcher.py`, Figma functions in `bridge.sh`, `bin/set-design-sync`
- Remove `_dp` import + `build_design_review_section` call from `verifier.py` (in the same commit as `design_parser.py` deletion to avoid broken-import window)
- Delete removed-capability spec folders (`design-make-parser`, `design-snapshot`, `design-spec-sync`, `design-brief-parser`, `design-brief-stem-match`)
- Update `templates/core/rules/design-bridge.md` to v0-only language
- Update `set-project init` to detect `.make` files and emit migration error

### Step 4 — Migrate craftbrew scaffold (validates the pipeline)
- Generate craftbrew design in v0.app using `docs/v0-prompts.md`
- Run `set-design-import` against scaffold
- Author `content-fixtures.yaml`, deploy via runner to consumer projects
- E2E run craftbrew end-to-end, verify fidelity gate passes
- Tune thresholds based on first real run

### Step 5 — Archive in-progress `v0-design-pipeline` change
- Move `v0-prompts.md` and any durable artifacts into this change's `docs/`
- Run `openspec archive v0-design-pipeline` with a "superseded by v0-only-design-pipeline" note

### Rollback strategy

This change is intentionally not designed for partial rollout — the BREAKING surface is too large to maintain a half-state. If the v0 pipeline proves unstable post-merge:
- Revert the entire merge (single PR / commit chain), restoring the previous Figma path from git history
- The Layer 1 ABC additions are forward-compatible; if rollback happens, the old methods (`build_per_change_design` etc.) are also restored
- For mitigations short of full revert, the fidelity gate has `warn_only: true` to disable blocking; the design source detection gracefully returns `"none"` if `v0-export/` is absent (so a project can disable v0 by removing its export)

## Open Questions

1. **Manifest scope-keyword matching algorithm:** simple substring match (current dispatcher pattern) or richer (token-frequency scoring, embedding similarity)? Simple substring is the pragmatic v1 choice, but craftbrew has 22 routes — collisions possible. **Default decision:** start with substring + explicit `scope_keywords` list per route in manifest (author-controlled), defer scoring algorithms to v2.

2. **Per-change design-source slice depth:** when copying scope-matched files, should we transitively follow imports (deeper traversal = more context for agent, larger slice) or stop at the manifest's declared `component_deps` (simpler, faster, but may omit transitively used utility files)? **Default decision:** stop at `component_deps` + `shared/**`; if agent is missing a util, the import error will fast-fail and we add it to the manifest.

3. **Fixture content discovery:** does `content-fixtures.yaml` live in scaffold/`docs/` or under `v0-export/_fixtures/`? Prefer **scaffold/`docs/`** because it's authored by humans (scaffold designer), not regenerated by importer.

4. **Existing in-progress `v0-design-pipeline` change:** the user explicitly chose to extend rather than archive. This change effectively SUPERSEDES it. Coordinate by: (a) merging v0-prompts.md from old to new, (b) closing old change with a "Superseded by v0-only-design-pipeline" note. Alternatively, delete the old change once this proposal is approved. **Default decision:** archive old change as superseded after this change's proposal lands.

5. **Should `design-brief.md` survive at all?** The scaffold may want a 1-page "vibe note" (brand personality, references, AVOID list) that informs prompt authoring but is NOT consumed by agents. Could live in `docs/v0-vibe.md` or stay as a stripped `design-brief.md`. **Default decision:** keep as `docs/design-brief.md` but mark non-authoritative; framework does not inject it into agent input.
