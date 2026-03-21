---
paths:
  - "src/components/**"
  - "src/app/**/*.tsx"
---
# Design Integration

These rules apply when a design MCP (e.g., Figma) is registered. If no design tool is available, skip this file — agents self-gate.

## Before Implementing UI

- Query the design tool for the relevant frame/page before writing component code
- If the required frame is MISSING from the design, flag it as a `design_gap` ambiguity — do not guess layout or styling

## Design Token Mapping

- Map design colors → `tailwind.config.ts` `theme.extend.colors` using CSS custom properties
- Map design spacing/sizing → Tailwind spacing scale or custom values in config
- Map design typography → `tailwind.config.ts` `theme.extend.fontFamily` / `fontSize`
- Map design shadows → `tailwind.config.ts` `theme.extend.boxShadow`
- For tokens not covered by Tailwind defaults, use CSS custom properties: `var(--token-name)`
- Token source of truth: `tailwind.config.ts` and `src/styles/tokens.*` — never hardcode values

## Component Mapping

- Map design components → shadcn/ui variants where a match exists
- Use existing shadcn/ui components before creating custom ones
- Match design states (hover, focus, disabled, error) to component variant props
- If a design component has no shadcn/ui equivalent, create in `src/components/` following the same pattern (Radix + Tailwind + `cn()`)

## Figma Source Files

When `docs/figma-raw/*/sources/` exists in the project, these files contain actual component code extracted from the Figma design (via Figma Make or similar). They are the ground-truth for:
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
