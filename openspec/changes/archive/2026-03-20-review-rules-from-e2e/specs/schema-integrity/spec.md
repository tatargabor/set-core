# schema-integrity

New rule file: `.claude/rules/web/schema-integrity.md`.

## ADDED Requirements

## IN SCOPE
- Nullable columns in unique constraints and their impact on duplicate prevention
- Boolean vs enum modeling for multi-state records
- Foreign key cascade strategies and their impact on active records
- JSON column validation patterns (runtime type checking, size bounds)

## OUT OF SCOPE
- General database performance tuning (indexing strategies, query optimization)
- ORM-specific migration tooling
- Database selection guidance (SQL vs NoSQL)

### Requirement: Nullable columns in unique constraints

The system SHALL NOT use nullable columns in unique constraint combinations when the intent is to prevent duplicates. In most databases, `NULL != NULL`, so `@@unique([userId, variantId, notifiedAt])` with nullable `notifiedAt` will not prevent duplicate rows where `notifiedAt` is NULL. The schema MUST use a non-nullable sentinel value or a partial unique index instead.

#### Scenario: Unique constraint with nullable column fails to prevent duplicates

- **WHEN** a unique constraint includes a nullable column (e.g., `@@unique([userId, productId, deletedAt])`) and two rows are inserted with NULL for that column
- **THEN** the database allows both rows because NULL != NULL, violating the intended uniqueness

#### Scenario: Correct approach using non-nullable sentinel or partial index

- **WHEN** the intent is to enforce uniqueness only for active (non-deleted) records
- **THEN** the schema uses either a partial unique index (`WHERE deletedAt IS NULL`) or a non-nullable sentinel value (e.g., a far-future date for "not deleted")

### Requirement: Boolean vs enum status modeling

When a database record can exist in more than two states, the schema MUST use an enum or string status field, not a boolean. Boolean fields cannot represent intermediate or error states, leading to ambiguous data (e.g., `isActive: false` could mean cancelled, expired, suspended, or pending).

#### Scenario: Order with multiple possible states

- **WHEN** an order can be PENDING, CONFIRMED, SHIPPED, DELIVERED, CANCELLED, or REFUNDED
- **THEN** the schema uses a status enum field, not boolean flags like `isPaid` and `isShipped`

#### Scenario: Subscription lifecycle

- **WHEN** a subscription can be TRIAL, ACTIVE, PAST_DUE, CANCELLED, or EXPIRED
- **THEN** the schema uses a status enum, not `isActive: Boolean`

### Requirement: FK cascade strategies for active records

Foreign key ON DELETE cascade strategies MUST NOT use SET NULL or CASCADE on foreign keys referenced by active financial records (orders, subscriptions, payments, invoices). Deleting a parent record that nullifies or cascades to active child records causes data loss and broken business logic.

#### Scenario: Product deleted while active orders reference it

- **WHEN** a product is deleted and orders reference it via foreign key with ON DELETE SET NULL
- **THEN** the order loses its product reference, breaking order history display and refund calculations

#### Scenario: Correct approach using soft delete or RESTRICT

- **WHEN** a product needs to be removed from the catalog but active orders reference it
- **THEN** the product uses soft delete (status transition to ARCHIVED) or the FK uses ON DELETE RESTRICT to prevent deletion

### Requirement: JSON column validation

JSON/JSONB columns MUST have runtime type validation on read and size bounds on write. Unvalidated JSON columns accept arbitrary data structures, leading to runtime crashes when consuming code assumes a specific shape.

#### Scenario: JSON column read without validation

- **WHEN** application code reads a JSON column and directly accesses nested properties without validation
- **THEN** a malformed or missing field causes a runtime TypeError instead of a graceful error

#### Scenario: Correct approach with schema validation on read

- **WHEN** application code reads a JSON column
- **THEN** the data is validated against a schema (Zod, Yup, or equivalent) before use, with a fallback for malformed data

#### Scenario: JSON column write without size bounds

- **WHEN** a user-controlled JSON field has no size limit on write
- **THEN** an attacker can store arbitrarily large payloads, causing storage and performance issues
