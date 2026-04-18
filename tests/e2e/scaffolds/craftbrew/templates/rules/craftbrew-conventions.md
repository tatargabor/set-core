---
description: CraftBrew coffee e-commerce project conventions
globs:
  - "src/**"
  - "prisma/**"
---

# CraftBrew Conventions

## Recommended Change Decomposition

CraftBrew is a complex e-commerce spec. Keep changes focused:

1. **foundation-setup** (Phase 1) — Prisma schema (all models; `Order.userId` is REQUIRED, not optional), seed data, package.json deps, i18n setup, Tailwind config, layout structure
2. **auth-and-accounts** (Phase 1) — NextAuth v5 Credentials + JWT, customer `/login` + `/register` (role=USER), admin `/admin` login (role=ADMIN, seed-only), user dashboard, `src/middleware.ts` for `/admin/*` (USER → 403), storefront Navbar with signed-in/signed-out variants, AdminSidebar skeleton shared by later admin changes
3. **product-catalog** (Phase 2) — Coffee/equipment/merch listing, detail pages, filters, search
4. **cart-and-session** (Phase 2) — Cart session (httpOnly `session_id` cookie), add/remove/update, cart page, cart E2E tests. **Cart browsing is anonymous; checkout is login-gated (handled in checkout-and-orders, not here).**
5. **admin-products** (Phase 2) — Admin CRUD for Coffee / Equipment / Merch / Bundles + variants, DataTable, admin-products E2E tests. Depends on auth-and-accounts (AdminSidebar + middleware). **Admin operations (orders, coupons, reviews) are NOT in this change.**
6. **checkout-and-orders** (Phase 3) — `placeOrder` server action asserts auth → creates `Order` with `userId`, clears cart. "Proceed to Checkout" CTA swaps to "Sign in to checkout" → `/login?returnTo=/cart` for anonymous users. Customer `/orders` + `/orders/[id]` with ownership check. On login the anonymous cart merges into the user cart (transactional). Cancellation, returns.
7. **admin-operations** (Phase 4, AFTER checkout-and-orders) — `/admin/orders` list (status filter, sorted by createdAt DESC) + `/admin/orders/[id]` detail, daily-deliveries view, coupon CRUD, promo days, gift cards, review moderation. Admin Dashboard stat cards become links to the relevant admin sub-pages.

Keep foundation and auth SEPARATE. Keep cart and checkout SEPARATE — login-gating lives in checkout-and-orders, not cart. Keep **admin-products and admin-operations SEPARATE** — they share only the AdminSidebar (owned by auth-and-accounts). Admin-operations depends on the `Order` table existing, so it cannot run before checkout-and-orders. This prevents 100K+ token mega-changes that are prone to integration failures.

CRITICAL: NEVER combine cart and checkout in one change. The cart-and-checkout mega-change caused integration-failed in previous runs. Cart session management and checkout/order processing are separate concerns.

## Auth-flow contract

These rules catch silent-failure patterns that surfaced repeatedly as review findings in earlier e-commerce runs. Each one is cheap to get right at implementation time and expensive to catch later:

- `placeOrder()` MUST start with `const session = await auth(); if (!session) return { error: "Please sign in to place an order" }`. NEVER create a guest Order with `userId = null` — `Order.userId` is required in the schema and the whole point of the login gate is that no row exists without a user.
- The "Proceed to Checkout" button on `/cart` MUST swap to "Sign in to checkout" → `/login?returnTo=/cart` for anonymous visitors. Do NOT render the checkout form for anonymous users and rely on form-submit to reject.
- `/orders` and `/orders/[id]` server components MUST redirect to `/login?returnTo=<current>` when unauthenticated — NOT render an empty state or "no orders yet" card. An anonymous visitor hitting `/orders` has no orders *by definition*, so the empty state is indistinguishable from an auth bug.
- Cart merge on login MUST be transactional: inside a single Prisma transaction, read items from the anonymous `session_id` cart, upsert them into the logged-in user's cart (summing quantities for identical variants), then delete the anonymous cart row. Do NOT do this in two separate write calls — a crash between them duplicates or loses items.
- `/admin/*` middleware MUST return a 403 page (NOT redirect to `/admin` login) when a USER-role session hits admin routes. Silent redirects hide privilege errors during E2E runs and make test failures look like login flow bugs.
- Server actions that mutate user data (`placeOrder`, cart mutations, all `/admin/*` actions) MUST re-check the session inside the action. Middleware is not the only line of defense — server actions are directly callable.

## Product Types

- Coffee: Single Origin, Blend, Espresso — each with origin, roast level, tasting notes
- Equipment: Grinders, Brewers, Accessories — each with specs
- Merch: T-shirts, Mugs, Bags — each with size/color variants
- Bundles: curated combinations of coffee + equipment

## Coffee-Specific Fields

- Roast levels: Light, Medium, Medium-Dark, Dark (enum in Prisma)
- Origin: country + region (e.g., "Ethiopia, Yirgacheffe")
- Tasting notes: comma-separated (e.g., "Blueberry, Chocolate, Citrus")
- Weight options: 250g, 500g, 1kg variants

## Subscription Model

- Frequencies: weekly, bi-weekly, monthly
- Subscription tied to a coffee product + weight + frequency
- Billing: recurring, cancel anytime
- Delivery scheduling based on frequency

## Currency & Locale

- HUF currency — prices displayed as `X Ft` (no decimals)
- Hungarian locale: date format `YYYY.MM.DD`, thousand separator: space
- `formatPrice(amount: number)`: format with space separators, append ` Ft`

## UI Components

- ALL UI components MUST use shadcn/ui: Button, Card, Input, Label, Textarea, Table, Dialog, Sheet, Select, etc.
- Import from `@/components/ui/<component>` — install first with `npx shadcn@latest add <component>`
- Use `cn()` from `@/lib/utils` for conditional class merging
- Do NOT use plain HTML `<button>`, `<input>`, `<select>` — always use shadcn equivalents
- Do NOT delete `components.json` or `src/lib/utils.ts` — these are required

## Design System

- `docs/design-system.md` has design tokens (colors, typography, spacing, radii)
- `docs/design-brief.md` has per-page visual descriptions (layout, components, responsive behavior)
- Per-change `openspec/changes/<name>/design.md` (if present) has scope-matched tokens + visual specs — read this FIRST
- Follow design tokens exactly — do not fall back to shadcn/ui or Tailwind defaults if they differ
- Brand colors: Coffee Brown `#78350F` (primary), Amber `#D97706` (secondary), Cream `#FFFBEB` (background)

## Admin

- Full CRUD for all product types
- Order management with status workflow: pending → processing → shipped → delivered
- Coupon/promo management
- Review moderation (approve/reject)

## Layout Parity

Admin and shop layouts MUST include the same provider components:
- `<Toaster>` — required for toast notifications after server actions
- `<SessionProvider session={await auth()}>` — required for client-side session access

Every server action that mutates data MUST show user feedback (toast.success/toast.error). Never fire-and-forget.

## Images

- Product images: use `https://placehold.co/400x300/78350F/FFFBEB?text=Product+Name` with brand colors

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
