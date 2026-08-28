## Why

`openspec/specs/figma-source-dispatch/spec.md` is a **live capability spec for a function
that no longer exists**. Every one of its six requirements names `design_sources_for_dispatch()`,
which was deleted on 2026-04-27 by `openspec/changes/archive/2026-04-27-v0-only-design-pipeline/tasks.md:113`
(task 7.5) — and the file that held it, `lib/design/bridge.sh`, is gone along with the whole
`lib/design/` directory. The spec's own Purpose line says how it got back:
`TBD — restored after delta-sync structural cleanup`. The code left; a structural delta-sync
put the spec back; it has stood as a published contract ever since.

The fail direction is what makes this worth a change rather than a shrug: nothing is missing.
The framework **publishes a capability it stopped standing behind four months ago**, and
anyone opening `openspec/specs/` reads it as current. It was found by a peer agent from
another project tracing this repo's Figma provenance — from the outside, which is exactly who
a published spec is for. Two dead carriers came up with it: a 700-line fetch script and a
four-file test fixture, both with zero live references.

## What Changes

- **BREAKING (contract): remove the `figma-source-dispatch` capability.** All six requirements
  are withdrawn, not reworded — the mechanism they describe does not exist. `openspec/specs/figma-source-dispatch/`
  is deleted; the change's own delta spec records the removal and the reason.
- **Delete `scripts/fetch-figma-design.py`** (700 lines). `grep -rn 'fetch-figma-design'` over
  the tracked tree finds only its own docstring and archived change documents.
- **Delete `tests/fixtures/figma-raw/TEST/sources/*.tsx`** (4 files). No `.py`, `.sh`, `.ts` or
  `.js` file references them; the test they were built for (`design-fidelity-bridge` task 7.2)
  exercised the deleted function.
- **Correct the presentation's stale claim.** The slide titled `Spec + Figma Design` and its
  speaker note (`set-design-sync extracts Figma tokens → design-system.md`) still assert a
  mechanism `docs/roadmap.md` itself records as dropped. The slide text is corrected; the
  images stay.

## What Explicitly Does NOT Change

Both of these look like Figma leftovers and are not. Naming them here is the point of the
change, because the obvious next step after "retire the Figma legacy" is to delete them.

- **The 4 archived figma-named change files stay** (in two archived changes totalling 11 files) (`openspec/changes/archive/2026-03-15-figma-direct-fetch/*`,
  `openspec/changes/archive/2026-03-15-design-fidelity-bridge/specs/figma-source-dispatch/spec.md`).
  They are the only record of **why** the Figma MCP path was dropped — instability, auth
  failures, and the same MCP producing radically different output four seconds apart. That
  finding is already being used as input by another project deciding its own design pipeline.
  An archive that loses the rejected path keeps only the answer and throws away the reasoning.
- **`docs/images/auto/figma/{product-detail,storefront}-design.png` stay — they are LIVE build
  input**, not history. `scripts/build-presentation.py:298` passes `storefront-design.png` to a
  slide, and `docs/presentation/set-core-presentation.md:326`, `set-core-bemutato.md:347` and
  both generated `.html` files embed it. Deleting them breaks the presentation build.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `figma-source-dispatch`: **removed in full.** All six requirements (source discovery, UI
  primitive exclusion, scope matching, output format, the 300-line budget, shared data files)
  are withdrawn — every one of them specifies a function deleted with the v0-only design
  pipeline.

## Impact

- **Specs:** `openspec/specs/figma-source-dispatch/` deleted (6 requirements, 9 scenarios).
- **Code:** `scripts/fetch-figma-design.py` deleted. No import, no caller, no test — verified
  by grep over the tracked tree.
- **Tests:** `tests/fixtures/figma-raw/TEST/sources/` deleted (4 fixture files). No test loads
  them; the suite's pass/fail set must be unchanged by this.
- **Docs:** two presentation source files and their generated HTML carry corrected slide text.
  `scripts/build-presentation.py` keeps its image reference and keeps building.
- **Not affected:** `lib/`, `modules/`, `bin/`, `web/` — nothing there references any of it.
- **If the capability is ever wanted again**, it is adopted from a project that runs a working
  local `.fig` decode path, not restored from this repo's dead version. That is the standing
  direction for this integration: the framework catches up to a mechanism proven elsewhere
  rather than reviving its own abandoned one.
- **Register:** closes `B-101` in `openspec/bugs/README.md`.
