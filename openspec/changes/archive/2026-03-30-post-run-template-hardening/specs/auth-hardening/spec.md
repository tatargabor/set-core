# Spec: Auth Hardening

## Status: new

## Requirements

### REQ-AUTH-NO-SECRET-FALLBACK: Never use fallback values for secret env vars
- Auth code MUST NOT use patterns like `process.env.JWT_SECRET || "fallback-secret"` or `process.env.NEXTAUTH_SECRET ?? "dev-secret"`
- If the env var is missing, the app MUST fail loudly (throw error at startup), not silently use a weak secret
- This prevents: stale cookies bypassing auth via known fallback, production running with dev secrets
- Add to both `auth-conventions.md` and `security.md` (security-patterns.md)

### REQ-AUTH-LAYOUT-VALIDATION: Protected layouts must validate JWT, not just check cookie presence
- Protected layout components MUST call `getSession()` or `verifyToken()` — not just `cookies().has('token')`
- Both root layout (for conditional nav rendering) and protected route layout must validate
- Cookie presence ≠ valid session: expired tokens, rotated secrets, pre-deployment tokens all have cookies but invalid JWTs
- Middleware catches most cases, but Next.js Router Cache can serve pages without hitting middleware on client-side navigation

### REQ-AUTH-POST-REGISTER: Auto-login after registration
- After successful user registration, the app SHOULD automatically sign the user in (e.g., `signIn("credentials", ...)`) rather than redirecting to login page
- This is a UX convention, not a security requirement — add as recommendation in auth-conventions

### REQ-AUTH-MIDDLEWARE-API-EXCLUDE: Middleware must exclude all API routes
- Auth/i18n middleware matcher MUST exclude all `/api/**` routes, not just specific sub-paths like `/api/auth`
- Pattern: `matcher: ['/((?!api|_next|.*\\..*).*)']`
- When middleware runs on API routes, it can redirect JSON responses to login pages or add locale prefixes to API paths
