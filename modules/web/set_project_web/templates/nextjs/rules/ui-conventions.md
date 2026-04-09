---
paths:
  - "src/components/**"
  - "src/app/**/*.tsx"
---
# UI Conventions

## Component Stack
- Use shadcn/ui components as the base layer
- Import from `@/components/ui/` — never use raw Radix primitives directly
- Install shadcn components ON DEMAND — only add a component when first needed. Do NOT pre-install unused primitives
- Base set (always available after foundation change): Button, AlertDialog
- Icons: use `lucide-react` exclusively
- When design source files (`docs/figma-raw/*/sources/`) specify particular icons (e.g., `ShoppingBag` for cart, `Package` for products), use those exact icons — design source files override generic icon choices

## Design Tokens — Use Tailwind Classes, Not Inline Hex

The project's `src/app/globals.css` defines brand colours, radii, and typography as Tailwind `@theme` tokens. Every visual primitive on the page MUST reach those tokens through the generated Tailwind class names — NEVER inline the raw hex value with arbitrary-value syntax like `bg-[#78350F]`.

**Wrong — inline hex, bypasses the token layer:**
```tsx
<button className="bg-[#78350F] hover:bg-[#78350F]/90 text-white rounded-[6px]">
  Add to Cart
</button>
<div className="bg-[#FFFBEB] text-[#1c1917]">...</div>
```
This "works" visually but it means:
- A design refresh (flipping the primary to a new brown) requires a project-wide search-replace.
- Dark mode / theming is impossible — there's no indirection.
- Agents copy the hex as a literal instead of "the primary colour," so half the site uses `#78350F` and the other half uses `#78350f` (same value, different token-space).

**Correct — tailwind classes that resolve to the `@theme` tokens:**
```tsx
<button className="bg-primary hover:bg-primary/90 text-primary-foreground rounded-button">
  Add to Cart
</button>
<div className="bg-background text-text-primary">...</div>
```

**The rule:** if a CSS value you want to write already exists as a `--color-*` / `--radius-*` / `--font-*` token in `src/app/globals.css @theme`, you MUST use the corresponding Tailwind class (`bg-primary`, `text-muted`, `rounded-card`, etc.) — not the inline `[#HEX]` form. The inline form is only acceptable for one-off values that are deliberately NOT part of the token system.

**Detection:** grep for `\[#[0-9a-fA-F]{6}\]` in `src/` — any match that corresponds to a value already in `globals.css @theme` is a rule violation and the review gate will flag it.

## Feature Component Location
- Co-locate feature-specific components with their route segment (e.g., `src/app/admin/(dashboard)/products/ProductsTable.tsx`)
- NEVER create `src/components/admin/`, `src/components/shop/`, or other domain directories
- `src/components/` is ONLY for:
  - `ui/` — shadcn primitives
  - Truly shared components used across both storefront and admin (e.g., `ImageWithFallback.tsx`)

## Layout Patterns
- Page layout: consistent header/content structure
- Use responsive containers — never hardcode pixel widths
- Mobile-first: design for small screens, enhance for larger
- All pages within a route group MUST use the shared layout — never create page-level wrappers that replace the route group layout sidebar/nav
- Admin pages must always render within the admin layout (`app/admin/layout.tsx`) — if the sidebar disappears on a sub-page, the layout nesting is broken

## shadcn-First — No Raw HTML Form Elements

Every interactive primitive on the page MUST be a shadcn/ui component, never a raw HTML element with hand-rolled Tailwind classes. The exception is static layout elements (`<div>`, `<section>`, `<header>`, `<main>`, etc.) — those are fine.

**Required replacements — always use the shadcn version:**

| Raw HTML | shadcn/ui equivalent |
|---|---|
| `<button>`, `<a>` styled as button | `<Button>` from `@/components/ui/button` |
| `<input type="text|email|password|number|search">` | `<Input>` |
| `<input type="checkbox">` | `<Checkbox>` |
| `<input type="radio">` | `<RadioGroup>` + `<RadioGroupItem>` |
| `<select>` | `<Select>` + `<SelectTrigger>` + `<SelectContent>` + `<SelectItem>` |
| `<textarea>` | `<Textarea>` |
| `<label>` | `<Label>` |
| `<hr>` | `<Separator>` |
| `<table>` | `@tanstack/react-table` + shadcn `<Table>` |
| Modal via `role="dialog"` | `<Dialog>` / `<AlertDialog>` / `<Sheet>` |
| Toast via `alert()` or custom | `toast()` from `sonner` |
| Tooltip via `title=""` | `<Tooltip>` + `<TooltipTrigger>` + `<TooltipContent>` |
| Badge via `<span>` | `<Badge>` |
| Tab via custom state | `<Tabs>` + `<TabsList>` + `<TabsTrigger>` + `<TabsContent>` |
| Accordion via `<details>` | `<Accordion>` |
| Avatar via `<img>` | `<Avatar>` + `<AvatarImage>` + `<AvatarFallback>` |
| Skeleton via custom animation | `<Skeleton>` |
| Progress via custom bar | `<Progress>` |

