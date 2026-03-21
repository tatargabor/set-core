---
paths:
  - "src/middleware*"
  - "next.config*"
  - "src/app/api/**"
  - "src/actions/**"
---
# Security Conventions

## Security Headers
Set the following headers via `next.config.js` headers or middleware:
- `Strict-Transport-Security: max-age=63072000; includeSubDomains; preload` (HSTS)
- `X-Content-Type-Options: nosniff`
- `X-Frame-Options: DENY`
- `Referrer-Policy: strict-origin-when-cross-origin`
- `Permissions-Policy: camera=(), microphone=(), geolocation=()` (disable unused browser APIs)

## Content Security Policy (CSP)
- Start strict: `default-src 'self'` and relax as needed
- Use nonce-based CSP via middleware for dynamic pages
- Never use wildcard `*` in CSP directives
- Allow inline styles for shadcn/ui if needed: `style-src 'self' 'unsafe-inline'`
- Test CSP before deploy — browser console shows violations

## CORS
- Do NOT set CORS headers unless the API is explicitly cross-origin
- If needed, be specific with allowed origins — never use `Access-Control-Allow-Origin: *` on authenticated endpoints
- Configure per API route, not globally

## Rate Limiting
- Apply rate limiting to sensitive endpoints: login, password reset, registration, OTP
- Use sliding window or token bucket algorithm (e.g., `@upstash/ratelimit`)
- Return `429 Too Many Requests` with `Retry-After` header when limits exceeded
- Stricter limits on auth endpoints (e.g., 5 attempts/min), relaxed on read endpoints

## Input Validation
- Validate ALL user input server-side with `zod` — client validation is UX, not security
- Sanitize user-generated HTML if rendering with `dangerouslySetInnerHTML` (use `dompurify`)
- Never interpolate user input into SQL — Prisma parameterizes by default, but avoid `$queryRaw` with string interpolation

## NEXT_PUBLIC_ Prefix
- Never prefix secrets with `NEXT_PUBLIC_` — these values are inlined into the client bundle at build time
- Only use `NEXT_PUBLIC_` for non-sensitive, client-safe values (site URL, feature flags)
- Access secrets only in server-side code (Server Components, API routes, Server Actions)

## Secret Code Enumeration Prevention
Endpoints accepting secret codes (gift cards, coupons, invite codes, reset tokens) MUST return a single generic error for all failure cases. Never distinguish "not found" vs "expired" vs "already used" in the response — this lets attackers enumerate valid codes. Log the specific reason server-side.

```typescript
// WRONG: distinct errors reveal code validity
if (!gc) return Response.json({ error: "Gift card not found" }, { status: 404 })
if (gc.balance <= 0) return Response.json({ error: "No balance" }, { status: 400 })

// CORRECT: single generic error
if (!gc || gc.balance <= 0 || gc.expiresAt < new Date()) {
  return Response.json({ error: "Invalid or expired gift card" }, { status: 400 })
}
```
