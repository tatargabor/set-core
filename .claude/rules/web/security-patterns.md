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
