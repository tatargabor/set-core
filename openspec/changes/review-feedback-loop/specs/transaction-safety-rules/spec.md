# Spec: Transaction Safety Rules

## ADDED Requirements

## IN SCOPE
- Payment/order transaction ordering rules (create record before charging)
- Server-side price/cost recalculation rules (never trust client-supplied monetary values)
- Atomic stock/inventory operations (check-and-decrement in single transaction)
- Cross-reference from existing security-patterns.md to new transaction-patterns.md
- Rules file format compatible with `.claude/rules/` auto-loading

## OUT OF SCOPE
- Automated extraction of CRITICAL patterns from review output (future iteration)
- Changes to the verifier.py review gate logic
- Runtime pattern learning or ML-based rule generation
- Non-web transaction patterns (CLI tools, batch processing)

### Requirement: Payment transaction ordering
The transaction rules SHALL specify that order/record creation MUST precede payment capture.

#### Scenario: Correct payment flow documented
- **WHEN** an agent implements a checkout or payment endpoint
- **THEN** the rules file instructs: create order in PENDING status first, attempt payment, then confirm order
- **AND** includes a rollback pattern: on payment failure, set order to CANCELLED

#### Scenario: Wrong pattern documented as anti-pattern
- **WHEN** the rules file describes payment ordering
- **THEN** it shows the wrong pattern (payment before record) explicitly marked as forbidden
- **AND** explains the failure mode (customer charged with no order record, no refund path)

### Requirement: Server-side price recalculation
The transaction rules SHALL specify that all monetary values MUST be recalculated server-side.

#### Scenario: Shipping cost recalculation
- **WHEN** an agent implements an order/checkout endpoint that includes shipping cost
- **THEN** the rules file instructs: ignore client-supplied `shippingCost`, recalculate from server-side shipping zone logic

#### Scenario: Cart total recalculation
- **WHEN** an agent implements order total calculation
- **THEN** the rules file instructs: recalculate item prices from database, never trust client-supplied `price` or `total` fields

### Requirement: Atomic inventory operations
The transaction rules SHALL specify that stock check and decrement MUST be atomic.

#### Scenario: Atomic conditional update pattern
- **WHEN** an agent implements stock decrement for an order
- **THEN** the rules file provides the atomic pattern: conditional update with `stock >= quantity` in the WHERE clause, inside a database transaction
- **AND** shows how to detect insufficient stock from the update result count

#### Scenario: Race condition anti-pattern documented
- **WHEN** the rules file describes inventory operations
- **THEN** it shows the wrong pattern (separate check then decrement) explicitly as forbidden
- **AND** explains the race condition (concurrent checkouts both pass check before either decrement)

### Requirement: Rules file deployment
The new rules file SHALL be deployed to consumer projects via set-project init.

#### Scenario: File present after init
- **WHEN** `set-project init` is run on a consumer project
- **THEN** `.claude/rules/web/transaction-patterns.md` exists in the project

### Requirement: Cross-reference from security patterns
The existing security-patterns.md SHALL reference the new transaction-patterns.md.

#### Scenario: Cross-reference added
- **WHEN** a developer reads security-patterns.md
- **THEN** there is a section pointing to transaction-patterns.md for payment/pricing/stock patterns
