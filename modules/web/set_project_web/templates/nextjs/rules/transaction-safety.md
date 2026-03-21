---
paths:
  - "src/server/**"
  - "src/app/api/**"
  - "src/actions/**"
  - "src/lib/**"
---
# Transaction Safety

## Payment Transaction Ordering
Payment capture MUST happen AFTER the order record exists — never before. Create → Charge → Confirm. On failure, the order record exists for debugging.

```typescript
// WRONG: charge before record
const payment = await processPayment(cart.total)
const order = await db.order.create({ ... })  // if this fails, money gone

// CORRECT: create first, then charge
const order = await db.order.create({ data: { status: "PENDING", ... } })
try {
  const payment = await processPayment(order.total)
  await db.order.update({ where: { id: order.id }, data: { status: "CONFIRMED" } })
} catch (e) {
  await db.order.update({ where: { id: order.id }, data: { status: "PAYMENT_FAILED" } })
  throw e
}
```

## Atomic Finite Resource Operations
Stock, gift card balances, coupon usage limits — any finite resource check-and-decrement MUST be a single atomic operation inside a transaction.

```typescript
// WRONG: separate check and decrement (race condition)
const gc = await db.giftCard.findUnique({ where: { code } })
if (gc.balance < amount) throw new Error("Insufficient")
await db.giftCard.update({ data: { balance: { decrement: amount } } })

// CORRECT: atomic conditional update
const updated = await tx.giftCard.updateMany({
  where: { id: gcId, balance: { gte: amount } },
  data: { balance: { decrement: amount } }
})
if (updated.count === 0) throw new Error("Insufficient balance")
```

## Payment Failure Rollback
When checkout has multiple side effects (stock, coupon, gift card), ALL must be reversed on payment failure. Apply side effects AFTER payment, or explicitly reverse in catch block.

## Soft Status Transitions
Records involving financial transactions MUST use status transitions, never hard deletes. Orders, subscriptions, payments use PENDING → CONFIRMED / PAYMENT_FAILED — never `delete()` on failure. The record must exist for customer support, debugging, and compliance.

## Server-Side Price Recalculation
ALL monetary values MUST be recalculated server-side. The client sends WHAT (item IDs, quantities), the server decides HOW MUCH. Never trust client-supplied prices, shipping costs, or discount amounts.

## Single Source of Truth for Validation
When business logic validates at multiple points (cart preview + checkout), extract into one shared function. Both paths MUST call the same function — the checkout path will always be weaker if re-implemented inline.
