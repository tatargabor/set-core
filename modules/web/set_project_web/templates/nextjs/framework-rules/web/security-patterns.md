---
description: Web security patterns — authorization, input validation, session handling
globs:
  - "src/**/*.{ts,tsx,js,jsx}"
  - "app/**/*.{ts,tsx,js,jsx}"
  - "pages/**/*.{ts,tsx,js,jsx}"
  - "api/**/*.{ts,tsx,js,jsx,py}"
  - "routes/**/*.{ts,tsx,js,jsx,py}"
  - "server/**/*.{ts,tsx,js,jsx,py}"
  - "lib/**/*.{ts,tsx,js,jsx,py}"
---

# Web Security Patterns

These patterns apply to any web project (React, Next.js, Express, Django, FastAPI, etc.).

## 1. Authorization on Mutations (IDOR Prevention)

Every mutation (create/update/delete) that uses a client-provided ID MUST verify ownership.

**Wrong — trusts client ID blindly:**
```
// DELETE /api/cart/:id
await db.cartItem.delete({ where: { id: params.id } })
```

**Correct — scopes by authenticated entity:**
```
// DELETE /api/cart/:id
const session = await getSession(req)
await db.cartItem.delete({
  where: { id: params.id, sessionId: session.id }  // ownership check
})
```

**The rule:** `where` clauses on mutations by client-provided ID MUST include the owning entity (userId, sessionId, orgId, etc.) — never just `{ id: clientId }`.

## 2. Route Protection / Auth Guards

Protected routes MUST enforce authentication BEFORE the handler runs, not inside it.

**Wrong — auth check inside handler (easy to forget):**
```
export async function GET(req) {
  const user = getUser(req)
  if (!user) return redirect('/login')  // handler already started
  // ...
}
```

**Correct — middleware/guard at the routing level:**
```
// middleware.ts / auth decorator / route guard
if (isProtectedRoute(path) && !isAuthenticated(req)) {
  return redirect('/login')  // never reaches handler
}
```

**The rule:** auth checks belong in middleware, decorators, or route guards — not in individual route handlers. If the framework supports middleware (Express, Next.js, Django, FastAPI), use it.

## 3. Input Validation at Boundaries

All user input (form data, query params, URL params, request body) MUST be validated at the entry point.

**Validate:**
- Type (string vs number vs array)
- Range/length (min/max, string length limits)
- Format (email, URL, UUID patterns)
- Enumeration (allowed values for status fields, sort orders)

**Where to validate:**
- API route handlers (before business logic)
- Server Actions / form handlers (before DB operations)
- URL/query parameters (before use in queries)

Use schema validation (Zod, Yup, Pydantic, marshmallow) rather than manual checks.

## 4. Session/Cookie Security

- Session tokens in httpOnly cookies (not localStorage) when the framework supports it
- Set `SameSite` attribute (Lax or Strict) on auth cookies
- Never expose session IDs in URLs or client-side JavaScript
- Validate session on every protected request, not just at login

## 5. Data Scoping for Multi-User Features

Every query that returns user-specific data MUST include the owning entity in the WHERE clause.

**Wrong:**
```
// GET /api/orders/:id
const order = await db.order.findUnique({ where: { id: params.id } })
```

**Correct:**
```
// GET /api/orders/:id
const order = await db.order.findUnique({
  where: { id: params.id, userId: currentUser.id }
})
```

**List endpoints too:**
```
// GET /api/orders — always scope
const orders = await db.order.findMany({ where: { userId: currentUser.id } })
```

## 6. XSS Prevention

- Never use `dangerouslySetInnerHTML` / `v-html` / `| safe` with user-supplied content
- If rich text is required, use a sanitizer (DOMPurify, bleach)
- CSP headers are a defense-in-depth layer — not a substitute for output encoding

### JSON-LD / Structured Data XSS

`<script type="application/ld+json">` is a common XSS sink because raw `JSON.stringify()` output can break out of the script tag if any field contains `</script>` or HTML-significant characters.

**Wrong — raw stringify in dangerouslySetInnerHTML:**
```typescript
<script type="application/ld+json"
  dangerouslySetInnerHTML={{ __html: JSON.stringify(jsonLd) }} />
```

If any field of `jsonLd` ever contains attacker-controlled text (product name, review body, story title), this is a script-tag breakout.

**Correct — escape `<`, `>`, `&` and use React 19 script children:**
```typescript
function SafeJsonLd({ data }: { data: Record<string, unknown> }) {
  const json = JSON.stringify(data)
    .replace(/</g, "\\u003c")
    .replace(/>/g, "\\u003e")
    .replace(/&/g, "\\u0026")
  return <script type="application/ld+json">{json}</script>
}
```

**The rule:** Any `<script type="application/ld+json">` rendering MUST escape the three HTML-significant characters (`<`, `>`, `&`) as Unicode escapes. Use a `SafeJsonLd` helper component — never inline `dangerouslySetInnerHTML`.

### Open Redirect Prevention

Login/auth pages with a `?from=...` redirect parameter are open-redirect sinks if the value is not validated.

**Wrong — trusts query param blindly:**
```typescript
const from = searchParams.from || "/"
redirect(from) // attacker: ?from=https://evil.com
```

**Correct — validate it's an internal relative path:**
```typescript
function isSafeInternalPath(p: string): boolean {
  if (!p || typeof p !== "string") return false
  if (p.startsWith("//")) return false  // protocol-relative
  if (!p.startsWith("/")) return false   // not absolute
  try {
    new URL(p)  // valid absolute URL → reject
    return false
  } catch {
    return true  // not a URL → safe relative path
  }
}

const from = searchParams.from
const safe = typeof from === "string" && isSafeInternalPath(from) ? from : "/"
redirect(safe)
```

