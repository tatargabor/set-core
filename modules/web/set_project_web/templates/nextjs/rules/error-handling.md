---
paths:
  - "src/app/**/error.tsx"
  - "src/app/**/not-found.tsx"
  - "src/app/global-error.tsx"
  - "src/app/**/loading.tsx"
---
# Error Handling Conventions

## Required Error Boundary Files
Every Next.js app MUST have these three files at the root `src/app/` level:
- `error.tsx` — catches route-level runtime errors (MUST be `"use client"`)
- `global-error.tsx` — catches root layout errors (MUST include own `<html>` and `<body>` tags)
- `not-found.tsx` — global 404 page

## Route-Specific Error Pages
- Add `not-found.tsx` in dynamic route segments for resource-specific 404s (e.g., `app/[locale]/products/[id]/not-found.tsx`)
- Call `notFound()` from server components when a resource doesn't exist — never return a 200 with "not found" message

## Error Page Content
- Show a user-friendly message with a clear action (retry, go home, contact support)
- Include a "Try again" button in `error.tsx` using the `reset()` prop
- Never expose stack traces, internal error details, or database errors to the user
- Log full error details server-side for debugging

## Loading States
- Add `loading.tsx` in route segments that fetch data — enables streaming SSR
- Use skeleton components matching real content layout to prevent CLS
- For nested layouts, place `loading.tsx` at the appropriate level — it applies to all child routes

## Server Action Error Pattern
- Call `redirect()` OUTSIDE the `try/catch` block — redirect works by throwing
- Return structured errors `{ success: false, error: string, field?: string }` — never throw from actions
- For multi-step forms: include which step has the error in the response
