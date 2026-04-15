---
paths:
  - "src/**"
  - "tests/**"
  - "prisma/**"
---
# Web Conventions — Anti-Patterns & Guardrails

These rules codify anti-patterns observed repeatedly during orchestrated runs.
Each rule has a direct e2e-failure signature and a concrete fix.

## 1. Never use `navigator.sendBeacon` for cart/order mutations

`navigator.sendBeacon()` is fire-and-forget — the browser discards the request
if the page unloads, and the endpoint may or may not have received it. For
cart, checkout, order, payment, or any state-changing mutation the user expects
to persist, this silently drops writes. It is appropriate ONLY for analytics.

**Wrong — cart add may silently fail after navigation:**
```typescript
navigator.sendBeacon('/api/cart', JSON.stringify({ productId, qty }));
router.push('/checkout');
```

**Correct — await the fetch and handle the error:**
```typescript
const r = await fetch('/api/cart', {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify({ productId, qty }),
});
if (!r.ok) {
  setError('Nem sikerült a kosárhoz adás, próbáld újra.');
  return;
}
router.push('/checkout');
```

**E2E signature:** tests that `goto('/checkout')` right after an add-to-cart
intermittently find an empty cart — especially under slow Playwright browsers.

## 2. Upsert unique-key discriminator rule

Prisma `upsert` with a `where` clause that picks only `productId` (not
`productId` + `userId` or `productId` + `recipientEmail`) will update a
neighbour user's record. When the upsert keys are not globally unique they
must include a discriminator.

**Wrong — `where: { productId }` updates whichever record matches first:**
```typescript
await prisma.wishlistItem.upsert({
  where: { productId: input.productId },
  update: { qty: input.qty },
  create: { productId: input.productId, userId: session.user.id, qty: input.qty },
});
```

**Correct — composite unique key scoped to the owning entity:**
```typescript
await prisma.wishlistItem.upsert({
  where: { userId_productId: { userId: session.user.id, productId: input.productId } },
  update: { qty: input.qty },
  create: { productId: input.productId, userId: session.user.id, qty: input.qty },
});
```

Make sure `schema.prisma` declares the composite unique constraint:
```prisma
model WishlistItem {
  id         Int    @id @default(autoincrement())
  userId     String
  productId  Int
  qty        Int
  @@unique([userId, productId])
}
```

Same pattern applies to gift cards (`recipientEmail`), reviews (`userId + productId`),
cart items (`userId + productId` or `sessionId + productId`).

**E2E signature:** two users share a test database; one user's action mutates
the other's record. Tests that assert on "my wishlist" see somebody else's data.

## 3. `data-testid` naming convention

Tests and components must agree on testid names. Drift between them is a
common cause of `page.locator('[data-testid="..."]').click()` hangs.

**Convention:** `data-testid="<feature>-<element>"`, kebab-case, stable across
refactors. Do NOT use text content as a testid (it changes with translation).

```tsx
// Component
<button data-testid="cart-add-button" onClick={handleAdd}>
  {t('addToCart')}
</button>

// Test
await page.locator('[data-testid="cart-add-button"]').click();
```

**E2E signature:** `TimeoutError: locator.click: Timeout 10000ms exceeded`
on a locator that "should be there" — because the component uses
`data-testid="add-to-cart"` and the test expects `cart-add-button`.

## 4. `storageState` for admin authentication

Tests that authenticate as an admin on every test (POST /api/auth/signin per
spec file) are slow and flaky — every test becomes session-dependent and a
single auth hiccup fails dozens of tests.

Use Playwright's `storageState` fixture and the shipped helper
`lib/auth/storage-state.ts`:

```typescript
// tests/e2e/admin.setup.ts
import { test as setup } from '@playwright/test';
import { createAdminStorageState } from '@/lib/auth/storage-state';

setup('authenticate as admin', async ({ page }) => {
  await createAdminStorageState(page, 'tests/e2e/.auth/admin.json');
});

// tests/e2e/admin-products.spec.ts
import { test, expect } from '@playwright/test';
test.use({ storageState: 'tests/e2e/.auth/admin.json' });

test('admin can edit product', async ({ page }) => {
  await page.goto('/admin/products');
  await expect(page.locator('[data-testid="admin-product-list"]')).toBeVisible();
});
```

**E2E signature:** admin tests fail sporadically with "expected
/admin, got /login" — the session expired or the signin request flaked.

## 5. Registration → auto-login races

A common pattern: `registerAction` calls `prisma.user.create({...})` then
immediately calls `signIn("credentials", {...})` to auto-log-in the new user.
This is race-prone — NextAuth's credentials provider re-queries the DB, and
the session cookie must reach the client before the client-side redirect
reads it.

**Wrong — silent partial success:**
```typescript
"use server";
export async function registerAction(input: RegisterInput) {
  await prisma.user.create({ data: { ... } });
  await signIn("credentials", { email, password, redirect: false });
  redirect("/fiokom");
}
```
Observed failure: `signIn()` throws `CredentialsSignin`; the page stays on
`/regisztracio` without an error. User thinks registration failed but actually
succeeded (their row is in the DB). E2E tests flake: first attempt fails, retry
passes once timing stabilizes.

**Correct — commit the user, handle the signIn failure explicitly:**
```typescript
"use server";
export async function registerAction(input: RegisterInput) {
  const user = await prisma.user.create({ data: { ... } });
  try {
    await signIn("credentials", { email, password, redirect: false });
  } catch (err) {
    // Registration succeeded; auto-login failed. Tell the user to log in.
    redirect(`/belepes?registered=1&email=${encodeURIComponent(email)}`);
  }
  redirect("/fiokom");
}
```

