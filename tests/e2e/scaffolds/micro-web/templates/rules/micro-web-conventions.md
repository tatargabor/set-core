---
description: Micro Web static site project conventions
globs:
  - "src/**"
---

# Micro Web Conventions

## Project Scope

This is a minimal static website — no database, no authentication, no API routes.

## Pages

- Home (`/`) — hero section with project name, brief description
- About (`/about`) — static content, team or company info
- Blog (`/blog`) — list of hardcoded blog posts from a data file
- Blog Post (`/blog/[slug]`) — individual post detail page
- Contact (`/contact`) — form with client-side validation only

## Data

- Blog posts: hardcoded array in `src/lib/blog-data.ts` (not a database)
- Each post: `{ slug, title, date, excerpt, content }` — content is plain text or simple HTML
- No API endpoints — all data is static/imported

## Dependencies

- Core: `next`, `react`, `react-dom`, `tailwindcss`
- UI: `shadcn/ui` — install components with `npx shadcn@latest add <component>`
- shadcn/ui utilities: `clsx`, `tailwind-merge`, `class-variance-authority`, `lucide-react` (pre-installed)
- No Prisma, no NextAuth, no bcrypt, no form libraries

## UI Components

- ALL UI components MUST use shadcn/ui: Button, Card, Input, Label, Textarea, Sheet, etc.
- Import from `@/components/ui/<component>` — install first if not present
- Use `cn()` from `@/lib/utils` for conditional class merging
- Do NOT use plain HTML `<button>`, `<input>` — always use shadcn equivalents
- Do NOT delete `components.json` or `src/lib/utils.ts` — these are required

## Forms

- Contact form: client-side validation only (required fields, email format)
- Form validation in `src/lib/validation.ts`
- No server action, no API route — form shows success message client-side
- Unit test for validation logic in `src/__tests__/validation.test.ts`

## Navigation

- Shared header component with nav links to all pages
- Active link highlighting based on current pathname
- Mobile responsive: hamburger menu on small screens

## See also — universal web anti-patterns

The framework-level `rules/web-conventions.md` (deployed by `set-project init`)
codifies e2e-failure-prone anti-patterns that apply to every web scaffold:

1. Never `navigator.sendBeacon` for cart/order mutations — await `fetch()` instead.
2. Upsert with composite unique key that includes the owning entity (userId/recipientEmail).
3. `data-testid="<feature>-<element>"` naming, kept in sync between component and test.
4. Use Playwright `storageState` via `lib/auth/storage-state.ts` for admin auth.
5. Annotate e2e spec files with `// @REQ-...` tags so the orchestrator can
   attribute failing tests to their owning change.

These apply here too — follow them alongside this scaffold's specific rules.
