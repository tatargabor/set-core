---
description: Database schema integrity — unique constraints, status modeling, FK cascades, JSON columns
globs:
  - "prisma/**/*.prisma"
  - "drizzle/**/*.ts"
  - "src/**/*.{ts,tsx,js,jsx}"
  - "app/**/*.{ts,tsx,js,jsx}"
  - "server/**/*.{ts,tsx,js,jsx}"
---

# Schema Integrity Patterns

These patterns prevent data modeling bugs that cause silent data loss, constraint violations, or inconsistent state.

## 1. Nullable Columns in Unique Constraints

Unique constraints that include nullable columns do NOT prevent duplicates when the nullable column is NULL (most databases treat each NULL as distinct).

**Wrong — unique constraint with nullable column:**
```prisma
model RestockNotification {
  userId    String
  variantId String
  notifiedAt DateTime?
  @@unique([userId, variantId, notifiedAt])
  // Two rows with NULL notifiedAt are NOT considered duplicates!
  // User can sign up for the same restock notification multiple times
}
```

**Correct — use non-nullable columns or a sentinel value:**
```prisma
// Option A: unique on non-nullable columns only
model RestockNotification {
  userId    String
  variantId String
  notifiedAt DateTime?
  @@unique([userId, variantId])  // use notifiedAt as a status flag, not part of uniqueness
}

// Option B: sentinel value instead of null
model RestockNotification {
  userId    String
  variantId String
  notifiedAt DateTime @default("1970-01-01T00:00:00Z")  // sentinel = "not yet notified"
  @@unique([userId, variantId, notifiedAt])
}
```

**The rule:** Never include nullable columns in unique constraints. Use the non-nullable subset for uniqueness and treat the nullable column as a status flag. If the nullable column MUST be part of uniqueness, use a sentinel value instead of NULL.

## 2. Boolean vs Enum Status Modeling

When a record has more than two meaningful states, use an explicit enum — not a boolean. A boolean can only represent two states; overloading it loses information.

**Wrong — boolean for multi-state (pending vs rejected indistinguishable):**
```prisma
model Review {
  approved Boolean @default(false)
  // false = never reviewed (pending) OR explicitly rejected
  // No way to distinguish, no way to query "show rejected reviews"
}
```

**Correct — enum captures all states:**
```prisma
enum ReviewStatus {
  PENDING
  APPROVED
  REJECTED
}

model Review {
  status ReviewStatus @default(PENDING)
  // Clear: PENDING = awaiting review, REJECTED = admin said no, APPROVED = published
}
```

**The rule:** If a field can be in more than two meaningful states, use an enum. Booleans are fine for true binary choices (isActive, isPublished) where there's no third state. When in doubt, use an enum — it's easy to add states later, impossible to un-overload a boolean.

## 3. FK Cascade Strategies for Active Records

Foreign keys on records with an "active" lifecycle (subscriptions, recurring payments, active orders) MUST use RESTRICT on delete, not SET NULL or CASCADE.

**Wrong — SET NULL silently breaks active subscriptions:**
```prisma
model Subscription {
  shippingAddressId String? @relation(onDelete: SetNull)
  // If user deletes their address, active subscription silently loses delivery address
  // Next billing cycle: crash or ship to nowhere
}
```

**Correct — RESTRICT prevents deletion of referenced records:**
```prisma
model Subscription {
  shippingAddressId String @relation(onDelete: Restrict)
  // Deleting an address with active subscriptions fails with a clear error
  // Application must handle: pause subscription first, or require address update
}
```

**The rule:** For FKs referenced by active records (subscriptions, orders in progress, recurring payments), use `Restrict` on delete. The application must check for active references before allowing deletion. `SetNull` is only safe for optional/archival FKs where a missing reference is a valid state (e.g., "deleted user" on an old log entry).

## 4. JSON Column Validation

JSON/JSONB columns MUST have runtime type validation on read and size bounds on write.

**Wrong — direct property access, no validation, unbounded growth:**
```typescript
// Reading: no type check — could be anything
const skipDates = subscription.skipDates as string[]  // could be null, number, corrupt JSON

// Writing: no size limit — grows forever
const dates = subscription.skipDates as any[]
dates.push(newDate)  // array grows unbounded
await db.subscription.update({ data: { skipDates: dates } })
```

**Correct — validate on read, bound on write:**
```typescript
// Reading: validate shape
const raw = subscription.skipDates
const skipDates: string[] = Array.isArray(raw)
  ? raw.filter((d): d is string => typeof d === 'string')
  : []

// Writing: enforce bounds
const MAX_SKIP_DATES = 52  // 1 year of weekly skips
if (skipDates.length >= MAX_SKIP_DATES) {
  throw new Error("Maximum skip limit reached")
}
skipDates.push(newDate.toISOString())
await db.subscription.update({ data: { skipDates } })
```

**The rule:** JSON columns MUST have: (1) runtime type validation on read (never cast to `any` or assume shape), (2) size/growth bounds on write (prevent unbounded arrays), (3) a documented schema even if just a TypeScript type or Zod schema. Prefer typed columns over JSON when the shape is known at design time.
