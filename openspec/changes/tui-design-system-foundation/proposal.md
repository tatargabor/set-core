## Why

The dashboard already **has** a design system spec — `tui-design-system`, seven requirements,
archived from an earlier change. Three of them are violated in the tree today, and nothing
reports it:

| Requirement | Measured on `HEAD` (2026-07-31) |
|---|---|
| "No arbitrary font sizes (`text-[9px]`, `text-[10px]`, `text-[11px]`)" | **81 occurrences across 15 files** (44× `10px`, 31× `11px`, 6× `9px`) |
| "Zero `font-mono` usages outside Battle" | **34 occurrences** |
| *(status colour is not covered at all)* | **493 raw `text-<colour>-400` status classes across 47 files** |

```
grep -rho "text-\[[0-9]*px\]" --include='*.tsx' web/src | sort | uniq -c   # 81
grep -rn  "font-mono" --include='*.tsx' web/src | grep -v battle | wc -l   # 34
grep -rn  "text-blue-400\|text-green-400\|text-red-400\|text-yellow-400\|text-orange-400\|text-neutral-500" \
          --include='*.tsx' web/src | wc -l                                # 493
```

So the problem is not that the visual language is undecided. It is that the language lives in
prose and in one 80-line file (`web/src/components/tui.tsx`, imported by **6 of ~40 component
files**), while the other 34 files re-derive it by hand. Drift is invisible because nothing
measures it, and it compounds: every new screen copies whichever neighbour it was written next
to.

The visible cost is the Project Status screen. Its renderer is deliberately domain-free and
correct about that — but a nested value carries `min-w-[18rem]`
(`web/src/components/StatusValue.tsx:344`), so an object inside a table cell forces the table
past the viewport, and prose in a cell wraps into a 14-line tower. **Nesting decides the
width, not the content's length** — the same finding already recorded in
`.claude/rules/evidence-discipline.md`. A different visual style would render the identical
tower.

Now, because a decision was taken (2026-07-31) to keep the terminal/control-panel language
rather than migrate to a component library: the language is a differentiator, the audience is
developers plus occasional demos, and a future customer-facing surface will be its own surface
rather than a light skin of this one. That makes it worth investing in the language we have
instead of replacing it.

## What Changes

- **Semantic design tokens** replace raw colour classes. A `@theme` block in
  `web/src/index.css` (Tailwind v4 native) defines status and density tokens by *meaning*
  (`--color-status-done`, `--color-status-fail`, …), not by hue. Components stop naming
  `blue-400`.
- **`web/src/components/tui.tsx` becomes `web/src/components/tui/`** — a primitive module. The
  three existing primitives keep their behaviour and their names; the patterns currently
  hand-written in several places each (panel frame, chip, key/value list, tab strip, table
  frame, badge) become primitives with one implementation.
- **A drift test** (`web/tests/unit/`) fails the build when a banned pattern reappears: an
  arbitrary `text-[Npx]`, a `font-mono` outside Battle, or a raw status colour outside the
  token layer. The existing spec's three violated requirements become checkable rather than
  aspirational. The test states its own exemption list; an exemption is a line in the test,
  not a habit.
- **The 81 + 34 + 493 existing violations are migrated** to the tokens and preset sizes, so
  the drift test starts from zero rather than from a grandfathered baseline.
- **Project Status stops deciding width by nesting.** A nested object no longer carries a
  minimum width inside a table cell; a value too deep or too long for a cell moves to a row
  detail expansion instead of widening the row. The compacting rule already in
  `project-status-surface` continues to hold: whatever moves out of the cell says so where the
  reader is standing.
- **Headless behaviour for the three hand-rolled interactive patterns.** Measured: 2
  popover/dropdown sites, 3 modal sites, 4 tab strips — 12 `aria-*` attributes and 9
  `onKeyDown` handlers in ~20 000 lines. These get keyboard navigation, focus management and
  click-outside from Radix primitives, skinned as TUI. `title=`-based tooltips (58 sites) are
  **out of scope** — the native attribute is adequate and replacing it would be a large
  low-value change.

Not in this change: migrating the remaining screens (Orchestration tabs, Manager, Memory,
Settings) onto the primitives. That is the follow-up change; this one proves the primitives on
one screen.

**No BREAKING changes** — the dashboard is internal, and no consumer contract is touched.

## Capabilities

### New Capabilities
- `tui-primitives`: the shared component module — which primitives exist, what each guarantees
  about compacting and keyboard access, and the rule that a screen may not hand-roll one.

### Modified Capabilities
- `tui-design-system`: adds semantic tokens as the only sanctioned source of status colour,
  and makes the existing font-size / `font-mono` requirements enforced by a test rather than
  stated in prose.
- `project-status-surface`: adds a requirement that nesting depth never widens a row, and that
  a value displaced from a cell is announced where the reader is standing.

## Impact

- **Code:** `web/src/index.css`, `web/src/components/tui.tsx` → `web/src/components/tui/*`,
  `web/src/components/StatusValue.tsx`, `web/src/components/StatusTable.tsx`,
  `web/src/pages/ProjectStatus.tsx`, plus mechanical class replacement across the 47 files
  carrying raw status colours and the 15 carrying arbitrary font sizes.
- **Dependencies:** adds `@radix-ui/react-popover`, `@radix-ui/react-dialog`,
  `@radix-ui/react-tabs` to `web/package.json`. No component library, no `components.json`.
- **Tests:** new drift test under `web/tests/unit/`; the existing Playwright E2E suite
  (`web/tests/e2e/`) is the regression net for the Project Status layout change and must be run
  with a real project, per `CLAUDE.md`.
- **Not affected:** the API layer (`lib/set_orch/`, `modules/web/`), the status contract, and
  every consumer-facing path. This change is confined to `web/`.
- **Build product caution:** `web/` has a build output (`dist/`), and `CLAUDE.md` records that
  this path has *not* been measured for the generated-artefact hybrid problem. Verification runs
  against a freshly built bundle, not a cached one.
