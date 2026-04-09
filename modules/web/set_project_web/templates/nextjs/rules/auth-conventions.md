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
- After successful registration, auto-login the user via `signIn("credentials", ...)` — do not redirect to login page

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
- **NEVER** use hardcoded fallback secrets: `process.env.JWT_SECRET || "fallback"` is FORBIDDEN. If the secret env var is missing, the app MUST crash at startup. Hardcoded fallbacks allow stale cookies to bypass auth and risk production running with dev secrets. See security-patterns.md § 10.

## Layout-Level Session Validation

Middleware alone is NOT sufficient for auth validation. Next.js Router Cache can serve pages on client-side navigation without hitting middleware.

- **Protected layout** (`app/(protected)/layout.tsx`) MUST call `getSession()` or `verifyToken()` — NOT just `cookies().has('token')`
- **Root layout** (`app/layout.tsx`) that conditionally renders navigation (e.g., BottomNav) MUST also validate the JWT, not just check cookie presence
- Cookie presence ≠ valid session: expired tokens, rotated secrets, and pre-deployment tokens all have cookies but invalid JWTs
- Pattern:
  ```typescript
  // app/(protected)/layout.tsx
  const session = await getSession();
  if (!session) redirect('/login');
  ```

## Edge Runtime Compatibility
- bcryptjs uses Node.js APIs (process.nextTick, setImmediate) — it CANNOT run in Edge Runtime
- Auth route handlers that use bcryptjs MUST set `export const runtime = 'nodejs'`
- Next.js middleware runs in Edge Runtime by default — do NOT import bcryptjs there
- For middleware auth checks, verify JWT/session tokens only (no password hashing)
- Password hashing (bcryptjs) belongs in API route handlers or Server Actions, never in middleware

### Required Pattern: Split Auth Config

The cleanest way to satisfy Edge Runtime constraints is to split your NextAuth config into two files. This is the **canonical pattern** — agents should follow it directly, not invent variations.

```typescript
// src/lib/auth.config.ts — EDGE-SAFE (no bcryptjs, no Prisma, no Node APIs)
import type { NextAuthConfig } from "next-auth"

export const authConfig = {
  session: { strategy: "jwt" as const },
  pages: { signIn: "/login" },
  providers: [], // Credentials provider added in auth.ts (Node-only)
  callbacks: {
    async jwt({ token, user }) {
      if (user) {
        token.id = user.id as string
        token.role = (user as { role: string }).role
      }
      return token
    },
    async session({ session, token }) {
      if (session.user) {
        session.user.id = token.id as string
        session.user.role = token.role as string
      }
      return session
    },
  },
} satisfies NextAuthConfig
```

```typescript
// src/lib/auth.ts — FULL CONFIG (Node-only, used by API routes & Server Actions)
import NextAuth from "next-auth"
import Credentials from "next-auth/providers/credentials"
import { compare } from "bcryptjs"
import { prisma } from "@/lib/prisma"
import { authConfig } from "./auth.config"

export const { handlers, auth, signIn, signOut } = NextAuth({
  ...authConfig,
  providers: [
    Credentials({
      name: "credentials",
      credentials: { email: { type: "email" }, password: { type: "password" } },
      async authorize(credentials) {
        const user = await prisma.user.findUnique({
          where: { email: credentials?.email as string },
        })
        if (!user) return null
        const ok = await compare(credentials?.password as string, user.passwordHash)
        return ok ? { id: user.id, email: user.email, role: user.role } : null
      },
    }),
  ],
})
```

```typescript
// src/middleware.ts — uses ONLY auth.config.ts (Edge-safe) + getToken
import { getToken } from "next-auth/jwt"
import { NextRequest, NextResponse } from "next/server"

export async function middleware(req: NextRequest) {
  if (req.nextUrl.pathname.startsWith("/admin")) {
    const token = await getToken({ req, secret: process.env.NEXTAUTH_SECRET })
    if (!token || token.role !== "ADMIN") {
      return NextResponse.redirect(new URL("/login", req.url))
    }
  }
  return NextResponse.next()
}

export const config = { matcher: ["/admin/:path*"] }
```

