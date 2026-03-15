# Design System

## Figma

**Figma Make:** https://www.figma.com/make/DDCs2kpcLYw6E3Q1EcDjCK/wt-CraftBrew

> **All design tokens (colors, typography, spacing, shadows) come from the Figma MCP.**
> The preflight snapshot is injected into the decompose prompt automatically.
> Agents query the Figma MCP at runtime for specific frame details during implementation.
> Do NOT hardcode design values — always reference the Figma source.

### Frame mapping

| Frame | Content | Related spec |
|-------|---------|--------------|
| Design Tokens & Components | Colors, typography, buttons, cards, badges | design-system.md |
| Homepage Desktop (1280px) | Header, Hero, Featured, Subscription CTA, Stories, Testimonials, Footer | product-catalog.md |
| Homepage Mobile (375px) | Hamburger drawer, mobile hero, 1-column layout | product-catalog.md |
| Coffee Catalog | Filter sidebar, 3-column grid, sorting | product-catalog.md |
| Product Detail | Variant selector, reviews, recommended products | product-catalog.md, reviews-wishlist.md |
| Cart | Cart items, coupon/gift card input, summary | cart-checkout.md |
| Checkout 3-Step | Shipping, payment, confirmation | cart-checkout.md |
| Subscription Wizard | 5-step wizard in Figma (spec defines 6 steps — spec is authoritative) | subscription.md |
| User Subscriptions & Calendar | Subscription card, calendar view | subscription.md |
| User Orders & Profile | Orders, favorites, dashboard | user-accounts.md, reviews-wishlist.md |
| User Profile & Addresses | Profile settings, saved addresses with zone labels | user-accounts.md |
| Admin Dashboard | KPI cards, revenue chart, top products, low stock | admin.md |
| Admin Products | Product list, editor tabs, bundle editor | admin.md |
| Admin Orders & Deliveries | Order list, daily deliveries view | admin.md |
| Admin Coupons/Promo/Gift/Reviews | 4 admin management pages | admin.md, promotions.md, reviews-wishlist.md |
| Admin Subscriptions | Subscription list, pause/modify/cancel | admin.md, subscription.md |
| Stories | Story list + detail + admin editor | content-stories.md |
| Auth Pages | Login, register, password reset | user-accounts.md |
| Special States | 404, 500, empty states, loading, toast, promo banner | — |
| Email Templates | Welcome, order, shipping, gift card | email-notifications.md |

## Brand

**CraftBrew** — warm, artisanal, premium but not elitist. The joy and community of coffee.

## Mobile Rules (CRITICAL)

1. **No horizontal overflow** — nothing should overflow horizontally (except DataTable)
2. **Touch target** — minimum 44x44px for every button, link, checkbox
3. **Font size** — minimum 16px in input fields (iOS zoom prevention)
4. **Safe area** — padding-bottom for sticky elements (iOS bottom bar)
5. **Images** — `object-fit: cover`, fixed aspect ratio, no distortion
6. **Modal/Dialog** — on mobile use full-screen sheet (sliding up from bottom), not a small modal

> For visual reference of all layouts (desktop + mobile), query the Figma MCP with frame names from the table above.

## Components

Using shadcn/ui components:
- Button, Card, Badge, Input, Label, Select, Checkbox, RadioGroup
- Dialog (desktop) / Sheet (mobile) — responsive modal
- DropdownMenu, Table, DataTable
- Toast (notifications)
- Separator, Tabs
- Calendar (date picker — subscription, promo day)
- Accordion (FAQ, filters on mobile)
