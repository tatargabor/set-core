# [SUPERSEDED by openspec/changes/v0-only-design-pipeline]

This change is superseded by `v0-only-design-pipeline`, which treats the v0
export as the authoritative design source (not a markdown brief). The
`v0-prompts.md` authored here was copied to
`openspec/changes/v0-only-design-pipeline/docs/v0-prompts.md`.

Archive this change once the new proposal is approved.

---

# Proposal: Replace Figma Make with v0.dev Design Pipeline

## Why

The current design authoring pipeline uses Figma Make to generate a `.make` binary that `set-design-sync` parses into `design-system.md` + `design-brief.md`. This flow has three problems exposed during craftbrew-run-20260415-1225:

1. **Token mismatch**: Figma uses its own naming (`color-muted`) while shadcn/ui expects specific pairs (`--muted` + `--muted-foreground`). The `.make` parser produced identical values for `muted` and `muted-foreground`, causing invisible text in tabs and sidebar labels (bugs 08, 09).

2. **Missing states**: Figma frames did not define interactive component states (hover, selected, disabled, focus). This led to variant selectors with indistinguishable states (bug 07) and tab labels that blended into the background (bug 08).

3. **Unreviewable binary**: The `.make` file is a 3.9MB binary ZIP. It cannot be diffed, reviewed, or version-controlled meaningfully. Duplicate sections in the generated `design-brief.md` (~150 lines) went unnoticed because the source was opaque.

Since the orchestration agents work from **markdown specs** (design-brief.md) and **CSS variables** (globals.css), and all UI components are shadcn/ui, the Figma layer adds complexity without value. The design-brief.md + globals.css combination already proved to be the most useful artifacts — agents never read Figma files directly.

**v0.dev** (Vercel) generates shadcn/ui + Tailwind + Next.js code from text prompts with live visual preview. Its output is native to our stack — no translation layer needed.

## What Changes

### Scaffold changes (craftbrew)

1. **Remove `docs/design.make`** — the 3.9MB Figma binary is no longer needed
2. **Remove `docs/design-system.md`** — replaced by `globals.css` as the single source of truth for tokens. The design-brief.md already references token values directly.
3. **Keep `docs/design-brief.md`** — this remains the primary visual spec for agents, now authored from v0.dev visual output instead of Figma Make output
4. **Keep `shadcn/globals.css`** — already deployed by the runner; becomes the canonical token source
5. **Add `docs/v0-prompts.md`** — reference document with per-page v0.dev prompts so designs can be regenerated or iterated

### Pipeline changes

6. **`run-craftbrew.sh`** — Remove the `set-design-sync` step that converts `.make` → `design-system.md`. The runner already deploys globals.css and copies design-brief.md directly.
7. **`bridge.sh` `design_context_for_dispatch()`** — When `design-system.md` is absent, extract tokens directly from `globals.css` CSS custom properties. This is a fallback, not a replacement — projects with design-system.md still work.
8. **`design-bridge.md` rule** — Update to reflect that `design-system.md` is optional when `globals.css` provides the tokens.

### Not changing

- `design_parser.py` MakeParser — kept for backward compatibility (projects that still use .make)
- `design_brief_for_dispatch()` — already works with design-brief.md directly, no changes needed
- `build_per_change_design()` — already scope-matches from design-brief.md, no changes needed
- `shadcn-ui-design-connector` change — complementary (runtime token extraction from existing project files)

## New Workflow

### For scaffold authors (one-time per scaffold)

```
1. Define theme tokens in globals.css (shadcn CSS variables)
2. Open v0.dev → paste theme + page description → iterate visually
3. Screenshot as reference, extract layout patterns into design-brief.md
4. Commit design-brief.md + globals.css to scaffold
```

### For orchestration runs (automated, unchanged)

```
design-brief.md + globals.css
    ↓ dispatcher
per-change design.md (scope-matched pages + tokens)
    ↓ agent
implementation using shadcn/ui components
    ↓ verify gate
design compliance check (token values in code vs spec)
```

## Impact

- **Scaffold (`tests/e2e/scaffolds/craftbrew/`)**: Remove 2 files (.make, design-system.md), add 1 file (v0-prompts.md)
- **Runner (`tests/e2e/runners/run-craftbrew.sh`)**: Remove ~15 lines (set-design-sync invocation, Figma URL extraction)
- **Bridge (`lib/design/bridge.sh`)**: Add globals.css token extraction fallback (~30 lines)
- **Rule (`templates/core/rules/design-bridge.md`)**: Update documentation
- **No breaking changes**: Projects with .make files and design-system.md continue to work unchanged