**The rule:** Any redirect target read from query params, body, or cookies MUST be validated as an internal path before being passed to `redirect()` or `Response.redirect()`. Reject URLs starting with `//`, `http://`, `https://`, or anything that parses as an absolute URL.

### Token Invalidation on Credential Changes

Password change/reset operations MUST invalidate all outstanding session tokens AND password-reset tokens for that user. Otherwise an attacker who already has a valid token (or who triggered a reset email but didn't complete it) retains access after the user thinks they've secured their account.

**Required cleanup on password change:**
```typescript
await db.$transaction([
  db.user.update({ where: { id: userId }, data: { passwordHash } }),
  // 1. Invalidate any pending password reset tokens
  db.passwordResetToken.deleteMany({ where: { userId } }),
  // 2. Invalidate active sessions (if using DB sessions)
  db.session.deleteMany({ where: { userId } }),
])
// 3. If using JWT sessions, bump a tokenVersion field on the user and check
//    it in the session callback to reject older tokens.
```

**The rule:** Password change/reset MUST be atomic with: deleting all `passwordResetToken` rows for the user, AND invalidating sessions (DB delete or JWT version bump). Do not leave a window where old tokens still work.

## 7. CSRF Protection

- State-changing requests (POST/PUT/DELETE) need CSRF tokens if using cookie-based auth
- Most modern frameworks handle this automatically — verify it's enabled, don't disable it
- SameSite=Lax cookies provide partial CSRF protection but are not sufficient alone for sensitive operations

## 8. Transaction Safety (see transaction-patterns.md)

For payment ordering, server-side price recalculation, and atomic inventory operations, see `.claude/rules/web/transaction-patterns.md`. These patterns prevent financial loss from business logic bugs — distinct from auth/authz issues covered above.

## 9. Secret Code Enumeration Prevention

Endpoints that accept secret codes (gift cards, coupons, invite codes, password reset tokens) MUST return a single generic error for all failure cases.

**Wrong — distinct errors let attackers enumerate valid codes:**
```
const gc = await db.giftCard.findUnique({ where: { code } })
if (!gc) return Response.json({ error: "Gift card not found" }, { status: 404 })
if (gc.balance <= 0) return Response.json({ error: "Gift card has no balance" }, { status: 400 })
if (gc.expiresAt < new Date()) return Response.json({ error: "Gift card expired" }, { status: 400 })
// Attacker learns: 404 = invalid code, 400 "no balance" = valid but spent, 400 "expired" = valid but old
```

**Correct — single generic error, log specifics server-side:**
```
const gc = await db.giftCard.findUnique({ where: { code } })
if (!gc || gc.balance <= 0 || (gc.expiresAt && gc.expiresAt < new Date())) {
  logger.info("Gift card lookup failed", { code: code.slice(0, 4) + "***", reason: !gc ? "not_found" : "exhausted_or_expired" })
  return Response.json({ error: "Invalid or expired gift card" }, { status: 400 })
}
```

**The rule:** Endpoints accepting secret codes MUST return the same generic error message and HTTP status for "not found," "expired," "already used," and "no balance." Log the specific failure reason server-side for debugging. This prevents attackers from probing for valid codes.

## 10. Secret Environment Variables

**NEVER** use fallback or default values for secret environment variables:

```
// ✗ FORBIDDEN — allows stale cookies to bypass auth via known fallback
const secret = process.env.JWT_SECRET || "fallback-secret"
const secret = process.env.NEXTAUTH_SECRET ?? "dev-secret"

// ✓ CORRECT — fail loudly if secret is missing
const secret = process.env.JWT_SECRET
if (!secret) throw new Error("JWT_SECRET environment variable is required")
```

This applies to:
- `JWT_SECRET` / `NEXTAUTH_SECRET` — auth token signing
- `DATABASE_URL` with credentials — database access
- API keys for external services (payment, email, AI)
- Any value that, if known, grants access to protected resources

**Why this matters:** A hardcoded fallback means production can silently run with a weak secret if the env var is misconfigured. Attackers who know the fallback value (from source code) can forge valid tokens. Stale cookies from development sessions bypass auth when the fallback matches.

### Lazy validation — never throw at module top level

"Fail loudly" MUST NOT be implemented as a top-level `throw` in a file imported by `src/app/**`. Next.js statically analyses routes during `next build` and executes top-level module code to collect page metadata; a top-level throw crashes the build with a cryptic "Collecting page data" error even when the code path needing the secret is never reached during build.

```typescript
// ✗ WRONG — crashes `next build` for any route that transitively imports this file
const secret = process.env.NEXTAUTH_SECRET
if (!secret) throw new Error("NEXTAUTH_SECRET is required")
export const { auth } = NextAuth({ secret, providers: [...] })

// ✓ CORRECT — validation runs at request time inside the handler/callback
function requireSecret(name: string): string {
  const v = process.env[name]
  if (!v) throw new Error(`${name} environment variable is required`)
  return v
}
export const { auth } = NextAuth({
  // Auth.js v5 reads NEXTAUTH_SECRET from process.env at request time automatically.
  providers: [
    Credentials({
      async authorize(credentials) {
        // Use requireSecret() here if you need to reference a secret inside the handler.
      },
    }),
  ],
})
```

If you genuinely need fail-fast on server startup (not per-request), put the check in `src/instrumentation.ts` — Next.js runs that once on server boot and NOT during `next build`. See also auth-conventions.md § "No Module-Level Env Validation Throws".
