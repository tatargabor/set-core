---
paths:
  - "src/components/**"
  - "src/app/**/*.tsx"
---
# Design Integration

These rules apply when a design source is present in the project. Detection
order:

1. **`v0-export/`** present in worktree (v0.app Next.js export) — **PRIMARY**.
   Follow `.claude/rules/design-bridge.md` for the integrator-not-rebuilder
   contract, strict shell-mounting rules, and the no-UX-pattern-reinterpretation
   rule. The design-fidelity gate enforces shell mounting + shadcn primitive
   parity automatically.
2. **Design MCP registered** (Figma, Penpot, Sketch, Zeplin) AND no
   `v0-export/` — query the MCP for frame specs before implementing.
3. **`docs/figma-raw/*/sources/`** present (Figma Make export) AND no
   `v0-export/` — those files are the ground-truth (Figma fallback).
4. **Neither** — agents self-gate (rare; treat the missing design as a
   `design_gap` ambiguity rather than guessing).

When `v0-export/` is present, sections below labelled "(Figma fallback)"
do NOT apply — the v0 source is canonical and `design-bridge.md` is the
contract.

## Before Implementing UI

- If `v0-export/` exists: read the matching v0 file at the path the
  manifest binds to your route/component (`docs/design-manifest.yaml`).
  Mount the shell components by canonical filename — see
  `.claude/rules/design-bridge.md`.
- Otherwise: query the design tool for the relevant frame/page before
  writing component code. If the required frame is MISSING from the
  design, flag it as a `design_gap` ambiguity — do not guess layout
  or styling.

## Design Token Mapping (Figma fallback)

When the project does NOT have `v0-export/`, tokens come from the Figma
spec and need to be wired to Tailwind by hand:

- Map design colors → `tailwind.config.ts` `theme.extend.colors` using CSS custom properties
- Map design spacing/sizing → Tailwind spacing scale or custom values in config
- Map design typography → `tailwind.config.ts` `theme.extend.fontFamily` / `fontSize`
- Map design shadows → `tailwind.config.ts` `theme.extend.boxShadow`
- For tokens not covered by Tailwind defaults, use CSS custom properties: `var(--token-name)`
- Token source of truth: `tailwind.config.ts` and `src/styles/tokens.*` — never hardcode values

When `v0-export/` is present, tokens already live in `v0-export/app/globals.css`
(deployed to your project's `src/app/globals.css`). Do NOT touch that file —
the token guard fires on any literal-color edit there.

## Component Mapping

- Map design components → shadcn/ui variants where a match exists
- Use existing shadcn/ui components before creating custom ones
- Match design states (hover, focus, disabled, error) to component variant props
- If a design component has no shadcn/ui equivalent, create in `src/components/` following the same pattern (Radix + Tailwind + `cn()`)
- **v0-export shell rule:** when a top-level shell exists in
  `v0-export/components/<X>.tsx`, mount it at `src/components/<X>.tsx`
  using the canonical kebab-case filename. Aliasing or renaming is a
  `shell-not-mounted` / `shadow-alias` violation. See `design-bridge.md`.

## Figma Source Files (Figma fallback only)

When `docs/figma-raw/*/sources/` exists AND no `v0-export/`, these files
contain actual component code extracted from the Figma design (via Figma
Make or similar). They are the ground-truth for:
- **Component structure**: exact layout hierarchy, container patterns, flex/grid usage
- **Icon usage**: which lucide-react icons appear in which components (e.g., `ShoppingBag` for cart)
- **Data model fields**: TypeScript interfaces with exact field names (e.g., `shortDescription`, `variants`)
- **Image patterns**: thumbnail dimensions, aspect ratios, placeholder usage

Rules:
- MUST read matched source files before implementing any UI component — the orchestrator injects relevant files into your context, but you can also read directly from `docs/figma-raw/*/sources/`
- Source filenames use `__` as path separators (e.g., `src__components__ProductCard.tsx` → `src/components/ProductCard.tsx`)
- When source files specify a particular icon, image size, or layout pattern, use it exactly — do not substitute with generic alternatives
- When source files contain `mockData.ts` or similar data files, use the exact field names and seed entity names from those files in your schema and seed data

## Responsive Behavior

- Check design for mobile/tablet/desktop breakpoint frames
- Map breakpoint-specific layouts to Tailwind responsive prefixes (`sm:`, `md:`, `lg:`)
- If only one breakpoint is designed, implement mobile-first and flag missing breakpoints
