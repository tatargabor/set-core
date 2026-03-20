# Tasks: review-rules-from-e2e

Rules live in TWO places (hierarchical):
- **set-core** `.claude/rules/web/` — review gate reads these via `_load_security_rules()`
- **set-project-web** `set_project_web/templates/nextjs/rules/` — deployed to consumer projects via `set-project init`

Both must be updated. set-core rules are the source of truth for the review gate;
set-project-web templates are what agents see during implementation.

## 1. Extend transaction-patterns.md (set-core)

- [x] 1.1 Add section #5 "Payment Failure Rollback of Side Effects" with wrong pattern (side effects before payment, no reversal) and correct pattern (side effects after payment, or explicit reversal in catch block) [REQ: payment-failure-rollback-of-side-effects]
- [x] 1.2 Add section #6 "Soft Status Transitions for Financial Records" with wrong pattern (hard delete on failure) and correct pattern (status transition PENDING → PAYMENT_FAILED) [REQ: soft-status-transitions-for-financial-records]
- [x] 1.3 Rename section #3 from "Atomic Inventory Operations" to "Atomic Finite Resource Operations" and add gift card balance and coupon usage limit examples alongside existing stock example [REQ: atomic-finite-resource-operations]

## 2. Extend security-patterns.md (set-core)

- [x] 2.1 Add section #9 "Secret Code Enumeration Prevention" with wrong pattern (distinct error messages for not-found vs expired vs used) and correct pattern (single generic error for all failure cases) [REQ: secret-code-enumeration-prevention]

## 3. Extend api-design.md (set-core)

- [x] 3.1 Add section #6 "Single Source of Truth for Validation" with wrong pattern (duplicated validation in preview and checkout) and correct pattern (shared validation function) [REQ: single-source-of-truth-for-validation]

## 4. Create schema-integrity.md (set-core + set-project-web)

- [x] 4.1 Create `set-core/.claude/rules/web/schema-integrity.md` with sections below [REQ: nullable-columns-in-unique-constraints]
- [x] 4.2 Add section #1 "Nullable Columns in Unique Constraints" with wrong pattern (@@unique with nullable column) and correct pattern (partial index or sentinel value) [REQ: nullable-columns-in-unique-constraints]
- [x] 4.3 Add section #2 "Boolean vs Enum Status Modeling" with wrong pattern (boolean flags for multi-state) and correct pattern (enum status field) [REQ: boolean-vs-enum-status-modeling]
- [x] 4.4 Add section #3 "FK Cascade Strategies for Active Records" with wrong pattern (SET NULL on active order FKs) and correct pattern (RESTRICT or soft delete) [REQ: fk-cascade-strategies-for-active-records]
- [x] 4.5 Add section #4 "JSON Column Validation" with wrong pattern (direct property access without validation) and correct pattern (schema validation on read, size bounds on write) [REQ: json-column-validation]
- [x] 4.6 Create `set-project-web/set_project_web/templates/nextjs/rules/schema-integrity.md` — copy of the above for consumer project deployment [REQ: nullable-columns-in-unique-constraints]

## 5. Create nextjs-patterns.md (set-project-web only — framework-specific)

- [x] 5.1 Create `set-project-web/set_project_web/templates/nextjs/rules/nextjs-patterns.md` with YAML frontmatter [REQ: force-dynamic-anti-pattern-prevention]
- [x] 5.2 Add section #1 "force-dynamic Anti-Pattern" with wrong pattern (blanket force-dynamic on mixed pages) and correct pattern (ISR, unstable_cache, Suspense boundaries) [REQ: force-dynamic-anti-pattern-prevention]
- [x] 5.3 Add section #2 "Server Actions in Client Effects" with wrong pattern (server action in useEffect without error handling) and correct pattern (try/catch with loading state) [REQ: server-actions-in-client-effects]

## 6. Sync set-project-web templates with set-core rules

