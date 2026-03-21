---
description: Web route completeness — listing pages, detail/listing pairs, task-file correlation, admin coverage
globs:
  - "src/app/**/*.{ts,tsx}"
  - "app/**/*.{ts,tsx}"
  - "pages/**/*.{ts,tsx}"
---

# Web Route Completeness Patterns

These patterns prevent functional gaps where pages or API routes are planned but never created, or where implementation covers one example but skips structurally identical siblings.

## 1. Category Listing Completeness

When the spec or database schema defines multiple product/content categories, ALL categories MUST have listing pages — not just the first one implemented.

**Wrong — one category has a listing page, others don't:**
```
src/app/[locale]/coffees/page.tsx          ✓ exists
src/app/[locale]/coffees/[slug]/page.tsx   ✓ exists
src/app/[locale]/equipment/[slug]/page.tsx ✓ exists (detail only!)
src/app/[locale]/merch/[slug]/page.tsx     ✓ exists (detail only!)
src/app/[locale]/bundles/[slug]/page.tsx   ✓ exists (detail only!)
// equipment, merch, bundles have detail pages but NO listing page
// Users cannot browse these categories
```

**Correct — every category has both listing and detail pages:**
```
src/app/[locale]/coffees/page.tsx          ✓ listing
src/app/[locale]/coffees/[slug]/page.tsx   ✓ detail
src/app/[locale]/equipment/page.tsx        ✓ listing
src/app/[locale]/equipment/[slug]/page.tsx ✓ detail
src/app/[locale]/merch/page.tsx            ✓ listing
src/app/[locale]/merch/[slug]/page.tsx     ✓ detail
src/app/[locale]/bundles/page.tsx          ✓ listing
src/app/[locale]/bundles/[slug]/page.tsx   ✓ detail
```

**The rule:** Enumerate all categories from the Prisma schema enum (e.g., `ProductCategory`) or from the spec. If one category has a listing page, all categories need listing pages. The listing pages typically share the same component pattern — reuse the grid/filter layout with category-specific filtering.

## 2. Detail Page Implies Listing Page

If a dynamic detail page (`[slug]/page.tsx` or `[id]/page.tsx`) exists in a directory, the parent directory MUST also have a listing/index `page.tsx`.

**Wrong — detail page exists without listing page:**
```
src/app/[locale]/bundles/[slug]/page.tsx   ✓ exists
src/app/[locale]/bundles/page.tsx          ✗ missing!
// Users can only reach bundle details via direct URL — no way to browse
```

**Correct — listing page accompanies detail page:**
```
src/app/[locale]/bundles/page.tsx          ✓ listing (grid of all bundles)
src/app/[locale]/bundles/[slug]/page.tsx   ✓ detail (single bundle view)
```

**The rule:** Every directory containing a `[slug]/page.tsx` or `[id]/page.tsx` must also have its own `page.tsx` for listing/browsing. The only exceptions are nested dynamic routes where the parent is itself dynamic (e.g., `[userId]/[orderId]/page.tsx`).

## 3. Task-File Correlation

When tasks.md marks a task `[x]` as complete, and the task description references creating a specific file, page, or API route, that file MUST actually exist in the working tree.

**Wrong — page task marked done but file doesn't exist:**
```markdown
- [x] 5.1 Create equipment listing page at /[locale]/equipment/page.tsx
```
```
$ ls src/app/[locale]/equipment/
[slug]/page.tsx    ← only detail page exists
                   ← NO page.tsx listing page!
```

**Wrong — API route task marked done but file doesn't exist:**
```markdown
- [x] 8.2 Create return request API endpoint at /api/returns
- [x] 8.3 Build return request UI on order detail page
```
```
$ ls src/app/api/returns/
ls: cannot access 'src/app/api/returns/': No such file or directory
                   ← API route never created!
```

**Correct — task only marked done when output exists:**
```markdown
- [x] 5.1 Create equipment listing page at /[locale]/equipment/page.tsx
```
```
$ ls src/app/[locale]/equipment/
page.tsx           ← listing page exists ✓
[slug]/page.tsx    ← detail page exists ✓
```

**The rule:** Never mark a task `[x]` complete if the task describes creating a file (page.tsx, route.ts, component) and that file does not exist. Before marking done, verify the file was actually written. This applies to page files, API routes, components, utility modules, and test files.

## 4. Admin Resource Completeness

When the spec defines admin management for multiple resources, ALL mentioned admin resources MUST have corresponding admin pages — not just the primary ones.

**Wrong — spec mentions 5 admin resources but only 3 have pages:**
```
Spec says: "Admin can manage products, orders, returns, coupons, and gift cards"

src/app/[locale]/admin/products/page.tsx   ✓ exists
src/app/[locale]/admin/orders/page.tsx     ✓ exists
src/app/[locale]/admin/coupons/page.tsx    ✓ exists
src/app/[locale]/admin/returns/            ✗ missing!
src/app/[locale]/admin/gift-cards/         ✗ missing!
```

**Correct — every spec-mentioned admin resource has its page:**
```
src/app/[locale]/admin/products/page.tsx   ✓
src/app/[locale]/admin/orders/page.tsx     ✓
src/app/[locale]/admin/returns/page.tsx    ✓
src/app/[locale]/admin/coupons/page.tsx    ✓
src/app/[locale]/admin/gift-cards/page.tsx ✓
```

**The rule:** Read the spec's admin requirements section. For every resource the spec says "admin can manage/view/moderate X", verify that `admin/<resource>/page.tsx` exists. Missing admin pages mean the feature is incomplete even if the user-facing side works.
