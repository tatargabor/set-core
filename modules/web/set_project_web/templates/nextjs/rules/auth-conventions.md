---
paths:
  - "src/lib/auth*"
  - "src/middleware*"
  - "src/app/**/login/**"
  - "src/app/**/register/**"
  - "src/app/api/auth/**"
---
# Auth Conventions

## Auth Library
- Use NextAuth.js v5 (Auth.js) — `next-auth@5`
- Use `auth()` for server-side session, NOT `getServerSession()`
- Use `useSession()` for client-side session access

## Role Checking
- Define project roles in auth config (e.g., USER, ADMIN)
- Use centralized role check helpers — never compare role strings inline
- Protected server actions: check auth/role at the top, before any logic
- Protected pages: use middleware or layout-level auth checks

## API Route Authentication (CRITICAL — most common review failure)
- **EVERY** API route under `/api/admin/` MUST check auth before processing
- **EVERY** state-mutating API route (POST/PUT/DELETE) MUST verify authentication — no exceptions
- Do NOT create API endpoints and "add auth later" — auth is part of the endpoint, not an afterthought
- If a route handles sensitive data (gift cards, coupons, orders, user data), it MUST have auth even for GET
- Test: `curl` the endpoint without auth headers — it MUST return 401, never 200

## Middleware
- Protect routes selectively — specify exact matcher patterns
- Public routes (storefront, landing) must remain accessible
- Auth pages (login, register) must be accessible without auth

## Password & Credentials
- Passwords hashed with `bcrypt` (bcryptjs)
- Never log or expose password hashes
- JWT session strategy for stateless auth

## Edge Runtime Compatibility
- bcryptjs uses Node.js APIs (process.nextTick, setImmediate) — it CANNOT run in Edge Runtime
- Auth route handlers that use bcryptjs MUST set `export const runtime = 'nodejs'`
- Next.js middleware runs in Edge Runtime by default — do NOT import bcryptjs there
- For middleware auth checks, verify JWT/session tokens only (no password hashing)
- Password hashing (bcryptjs) belongs in API route handlers or Server Actions, never in middleware
