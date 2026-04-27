# Benchmark Testing Specification

## Purpose

TBD — restored after delta-sync structural cleanup. Update Purpose with a one-line statement of what this capability owns.

## Requirements

### Requirement: Payout Behavioral Verification
test-12 Bug 2 (payout rounding) SHALL FAIL when no multi-vendor orders exist in the database. The test MUST NOT auto-pass on missing data.

#### Scenario: No multi-vendor orders available
- **WHEN** `curl /api/orders` returns zero orders with 2+ payouts
- **THEN** the check SHALL FAIL with message "No multi-vendor orders — payout algorithm untested"

#### Scenario: Multi-vendor orders with correct payouts
- **WHEN** an order with 3+ vendor payouts exists and `sum(netAmount + platformFee)` equals `payment.amount`
- **THEN** the check SHALL PASS

### Requirement: TRAP-M Render Detection
test-12 Bug 11 (Pagination) SHALL check for JSX render syntax, not just import presence. A file that imports Pagination but does not render it MUST NOT pass the check.

#### Scenario: Page renders Pagination component
- **WHEN** a page file contains `<Pagination` (JSX render syntax)
- **THEN** the page SHALL count toward the "pages using Pagination" total

#### Scenario: Page only imports Pagination
- **WHEN** a page file contains `import.*Pagination` but no `<Pagination` render
- **THEN** the page SHALL NOT count toward the "pages using Pagination" total

#### Scenario: Minimum render count
- **WHEN** fewer than 3 pages render `<Pagination` in JSX
- **THEN** the TRAP-M check SHALL FAIL

### Requirement: TRAP-N Global Mount Verification
test-12 Bug 12 (Toast) SHALL verify that the Toast/notification component is mounted globally in the root layout, not just imported in individual pages.

#### Scenario: Toast mounted in root layout
- **WHEN** `src/app/layout.tsx` contains a reference to `Toast` or `Toaster` or a notification provider
- **THEN** the global mount check SHALL PASS

#### Scenario: Toast only in individual pages
- **WHEN** `src/app/layout.tsx` does NOT contain a Toast reference but 3+ page files import it
- **THEN** the global mount check SHALL FAIL with message indicating per-page mount detected

### Requirement: Vendor Regression Enforcement
test-12 vendor dashboard checks SHALL FAIL when no vendor ID can be obtained, instead of silently skipping.

#### Scenario: No vendor ID available
- **WHEN** `curl /api/vendors` returns no vendor data or parse fails
- **THEN** the vendor regression checks SHALL FAIL (not skip) with message "No vendor ID — cannot verify dashboard regression"

#### Scenario: Vendor ID obtained
- **WHEN** a valid vendor ID is extracted from `/api/vendors`
- **THEN** all vendor dashboard checks (no tabs, has badges) SHALL execute normally

### Requirement: C12 Explicit Architecture in Change Definition
The `12-sprint-retro.md` change definition acceptance criteria SHALL explicitly require that Pagination is rendered (JSX) on all list pages and that Toast is mounted globally in layout.tsx.

#### Scenario: Pagination render requirement
- **WHEN** the agent reads Bug 11 acceptance criteria in `12-sprint-retro.md`
- **THEN** it SHALL find an explicit requirement that Pagination must be rendered (`<Pagination .../>`) on all list pages, not just imported

#### Scenario: Toast global mount requirement
- **WHEN** the agent reads Bug 12 acceptance criteria in `12-sprint-retro.md`
- **THEN** it SHALL find an explicit requirement that Toast must be mounted once in `src/app/layout.tsx` for global availability

### Requirement: TRAP-G Checkout Navigation
The `02-shopping-cart.md` change definition SHALL include an acceptance criterion requiring a "Proceed to Checkout" link on the cart page. test-02.sh SHALL include a check verifying this link exists.

#### Scenario: Checkout link in C02 acceptance criteria
- **WHEN** the agent reads `02-shopping-cart.md`
- **THEN** it SHALL find an acceptance criterion: "Cart page must include a 'Proceed to Checkout' button/link navigating to /checkout"

#### Scenario: test-02 checkout link check
- **WHEN** test-02.sh runs against a cart page
- **THEN** it SHALL check for a link containing "checkout" (href to /checkout)

### Requirement: Memory Database Isolation
Benchmark init scripts SHALL use distinct project names for Run A and Run B to ensure physically separate shodh-memory databases.

#### Scenario: Run A project name
- **WHEN** `init-baseline.sh` initializes the project
- **THEN** any memory-related configuration SHALL use project name `craftbazaar-baseline` (or equivalent distinct name)

#### Scenario: Run B project name
- **WHEN** `init-with-memory.sh` initializes the project
- **THEN** memory storage SHALL use project name `craftbazaar-memory` (or equivalent distinct name, different from Run A)

#### Scenario: No shared storage
- **WHEN** both runs execute concurrently
- **THEN** Run A's memory database path and Run B's memory database path SHALL NOT overlap
