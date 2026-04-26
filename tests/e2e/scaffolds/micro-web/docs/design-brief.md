# Design Brief — v0 Pattern Map

This file is a **navigator**, not a visual spec. The authoritative visuals
live in the v0 design source (cloned into `v0-export/` at run time, see
`scaffold.yaml::design_source`).

If `v0-export/` is present in your worktree, treat its files as visual truth
and follow `.claude/rules/design-bridge.md`. This document only points the
planner at the distinctive UX patterns the v0 design uses, so spec
decomposition can plan for them.

## Distinctive shadcn primitives expected in v0

These are not standard form controls — each one has a specific UX contract
that the implementation MUST preserve. The fidelity gate's
`shadcn-primitive-missing` check fails verify if any of these appear in
`v0-export/` but no `src/` file imports them.

| Primitive | Where it appears | What it replaces |
|---|---|---|
| `CommandDialog` (+ `CommandInput`, `CommandItem`, `CommandGroup`) | Global — Cmd+K palette in header (all pages) | Plain `Input` with dropdown |
| `Sheet` (+ `SheetContent`, `SheetTrigger`) | Mobile nav drawer (header on small viewport) AND newsletter signup CTA on home page | `Dialog` modal |
| `HoverCard` (+ `HoverCardContent`, `HoverCardTrigger`) | Team member avatars on About page; author avatars on Blog list | `Tooltip` (label-only) |
| `Dialog` with multi-step content | Contact form ("Get in touch" CTA opens it) — 3 steps inside a single dialog | Sequential pages |
| `Combobox` | Contact form: Subject field (typed search + category select fused). Blog list: filter bar | Two separate `Select` widgets |
| `Progress` | Blog detail: reading progress bar (sticky top) | No indicator |
| `Breadcrumb` | Blog detail: navigation trail | Plain "← Back" link |
| `Popover` (+ `PopoverContent`, `PopoverTrigger`) | Blog detail: reactions/share button row | Inline buttons |

## Page → primitive map

Per page, the implementation MUST mount these primitives. If you don't see
them in the v0 source, escalate as a scaffold-author bug; do not invent a
substitute.

- **Home (`/`):** Header with Cmd+K trigger button, hero, features grid
  (3× `Card`), newsletter Sheet trigger, footer
- **About (`/about`):** Header, page title, team grid with `HoverCard` per
  member, footer
- **Contact (`/contact`):** Header, "Get in touch" CTA → Dialog wizard
  (3 steps with stepper + Combobox in step 2 + Toast on submit), footer
- **Blog (`/blog`):** Header, page title, Combobox filter bar, post list
  (`Card` + `Badge` + `HoverCard` for author), footer
- **Blog detail (`/blog/[slug]`):** Header, sticky `Progress`, `Breadcrumb`,
  article content, reactions row (`Popover`), back link, footer

## Data still hardcoded — no schema work

The functional contract is unchanged from `spec.md`: 3 hardcoded blog posts,
3 hardcoded team members, contact form is `console.log` + toast. The point
of this scaffold is to test design-fidelity tracking with minimal functional
distraction. Don't add a database, don't wire up real forms — just mount the
v0 components and pass through the hardcoded data.

## Tokens

The v0 export ships its own `app/globals.css` with shadcn theme tokens
(framework auto-syncs to a generated `design-system.md`). Use those tokens
exclusively — do NOT hardcode hex/rgb literals in TSX/CSS. The token guard
will catch literal colors in newly added code.
