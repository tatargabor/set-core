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

shadcn `<Select>` uses Radix Select. Three distinct mechanics matter:

1. **Portal mount** — `<SelectItem>` (`role="option"`) only renders after the
   trigger is opened. Querying options before the listbox is visible races.
2. **Pointer events, not click** — Radix commits the selection on `pointerup`,
   not `click`. Playwright's `.click()` dispatches mousedown/up + click; Radix
   closes the portal during mouseup. After that, Playwright tries to verify
   the click landed on the same element — but the element is already detached.
   Result: `TimeoutError ... performing click action [hangs]`, even though
   the selection *did* fire.
3. **onValueChange → re-render cascade** — selecting an option typically
   triggers `router.replace(?cat=...)` or a state setter that re-renders the
   surrounding table/list. Locators captured before the selection point to
   stale DOM nodes.

### Rule: use keyboard selection — never `dispatchEvent('click')`

**Forbidden — `dispatchEvent` bypasses the real event chain:**
```typescript
// ❌ DO NOT DO THIS — even if the test "passes", the production code path
//    is not exercised. Radix listens to pointerdown/pointerup; a synthetic
//    `click` event via dispatchEvent will not run the same code, so the test
//    passes while the real user interaction still breaks.
await page.locator('[role="option"]').evaluate(el =>
  el.dispatchEvent(new MouseEvent("click", { bubbles: true }))
);
```

**Preferred — keyboard navigation (no click-completion race):**
```typescript
const trigger = page.locator('[data-testid="type-select"]');
await trigger.click();
await expect(page.getByRole("listbox")).toBeVisible();
// First-letter jump: Radix Select supports type-ahead just like a native <select>.
await page.keyboard.press("K");             // jumps to "Kávé"
await page.keyboard.press("Enter");         // commits selection, closes portal
await expect(trigger).toContainText("Kávé"); // confirms selection applied
```

Why keyboard: `page.keyboard.press` returns as soon as the key event is
dispatched — no post-action settling wait, no detached-element race.

**Fallback — mouse click with `noWaitAfter` when keyboard isn't an option:**
```typescript
await trigger.click();
await expect(page.getByRole("listbox")).toBeVisible();
// noWaitAfter: Playwright does not wait for the element to settle AFTER the
// click. The click still fires through the real pointer-event chain, but the
// wait-after step (which hangs when Radix detaches the portal) is skipped.
await page.getByRole("option", { name: "Kávé" }).click({ noWaitAfter: true });
await expect(trigger).toContainText("Kávé");
```

### Rule: re-query locators after selection re-renders the list

After an `onValueChange` filter fires, Next.js re-runs the server component
and the table re-hydrates. Locators taken *before* the selection are stale:

**Wrong — stored locator becomes detached:**
```typescript
const row = page.locator('[data-testid="product-row"]').first();
await selectCategory("COFFEE");              // triggers router.replace → re-render
await row.getByRole("link", { name: /edit/i }).click();  // detached → timeout
```

**Correct — re-query after the filter settles:**
```typescript
await selectCategory("COFFEE");
// Assert the new DOM state has stabilized before continuing.
await expect(page.locator('[data-testid="product-row"]')).toHaveCount(2);
const row = page.locator('[data-testid="product-row"]').first();  // re-query
await row.getByRole("link", { name: /edit/i }).click();
```

**E2E signatures addressed by this rule:**
- `locator.click: Timeout 10000ms exceeded ... performing click action` on an
  option that looks visible+enabled (craftbrew-run-20260415-0146:admin-products
  REQ-ADM-002:AC-1 — second filter change hung even after listbox-visible).
- `Element is not attached to the DOM` on a row locator touched after a filter
  change — the table re-rendered and your locator pointed at the old node.

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
| `getByRole('option')` click times out — or row detached after filter | #6 Radix Select + re-query |
| `ű`/`ő` disappears from slugs/IDs | #7 slug NFD normalize |
| current-change gate fails on another change's test | #8 REQ-id comments |