**Wrong — raw button with Tailwind classes:**
```tsx
<button
  className="px-4 py-2 bg-primary text-primary-foreground rounded-button hover:bg-primary/90"
  onClick={handleSubmit}
>
  Save
</button>
```

**Correct — shadcn Button with `variant`:**
```tsx
import { Button } from "@/components/ui/button";

<Button variant="default" onClick={handleSubmit}>
  Save
</Button>
```

**Why this matters**:
1. **Accessibility**: shadcn components ship with keyboard navigation, focus states, ARIA attributes, and `aria-disabled` handling. A raw `<button>` with `disabled` class but no `aria-disabled` fails the accessibility gate.
2. **Consistency**: a site with 8 pages using 7 different custom button styles looks cheap. Using `<Button variant="...">` guarantees visual + interactive consistency.
3. **Design system evolution**: if the design team flips primary colours or border radii, changing the `@theme` tokens updates every shadcn component automatically. Hand-rolled buttons stay stuck on the old values.
4. **Review gate**: the review gate flags raw `<button>` usage as a finding — saving you one retry round.

**Install on demand**: run `npx shadcn@latest add <component>` when you first need a component. Don't pre-install everything.

## Button Variant Policy
- `variant="ghost"` → icon-only, NO text content
- `variant="outline"` → secondary actions with text
- `variant="default"` → primary actions
- `variant="destructive"` → delete/remove actions, always with confirmation dialog

## Table Conventions
- Use `@tanstack/react-table` via shadcn DataTable
- Include loading skeleton states
- Pagination server-side for datasets > 50 rows

## Dialog Patterns
- Use shadcn `Dialog` component
- Forms inside dialogs follow Pattern A (see functional-conventions)
- Dialogs close on successful submit, stay open on error
- Confirmation dialogs for destructive actions

## Components by Default
- All components are Server Components by default
- Add `"use client"` only when needed: event handlers, hooks, browser APIs
- Keep client components small — extract data fetching to server parents

## Responsive Design
- Breakpoints: `sm` (640px), `md` (768px), `lg` (1024px), `xl` (1280px)
- Mobile-first: write base styles for mobile, add `md:` / `lg:` for larger screens
- Grid layouts: 1 column mobile → 2 columns tablet → 3-4 columns desktop
- Navigation: hamburger menu with drawer on mobile, horizontal nav on desktop
- Modals: full-screen sheet on mobile (`<Sheet>`), centered dialog on desktop (`<Dialog>`)
- Tables: horizontal scroll wrapper on mobile, or switch to card layout

## Toast & Notifications
- Use shadcn `toast` (sonner) for transient feedback — auto-dismiss after 5s
- Success: green toast, no action needed
- Error: red toast, persists until dismissed, include retry action if applicable
- Never use `alert()` or `window.confirm()` — use shadcn Dialog for confirmations

## Loading & Empty States
- Use skeleton components (shadcn `Skeleton`) during data loading — match the shape of real content
- Show meaningful empty states with icon + message + action (e.g., "No orders yet" + link)
- Use `loading.tsx` for route-level streaming — shows shell immediately
- Disable submit buttons during form submission — show spinner icon

## No Placeholder Content
- Components MUST render real data using real sub-components — never placeholder `<div>`s with "coming soon" text
- Product grids MUST use `ProductCard`, featured sections MUST use actual components — not hardcoded divs with dummy content
- If seed data exists for an entity, use it. If data doesn't exist yet, show a proper empty state (icon + message + action)
- "Coming soon" or "full content placeholder" text is not acceptable in delivered code — either implement the feature or show an empty state

## Navigation Integrity
- Every navigation link (header, footer, sidebar, CTA buttons) MUST point to an existing route
- Broken links (404) are gate failures — verify all links resolve to real pages
- When adding footer/header links, check that the target page exists in the app router
- CTA buttons ("Go to checkout", "View subscription") must use correct localized paths if i18n is enabled

## File Size
- Components should stay under 400 lines
- Split large components: extract hooks, sub-components, or utilities