**Why this works:** middleware imports `getToken` from `next-auth/jwt` (Edge-safe JWT verification, no bcryptjs). The full Credentials provider with bcryptjs lives in `auth.ts` which is only imported by Node-runtime contexts (API routes, Server Actions, layouts).

**Anti-pattern:** importing `auth` from `auth.ts` in `middleware.ts` — pulls bcryptjs into Edge Runtime → build error or runtime crash.

## Auth Action Ordering — Side-Effects AFTER Verification

Login/register server actions that also mutate per-user state (cart merge, audit log, welcome email, history write) MUST run those side-effects ONLY after credential verification has succeeded. Running them before is both a correctness bug (stale/bot cart content pollutes the real account) and a timing oracle (attackers can measure login latency to learn which emails exist).

**Wrong — cart merge runs before password check:**
```typescript
export async function loginAction(formData: FormData) {
  const email = formData.get("email") as string;
  const password = formData.get("password") as string;

  // ❌ Fires regardless of whether the password is correct.
  //    - Bot traffic pollutes real users' carts.
  //    - Timing difference between "merge ran" and "merge didn't" leaks
  //      whether the account exists before any credential check.
  await mergeGuestCartIntoUser(email);

  const result = await signIn("credentials", { email, password, redirect: false });
  if (result?.error) return { error: "Invalid credentials" };
  // ...
}
```

**Correct — verify first, mutate second:**
```typescript
export async function loginAction(formData: FormData) {
  const email = formData.get("email") as string;
  const password = formData.get("password") as string;

  const result = await signIn("credentials", { email, password, redirect: false });
  if (result?.error) return { error: "Invalid credentials" };

  // ✅ Only reachable on successful auth. Cart merge, audit log,
  //    and any "first-time login" side-effects go here.
  const session = await auth();
  if (session?.user?.id) {
    await mergeGuestCartIntoUser(session.user.id);
  }
  // ...
}
```

**The rule:** In any auth-adjacent server action (`login`, `register`, `reset-password`, `verify-email`), the ordering MUST be:
1. Parse and validate input.
2. Run credential/token verification.
3. On success only: run side-effects that touch per-user state.
4. Return/redirect.

Audit logs and rate-limit counters are the exception — they record the attempt regardless of outcome and should log BOTH success and failure (but never mutate user data on failure).

## No Module-Level Env Validation Throws

Validation of secret env vars (see security-patterns.md § 10) MUST run **lazily** inside the handler/callback that uses the secret — never at module top level. Top-level throws crash `next build` during page data collection for any route that transitively imports the file, even when the code path using the secret is never actually hit during build.

**Wrong — throws at import time, crashes `next build` for all admin routes:**
```typescript
// src/lib/auth.ts
const secret = process.env.NEXTAUTH_SECRET;
if (!secret) {
  throw new Error("NEXTAUTH_SECRET is required"); // ❌ runs during build
}

export const { handlers, auth } = NextAuth({
  secret,
  // ...
});
```

Next.js statically analyses every route during build. Importing `auth.ts` into `app/admin/layout.tsx` runs this top-level throw, so `pnpm build` fails with a cryptic "Collecting page data" error — even if `NEXTAUTH_SECRET` will be set at runtime.

**Correct — lazy validation inside the callback:**
```typescript
// src/lib/auth.ts
function getSecret(): string {
  const s = process.env.NEXTAUTH_SECRET;
  if (!s) throw new Error("NEXTAUTH_SECRET is required");
  return s;
}

export const { handlers, auth } = NextAuth({
  // Auth.js v5 reads NEXTAUTH_SECRET from process.env automatically at
  // request time. Explicit `secret: getSecret()` in a callback is also OK.
  // What's NOT ok: a bare top-level throw.
  providers: [/* ... */],
});
```

**The rule:** any `throw` that depends on `process.env.*` MUST live inside a function body that only runs at request/handler time. If the validation needs to fail fast on startup, put it in a dedicated `instrumentation.ts` (Next.js calls this once on server boot, never during build). Never at top level of a module imported by `src/app/**`.
