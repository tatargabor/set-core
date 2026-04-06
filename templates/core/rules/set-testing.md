# E2E Test Naming Convention

Every E2E test that validates a requirement MUST include the REQ-ID prefix in its test name. The coverage gate parses test names to track which requirements are tested.

## Format

```typescript
test('REQ-CART-001: Add to cart updates badge count', async ({ page }) => {
  // ...
});

test.describe('REQ-AUTH-002: Login flow', () => {
  test('valid credentials redirect to profile', async ({ page }) => {
    // ...
  });
  test('invalid password shows error', async ({ page }) => {
    // ...
  });
});
```

## Rules

- Place the `REQ-XXX-NNN:` prefix at the start of the test name or describe block
- Use the exact REQ-ID from the requirements (e.g., `REQ-CART-001`, not `CART-1`)
- Tests without REQ-IDs are invisible to the coverage gate and do not count toward the merge threshold
- SMOKE tests should also include `@SMOKE` tag: `test('REQ-AUTH-001: Registration @SMOKE', { tag: '@smoke' }, ...)`
- One test block can cover one REQ-ID; group related tests under a `test.describe` with the REQ-ID
