# transaction-safety-extensions

Delta spec for `.claude/rules/web/transaction-patterns.md`.

## ADDED Requirements

### Requirement: Payment failure rollback of side effects

When a checkout flow has multiple side effects (stock decrement, coupon usage, gift card balance deduction), ALL side effects MUST be reversed on payment failure. The system SHALL NOT leave orphaned side effects (e.g., decremented stock with no order, used coupon with no purchase).

#### Scenario: Payment fails after side effects applied

- **WHEN** checkout decrements stock, marks a coupon as used, and deducts gift card balance before attempting payment, and the payment fails
- **THEN** all three side effects (stock, coupon, gift card) MUST be reversed in the catch block or via database transaction rollback

#### Scenario: Side effects applied after payment

- **WHEN** checkout applies side effects (stock, coupon, gift card) only after successful payment confirmation
- **THEN** no reversal is needed on payment failure because side effects were never applied

### Requirement: Soft status transitions for financial records

The system SHALL NEVER hard-delete orders, subscriptions, payments, or other financial records on failure. Financial records MUST use status transitions (e.g., PENDING to PAYMENT_FAILED) instead of deletion. The record MUST exist for customer support, debugging, and compliance.

#### Scenario: Payment fails on pending order

- **WHEN** a payment attempt fails for a PENDING order
- **THEN** the order status transitions to PAYMENT_FAILED (not deleted), and the record remains queryable

#### Scenario: Subscription cancellation

- **WHEN** a subscription is cancelled or payment lapses
- **THEN** the subscription record transitions to CANCELLED or EXPIRED status, never deleted

### Requirement: Atomic finite resource operations

The atomic conditional update pattern (check-and-decrement in one operation) SHALL apply to all finite resources, not just inventory stock. This includes gift card balances, coupon usage limits, seat counts, license quantities, and any other bounded numeric resource.

#### Scenario: Gift card balance deduction

- **WHEN** a gift card is used for payment
- **THEN** the balance check and deduction MUST be a single atomic operation using conditional update (`WHERE balance >= amount`)

#### Scenario: Coupon usage limit enforcement

- **WHEN** a coupon with a usage limit is applied
- **THEN** the usage count increment MUST be atomic with a conditional check (`WHERE usageCount < maxUses`)

#### Scenario: Seat count allocation

- **WHEN** a new user is added to a plan with seat limits
- **THEN** the seat allocation MUST use atomic conditional update (`WHERE usedSeats < maxSeats`)