**E2E signature:** `REQ-AUTH-*` tests that register-then-expect-redirect flake
— first run fails with `19× unexpected value "/hu/regisztracio"`, retry
passes. The orchestration e2e gate with `PW_FLAKY_FAILS=1` catches this as a
real failure. Locally, `retries: 1` masks the bug.

## 6. Radix Select (shadcn) — opening the dropdown in tests

shadcn `<Select>` uses Radix Select, which renders `<SelectItem>` (with
`role="option"`) into a PORTAL that only mounts when the trigger is opened.
Tests that click the trigger then immediately query `getByRole('option', …)`
flake — the dropdown animation + portal mount lose a ~50-200ms race.

**Wrong — click trigger, immediately click option, hope for the best:**
```typescript
await page.locator('[data-testid="type-select"]').click();
await page.getByRole("option", { name: "Kávé" }).click();  // TimeoutError
```
Observed failure signature (craftbrew-run-20260415-0146 admin-products):
```
TimeoutError: locator.click: Timeout 10000ms exceeded.
  - waiting for getByRole('option', { name: 'Kávé' })
    - locator resolved to <div role="option" ...>
    - element is visible, enabled and stable
    - performing click action
  [times out — click doesn't register because portal handler is still mounting]
```

**Correct — wait for the listbox to appear, then click:**
```typescript
await page.locator('[data-testid="type-select"]').click();
// Wait for the dropdown content to mount + become interactive.
await expect(page.getByRole("listbox")).toBeVisible();
await page.getByRole("option", { name: "Kávé" }).click();
// Wait for the Select value to reflect the selection before moving on.
await expect(page.locator('[data-testid="type-select"]')).toContainText("Kávé");
```

Alternative: query `getByRole("option", { name: "Kávé" })` via
`{ exact: false }` if the label has surrounding text, and always pair with a
`toBeVisible()` assertion BEFORE clicking.

## 7. Slug / ID generation for non-ASCII (Hungarian, German, etc.)

Slug generators must normalize Unicode accents via `NFD`-decomposition +
combining-mark strip. Naive `toLowerCase().replace(/\s+/g, '-')` loses
characters like `ű`, `ő`, `ä`, `ß` by dropping them silently instead of
mapping to their base form.

**Wrong — `ű`/`ő` drop silently, producing truncated slugs:**
```typescript
function slugify(s: string) {
  return s.toLowerCase().replace(/[^a-z0-9]+/g, "-").replace(/^-|-$/g, "");
}
// slugify("Árvíztűrő tükörfúrógép") → "rv-zt-r-t-k-rf-r-g-p"  (garbage)
```
E2E signature (craftbrew-run-20260415-0146 admin-products REQ-ADM-002:
`meta-title-description-HU-EN`):
```
expect(locator).toHaveValue failed
Expected: "teszt-kave-arviztuero"
Received: "teszt-kave-arvizturo"   ← ű character lost, chars merged
```

**Correct — NFD normalize, strip combining marks, then slugify:**
```typescript
export function slugify(input: string): string {
  return input
    .normalize("NFD")                         // decompose accents
    .replace(/[\u0300-\u036f]/g, "")          // strip combining marks
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, "-")
    .replace(/^-|-$/g, "");
}
// slugify("Árvíztűrő tükörfúrógép") → "arvizturo-tukorfurogep"  ✓
```

For languages where NFD doesn't cover (German `ß`, Nordic `ø`, Turkish `ı`),
pre-map before normalize:
```typescript
const PRE_MAP: Record<string, string> = {
  ß: "ss", æ: "ae", œ: "oe", ø: "o", å: "aa", ı: "i",
};
input = [...input].map(c => PRE_MAP[c] ?? c).join("");
// then NFD normalize as above
```

Put this in `src/lib/slug.ts` and import everywhere a slug is generated —
product slugs, blog post slugs, admin URL segments. **Never inline-duplicate
the slug logic** — drift between call sites is a common source of "same
title produces different slugs on different pages" bugs.

## 8. REQ-id comment convention on specs

Every e2e test file should declare the REQ-ids it covers at the top of the
file. This lets the orchestrator scope-filter `npx playwright test` to only
the tests the current change owns.

```typescript
// tests/e2e/wishlist.spec.ts
// @REQ-WISHLIST-001: a user can add a product to their wishlist
// @REQ-WISHLIST-002: a user can remove a product from their wishlist
// @REQ-WISHLIST-003: another user's wishlist is not visible

import { test, expect } from '@playwright/test';
test('add to wishlist persists across page refresh', async ({ page }) => { /* @REQ-WISHLIST-001 */
  // ...
});
```

**E2E signature:** an integration gate runs the full e2e suite; a failing test
from an already-merged feature fails the current change's gate. With REQ-id
comments, the orchestrator can attribute the failing test to its owning
change and emit a `CROSS_CHANGE_REGRESSION` event instead of penalising the
current change (see Tier 2: cross-change regression detection).

## Quick reference

| Symptom | Rule |
|---|---|
| cart / checkout intermittently empty after navigation | #1 sendBeacon ban |
| "my X" shows somebody else's X | #2 upsert unique-key |
| locator timeout on testid element | #3 testid naming |
| auth-dependent tests fail sporadically | #4 storageState |
| register succeeds, user sees empty registration page | #5 register→signIn race |
| `getByRole('option')` click times out | #6 Radix Select portal |
| `ű`/`ő` disappears from slugs/IDs | #7 slug NFD normalize |
| current-change gate fails on another change's test | #8 REQ-id comments |
