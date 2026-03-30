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
