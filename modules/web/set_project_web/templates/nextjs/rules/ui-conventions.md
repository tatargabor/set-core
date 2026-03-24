---
paths:
  - "src/components/**"
  - "src/app/**/*.tsx"
---
# UI Conventions

## Component Stack
- Use shadcn/ui components as the base layer
- Import from `@/components/ui/` — never use raw Radix primitives directly
- Icons: use `lucide-react` exclusively
- When design source files (`docs/figma-raw/*/sources/`) specify particular icons (e.g., `ShoppingBag` for cart, `Package` for products), use those exact icons — design source files override generic icon choices

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

## File Size
- Components should stay under 400 lines
- Split large components: extract hooks, sub-components, or utilities
