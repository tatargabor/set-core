---
description: Auth middleware patterns for web frameworks — route protection, redirect logic
globs:
  - "middleware.{ts,tsx,js,jsx}"
  - "src/middleware.{ts,tsx,js,jsx,py}"
  - "app/middleware.{ts,tsx,js,jsx,py}"
  - "server/middleware/**"
  - "lib/auth/**"
  - "utils/auth/**"
---

# Auth Middleware Patterns

When a spec requires "admin pages" or "protected routes", you MUST create auth middleware — not just auth check functions.

## Pattern: Route Protection Middleware

The middleware runs BEFORE route handlers. It checks auth and redirects or returns 401.

### General pattern (any framework):

```
function authMiddleware(request):
  path = request.url.pathname

  # Define protected route prefixes
  protectedPrefixes = ["/admin", "/dashboard", "/account", "/api/protected"]

  # Check if current path needs protection
  if not any(path.startsWith(p) for p in protectedPrefixes):
    return next()  # public route, pass through

  # Check authentication
  session = getSession(request)
  if not session or not session.isValid():
    if isApiRoute(path):
      return Response(401, { error: "Unauthorized" })
    else:
      return redirect("/login?from=" + encodeURIComponent(path))

  return next()  # authenticated, proceed
```

### Key requirements:

1. **Create the middleware file** — it won't exist by default. This is the most common omission.
2. **Register it** — add to framework config (Express `app.use()`, Next.js root `middleware.ts`, Django `MIDDLEWARE` list, FastAPI `@app.middleware`)
3. **Match protected paths** — use prefix matching, not exact paths (new sub-routes auto-protected)
4. **Preserve redirect target** — save the original URL so user returns after login
5. **Handle API vs page routes differently** — APIs return 401 JSON, pages redirect to login

## Protected layout: hide navigation for unauthenticated users

Admin/dashboard layouts often include sidebar navigation (links to sub-pages). These navigation elements MUST only be visible to authenticated users. Unauthenticated users should see only the login/register form — not the full admin chrome.

### Pattern: separate layouts for public vs protected admin routes

```
# Option A: Route groups (Next.js App Router, Remix)
app/admin/(auth)/login/page.tsx     ← uses minimal layout (no sidebar)
app/admin/(auth)/register/page.tsx  ← uses minimal layout (no sidebar)
app/admin/(dashboard)/page.tsx      ← uses admin layout WITH sidebar
app/admin/(dashboard)/products/     ← uses admin layout WITH sidebar

# Option B: Conditional layout
function AdminLayout({ children }) {
  const session = await getSession()
  if (!session) {
    return <div className="centered">{children}</div>  // minimal wrapper
  }
  return (
    <div className="flex">
      <AdminSidebar />  // only rendered when authenticated
      <main>{children}</main>
    </div>
  )
}
```

**The rule:** admin navigation links (Dashboard, Products, Users, etc.) must NOT be visible on login/register pages. Showing them to unauthenticated users is confusing — they can see the menu but can't access any page.

## Common mistakes:

- Creating login/register pages but no middleware → direct URL access bypasses auth
- Auth check only in layout/component → server-side rendering still processes the full page
- Redirecting to `/login` without preserving the original URL → bad UX
- Forgetting to handle `/api/*` routes under the same middleware → API endpoints unprotected
- **Rendering admin sidebar/nav on login page** — layout wraps all `/admin/*` routes including login, showing nav items the user can't access

## E2E test requirement:

Any auth middleware MUST have a "cold visit" E2E test:
```
test('unauthenticated visit to /admin redirects to /login', async ({ page }) => {
  await page.goto('/admin')
  await expect(page).toHaveURL(/\/login/)
})
```
