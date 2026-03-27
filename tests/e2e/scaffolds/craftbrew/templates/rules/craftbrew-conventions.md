---
description: CraftBrew coffee e-commerce project conventions
globs:
  - "src/**"
  - "prisma/**"
---

# CraftBrew Conventions

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

## Design System

- Design source: `docs/figma-raw/` directory contains Figma export
- `docs/design-snapshot.md` has design tokens (colors, typography, spacing)
- Follow design tokens exactly — do not fall back to Tailwind defaults if they differ
- Brand colors: Coffee Brown (#6F4E37), Cream (#FFF8DC), Dark Roast (#3C2415)

## Admin

- Full CRUD for all product types
- Order management with status workflow: pending → processing → shipped → delivered
- Coupon/promo management
- Review moderation (approve/reject)

## Images

- Product images use placeholder service: `https://placehold.co/400x300/6F4E37/FFF8DC?text=Product+Name`
- Use brand colors in placeholder URLs
