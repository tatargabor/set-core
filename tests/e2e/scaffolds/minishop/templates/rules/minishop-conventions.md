---
description: MiniShop e-commerce project conventions
globs:
  - "src/**"
  - "prisma/**"
---

# MiniShop Conventions

## Product Data

- 6 seed products with variants (e.g., Mechanical Keyboard, Wireless Mouse, 4K Webcam)
- 3 attribute types: Size, Color, Material — each with 2-4 values
- Prisma schema: Product → ProductVariant → AttributeType → ProductAttribute → VariantAttributeValue
- Product basePrice in cents (integer), variant price overrides optional
- Stock tracked per variant, not per product

## Currency & Formatting

- EUR currency — prices displayed as `€X.XX`
- `formatPrice(cents: number)`: divide by 100, format with 2 decimals, prepend €
- Price ranges: `€89.99` (single) or `€129.99 – €134.99` (variant range)
- Use `src/lib/format.ts` for all price formatting

## Images

- Product images use placeholder service: `https://placehold.co/400x300/EEE/999?text=Product+Name`
- NEVER reference local files like `/images/product.jpg`
- Seed data `imageUrl` fields must use working placeholder URLs

## Admin Authentication

- bcrypt for password hashing (devDependency: `bcryptjs`)
- NextAuth with Credentials provider
- Admin registration: `/admin/register` (first user becomes admin)
- Session-based auth with JWT strategy
- Middleware protects `/admin/*` routes (except login/register)

## Seed Data

- `prisma/seed.ts` using `tsx` runner
- Idempotent: use `upsert` or check-before-insert
- Creates: 6 products, 3 attribute types, variants for each product, 1 admin user (admin@example.com / password123)
