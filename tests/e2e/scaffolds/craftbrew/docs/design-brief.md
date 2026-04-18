# Design Brief — craftbrew (non-authoritative vibe note)

> **This file is non-authoritative.** Agents do NOT consume it. The design
> source of truth is `v0-export/` (materialized from the git repo declared
> in `scaffold.yaml`) plus `docs/design-manifest.yaml`.

## Brand feel

- Warm, earthy palette — rich coffee browns, cream, deep espresso accents
- Typography leans editorial — pairs a serif for hero headlines with a clean sans for body
- Photography-first hero sections; plenty of whitespace

## Avoid

- Neon / bright chromatic accents
- Tech-startup sans-serif maximalism
- Stock "generic coffee shop" photography

## Refactor latitude

When implementing, agents integrate v0's TSX into the Prisma/HU i18n
layer. Visual fidelity is enforced by the `design-fidelity` gate — see
`.claude/rules/design-bridge.md` for the refactor policy.
