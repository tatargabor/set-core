---
paths:
  - "tests/e2e/**"
  - "**/*.spec.ts"
  - "**/*.spec.js"
  - "playwright.config.*"
---
# Playwright Assertion Patterns

Playwright's `expect` API is narrow and opinionated. Several widely-used-elsewhere
matchers do not exist here, and using them produces confusing runtime errors
like `locator._expect: expectedNumber: expected float, got object`.

## `toHaveCount` — exact count only

```ts
// ✅ Correct — exact match
await expect(page.locator('li')).toHaveCount(3)
```

```ts
// ❌ INVALID — toHaveCount only accepts a plain number
await expect(page.locator('li')).toHaveCount({ min: 2 })
await expect(page.locator('li')).toHaveCount({ gte: 3 })
```

The `{ min, max, gte }` object form does **NOT** exist in Playwright. It is a
common confusion with `expect(x).toEqual({ ... })` in Jest/Vitest — those are
deep-equality matchers, not count matchers. Playwright's `toHaveCount` is a
terminal assertion: it waits for the locator's count to equal EXACTLY the given
integer and fails otherwise.

## "At least N" assertions

For range-style assertions (`at least N`, `more than N`, `between N and M`),
call `.count()` and use standard numeric matchers:

```ts
// ✅ At least 2
const n = await page.locator('li').count()
expect(n).toBeGreaterThanOrEqual(2)
```

```ts
// ✅ Between 1 and 5 (inclusive)
const n = await page.locator('li').count()
expect(n).toBeGreaterThanOrEqual(1)
expect(n).toBeLessThanOrEqual(5)
```

```ts
// ✅ More than 0 — prefer the semantic form over a literal number
await expect(page.locator('li').first()).toBeVisible()
```

## Other common mistakes

| ❌ Wrong | ✅ Correct |
|---------|----------|
| `toHaveText('foo', { exact: false })` | `toContainText('foo')` |
| `toHaveValue(/regex/)` | `.inputValue()` + `expect(v).toMatch(/regex/)` |
| `toBeVisible({ visible: true })` | `toBeVisible()` (no options) |
| `toHaveAttribute('src')` (no value) | `toHaveAttribute('src', /./)` |
| `expect(locator).toExist()` | `toHaveCount(1)` or `toBeAttached()` |

## Rule summary

1. **`toHaveCount(N)` takes a plain integer, never an object.**
2. **For "at least / at most / range", use `.count()` + numeric matchers.**
3. **Check the Playwright docs before inventing a new matcher.** The surface is
   narrow by design — if what you want isn't listed, the framework doesn't have
   it and you need to fall back to raw locator methods + Jest-style `expect()`.
4. **Never pass `{ min, max, gte, lte }` to any Playwright matcher.** None of
   them accept these. You will get `expected float, got object` at runtime.
