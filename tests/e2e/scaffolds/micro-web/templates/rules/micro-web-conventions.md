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

- Minimal: `next`, `react`, `react-dom`, `tailwindcss` only
- No Prisma, no NextAuth, no bcrypt, no form libraries
- No shadcn/ui — use plain Tailwind classes for styling

## Forms

- Contact form: client-side validation only (required fields, email format)
- Form validation in `src/lib/validation.ts`
- No server action, no API route — form shows success message client-side
- Unit test for validation logic in `src/__tests__/validation.test.ts`

## Navigation

- Shared header component with nav links to all pages
- Active link highlighting based on current pathname
- Mobile responsive: hamburger menu on small screens