- [x] 6.1 Update `set-project-web/set_project_web/templates/nextjs/rules/security.md` to include secret code enumeration prevention (from 2.1) [REQ: secret-code-enumeration-prevention]
- [x] 6.2 Create `set-project-web/set_project_web/templates/nextjs/rules/transaction-safety.md` with the key patterns from transaction-patterns.md (payment ordering, atomic resources, rollback, soft status) [REQ: payment-failure-rollback-of-side-effects]

## 7. Verify and cross-check

- [x] 7.1 Search set-core codebase for any references to "Atomic Inventory Operations" heading and update them to "Atomic Finite Resource Operations" [REQ: atomic-finite-resource-operations]
- [x] 7.2 Verify all new sections follow the existing format: problem description, wrong pattern (code), correct pattern (code), bold "The rule:" summary [REQ: payment-failure-rollback-of-side-effects]
- [x] 7.3 Run `set-project-web` tests to ensure templates are valid [REQ: payment-failure-rollback-of-side-effects]

## Acceptance Criteria (from spec scenarios)

- [x] AC-1: WHEN checkout decrements stock, marks coupon used, and deducts gift card before payment, and payment fails THEN all three side effects are reversed [REQ: payment-failure-rollback-of-side-effects, scenario: payment-fails-after-side-effects-applied]
- [x] AC-2: WHEN checkout applies side effects only after payment confirmation THEN no reversal needed on payment failure [REQ: payment-failure-rollback-of-side-effects, scenario: side-effects-applied-after-payment]
- [x] AC-3: WHEN payment fails for a PENDING order THEN order transitions to PAYMENT_FAILED, not deleted [REQ: soft-status-transitions-for-financial-records, scenario: payment-fails-on-pending-order]
- [x] AC-4: WHEN a gift card is used for payment THEN balance check and deduction are a single atomic operation [REQ: atomic-finite-resource-operations, scenario: gift-card-balance-deduction]
- [x] AC-5: WHEN a coupon with usage limit is applied THEN usage count increment is atomic with conditional check [REQ: atomic-finite-resource-operations, scenario: coupon-usage-limit-enforcement]
- [x] AC-6: WHEN a user submits a non-existent gift card code THEN API returns generic error identical to expired/used codes [REQ: secret-code-enumeration-prevention, scenario: invalid-gift-card-code-submitted]
- [x] AC-7: WHEN a user submits an expired coupon THEN API returns same generic error as non-existent codes [REQ: secret-code-enumeration-prevention, scenario: expired-coupon-code-submitted]
- [x] AC-8: WHEN cart preview and checkout both validate items THEN both call the same shared validation function [REQ: single-source-of-truth-for-validation, scenario: cart-preview-and-checkout-use-same-validation]
- [x] AC-9: WHEN a unique constraint includes a nullable column THEN the schema uses partial index or sentinel value instead [REQ: nullable-columns-in-unique-constraints, scenario: correct-approach-using-non-nullable-sentinel-or-partial-index]
- [x] AC-10: WHEN an order can be in multiple states THEN schema uses status enum, not boolean flags [REQ: boolean-vs-enum-status-modeling, scenario: order-with-multiple-possible-states]
- [x] AC-11: WHEN a product is deleted and active orders reference it THEN FK uses RESTRICT or product uses soft delete [REQ: fk-cascade-strategies-for-active-records, scenario: correct-approach-using-soft-delete-or-restrict]
- [x] AC-12: WHEN application reads a JSON column THEN data is validated against schema before use [REQ: json-column-validation, scenario: correct-approach-with-schema-validation-on-read]
- [x] AC-13: WHEN a page has mixed static/dynamic content THEN it uses ISR or Suspense, not force-dynamic [REQ: force-dynamic-anti-pattern-prevention, scenario: page-with-mostly-static-content-and-one-dynamic-section]
- [x] AC-14: WHEN a client component invokes a server action THEN call is wrapped in try/catch with loading state and error display [REQ: server-actions-in-client-effects, scenario: correct-approach-with-error-handling]
