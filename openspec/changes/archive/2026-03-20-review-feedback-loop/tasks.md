# Tasks: Review Feedback Loop

## 1. Create transaction patterns rules file

- [ ] 1.1 Create `.claude/rules/web/transaction-patterns.md` with frontmatter (globs matching api/route/lib files) [REQ: payment-transaction-ordering]
- [ ] 1.2 Add payment transaction ordering rule (anti-pattern + correct pattern + why) [REQ: payment-transaction-ordering]
- [ ] 1.3 Add server-side price recalculation rule (shipping cost + cart total) [REQ: server-side-price-recalculation]
- [ ] 1.4 Add atomic inventory operations rule (race condition anti-pattern + atomic conditional update) [REQ: atomic-inventory-operations]

## 2. Cross-reference and deployment

- [ ] 2.1 Add cross-reference section to `.claude/rules/web/security-patterns.md` pointing to transaction-patterns.md [REQ: cross-reference-from-security-patterns]
- [ ] 2.2 Verify `set-project init` deploys the new file (check deploy.sh includes web/transaction-patterns.md) [REQ: rules-file-deployment]

## Acceptance Criteria (from spec scenarios)

- [ ] AC-1: WHEN an agent implements checkout THEN rules instruct create-order-first, payment-second, rollback-on-failure [REQ: payment-transaction-ordering, scenario: correct-payment-flow-documented]
- [ ] AC-2: WHEN rules describe payment ordering THEN wrong pattern shown as forbidden with failure mode explanation [REQ: payment-transaction-ordering, scenario: wrong-pattern-documented-as-anti-pattern]
- [ ] AC-3: WHEN agent implements order endpoint with shipping THEN rules instruct server-side recalculation [REQ: server-side-price-recalculation, scenario: shipping-cost-recalculation]
- [ ] AC-4: WHEN agent implements stock decrement THEN rules provide atomic conditional update pattern [REQ: atomic-inventory-operations, scenario: atomic-conditional-update-pattern]
- [ ] AC-5: WHEN set-project init runs THEN transaction-patterns.md exists in consumer project [REQ: rules-file-deployment, scenario: file-present-after-init]
- [ ] AC-6: WHEN developer reads security-patterns.md THEN cross-reference to transaction-patterns.md exists [REQ: cross-reference-from-security-patterns, scenario: cross-reference-added]
