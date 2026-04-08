---
description: CraftBrew coffee e-commerce project conventions
globs:
  - "src/**"
  - "prisma/**"
---

# CraftBrew Conventions

## Recommended Change Decomposition

CraftBrew is a complex e-commerce spec. Keep changes focused:

1. **foundation-setup** (Phase 1) — Prisma schema (all models), seed data, package.json deps, i18n setup, Tailwind config, layout structure
2. **auth-and-accounts** (Phase 1) — NextAuth, login/register, user dashboard, middleware
3. **product-catalog** (Phase 2) — Coffee/equipment/merch listing, detail pages, filters, search
4. **cart-and-session** (Phase 2) — Cart session, add/remove/update, cart page (NO checkout)
5. **admin-panel** (Phase 2) — Admin CRUD for products, orders, coupons, reviews
6. **checkout-and-orders** (Phase 3) — Checkout flow, payment, order history, cancellation, returns

CRITICAL: NEVER combine cart and checkout in one change. The cart-and-checkout mega-change caused integration-failed in previous runs. Cart session management and checkout/order processing are separate concerns.

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

## Images

- Product images use placeholder service: `https://placehold.co/400x300/78350F/FFFBEB?text=Product+Name`
- Use brand colors in placeholder URLs (coffee brown `#78350F` bg, cream `#FFFBEB` fg)
