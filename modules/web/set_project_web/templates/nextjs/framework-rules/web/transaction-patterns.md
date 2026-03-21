---
description: Transaction safety patterns — payment ordering, price validation, atomic resources, rollback
globs:
  - "src/**/*.{ts,tsx,js,jsx}"
  - "app/**/*.{ts,tsx,js,jsx}"
  - "api/**/*.{ts,tsx,js,jsx,py}"
  - "routes/**/*.{ts,tsx,js,jsx,py}"
  - "server/**/*.{ts,tsx,js,jsx,py}"
  - "lib/**/*.{ts,tsx,js,jsx,py}"
---

# Transaction Safety Patterns

These patterns prevent business logic bugs that cause financial loss, data inconsistency, or customer-facing failures. They apply to any e-commerce, payment, or inventory system.

## 1. Payment Transaction Ordering

Payment capture MUST happen AFTER the order record exists — never before.

**Wrong — payment before record (customer charged with no order, no refund path):**
```
// FORBIDDEN: charge first, create record second
const payment = await processPayment(cart.total)
const order = await db.order.create({ data: { ... } })  // if this fails, money is gone
```

**Correct — create record first, then charge, then confirm:**
```
// 1. Create order in PENDING status
const order = await db.order.create({
  data: { status: "PENDING", total: serverCalculatedTotal, userId, items }
})

// 2. Attempt payment
try {
  const payment = await processPayment(order.total, { orderId: order.id })
  // 3. Confirm order
  await db.order.update({ where: { id: order.id }, data: { status: "CONFIRMED", paymentId: payment.id } })
} catch (e) {
  // 4. Rollback on failure
  await db.order.update({ where: { id: order.id }, data: { status: "CANCELLED" } })
  throw e
}
```

**The rule:** Create → Charge → Confirm. Never Charge → Create. On payment failure, the order record exists for debugging and customer support.

## 2. Server-Side Price Recalculation

ALL monetary values (prices, totals, shipping costs, discounts) MUST be recalculated server-side. Never trust client-supplied amounts.

**Wrong — trusts client-supplied shipping cost (attacker sends 0 or negative):**
```
// FORBIDDEN: using body.shippingCost directly
const { items, shippingCost } = await request.json()
const total = itemsTotal + shippingCost  // attacker controls this
```

**Correct — recalculate everything server-side:**
```
const { items, shippingAddress } = await request.json()

// Recalculate prices from database (not from client)
const dbItems = await db.product.findMany({ where: { id: { in: items.map(i => i.id) } } })
const itemsTotal = dbItems.reduce((sum, item) => sum + item.price * getQuantity(items, item.id), 0)

// Recalculate shipping from server-side logic
const shippingCost = calculateShipping(shippingAddress.postalCode)

const total = itemsTotal + shippingCost
```

**The rule:** The client sends WHAT they want (item IDs, quantities, addresses). The server decides HOW MUCH it costs. This applies to: item prices, shipping costs, tax amounts, discount values, order totals.

## 3. Atomic Finite Resource Operations

Any finite resource check-and-decrement MUST be a single atomic operation. This applies to stock, gift card balances, coupon usage limits, seat counts, and quota allocations. Separate check-then-decrement causes race conditions.

**Wrong — non-atomic check then decrement (two concurrent checkouts both pass):**
```
// FORBIDDEN: separate check and decrement — applies to ALL finite resources
const variant = await db.productVariant.findUnique({ where: { id } })
if (variant.stock < quantity) throw new Error("Out of stock")
// Race window: another request reads same stock value here
await db.productVariant.update({
  where: { id },
  data: { stock: { decrement: quantity } }
})

// Same bug with gift cards:
const gc = await db.giftCard.findUnique({ where: { code } })
if (gc.balance < amount) throw new Error("Insufficient balance")
await db.giftCard.update({ where: { id: gc.id }, data: { balance: { decrement: amount } } })

// Same bug with coupons:
const coupon = await db.coupon.findUnique({ where: { code } })
if (coupon.usageCount >= coupon.maxUsage) throw new Error("Coupon exhausted")
await db.coupon.update({ where: { id: coupon.id }, data: { usageCount: { increment: 1 } } })
```

**Correct — atomic conditional update inside transaction:**
```
await db.$transaction(async (tx) => {
  // Stock: atomic decrement
  const stockUpdate = await tx.productVariant.updateMany({
    where: { id: variantId, stock: { gte: quantity } },
    data: { stock: { decrement: quantity } }
  })
  if (stockUpdate.count === 0) throw new Error("Insufficient stock")

  // Gift card: atomic balance deduction
  const gcUpdate = await tx.giftCard.updateMany({
    where: { id: gcId, balance: { gte: gcAmount } },
    data: { balance: { decrement: gcAmount } }
  })
  if (gcUpdate.count === 0) throw new Error("Insufficient gift card balance")

  // Coupon: atomic usage increment
  const couponUpdate = await tx.coupon.updateMany({
    where: { id: couponId, usageCount: { lt: maxUsage } },
    data: { usageCount: { increment: 1 } }
  })
  if (couponUpdate.count === 0) throw new Error("Coupon usage limit reached")

  return tx.order.create({ data: { ... } })
})
```

**The rule:** Use conditional update (`WHERE resource >= needed`) inside a database transaction for ANY finite resource — not just stock. Check the result count — `0` means the resource was insufficient. Never read-check-then-mutate across separate operations.

## 4. Idempotent Order Creation

Order creation endpoints MUST be idempotent to prevent duplicate charges on retry/refresh.

**Pattern:**
```
// Use client-generated idempotency key
const { idempotencyKey } = await request.json()
const existing = await db.order.findUnique({ where: { idempotencyKey } })
if (existing) return existing  // return same result, don't re-charge

const order = await createOrder(...)
```

**The rule:** Accept an idempotency key from the client. If the key already exists, return the existing result without re-processing. This prevents double-charges on network retries, browser refresh, or mobile app retry.

## 5. Payment Failure Rollback of Side Effects

When checkout has multiple side effects (stock decrement, coupon usage increment, gift card balance deduction), ALL must be reversed on payment failure.

**Wrong — side effects applied before payment, no reversal on failure:**
```
const result = await db.$transaction(async (tx) => {
  // Side effects happen BEFORE payment — irreversible if payment fails
  await tx.productVariant.updateMany({ where: { id, stock: { gte: qty } }, data: { stock: { decrement: qty } } })
  await tx.coupon.update({ where: { id: couponId }, data: { usageCount: { increment: 1 } } })
  await tx.giftCard.update({ where: { id: gcId }, data: { balance: { decrement: gcAmount } } })
  return tx.order.create({ data: { status: "PENDING", ... } })
})
// Payment OUTSIDE transaction — if this fails, stock/coupon/GC already mutated
const payment = await processPayment(result.total)
```

**Correct — side effects after payment, or explicit reversal in catch:**
```
// Option A (preferred): side effects AFTER successful payment
const order = await db.order.create({ data: { status: "PENDING", ... } })
const payment = await processPayment(order.total, { orderId: order.id })
// Only now apply side effects — payment succeeded
await db.$transaction(async (tx) => {
  await tx.productVariant.updateMany({ where: { id, stock: { gte: qty } }, data: { stock: { decrement: qty } } })
  await tx.coupon.update({ where: { id: couponId }, data: { usageCount: { increment: 1 } } })
  await tx.giftCard.update({ where: { id: gcId }, data: { balance: { decrement: gcAmount } } })
  await tx.order.update({ where: { id: order.id }, data: { status: "CONFIRMED" } })
})

// Option B: side effects before payment, explicit reversal on failure
try {
  const payment = await processPayment(order.total)
} catch (e) {
  await db.$transaction(async (tx) => {
    await tx.productVariant.update({ where: { id }, data: { stock: { increment: qty } } })
    await tx.coupon.update({ where: { id: couponId }, data: { usageCount: { decrement: 1 } } })
    await tx.giftCard.update({ where: { id: gcId }, data: { balance: { increment: gcAmount } } })
    await tx.order.update({ where: { id: order.id }, data: { status: "PAYMENT_FAILED" } })
  })
  throw e
}
```

**The rule:** If checkout applies multiple side effects (stock, coupon, gift card, loyalty points), either apply them AFTER payment succeeds, or explicitly reverse ALL of them in the payment failure catch block. Never leave side effects partially applied.

## 6. Soft Status Transitions for Financial Records

Records involving financial transactions MUST use status transitions, never hard deletes.

**Wrong — hard delete on payment failure (destroys audit trail):**
```
// FORBIDDEN: delete on failure
try {
  await processPayment(subscription.total)
} catch (e) {
  await db.subscription.delete({ where: { id: subscription.id } })
  return { error: "Payment failed" }
}
```

**Correct — status transition preserves the record:**
```
try {
  await processPayment(subscription.total)
} catch (e) {
  await db.subscription.update({
    where: { id: subscription.id },
    data: { status: "PAYMENT_FAILED", failedAt: new Date(), failureReason: e.message }
  })
  return { error: "Payment failed" }
}
```

**The rule:** Orders, subscriptions, payments, refunds, and gift card redemptions MUST use status transitions (PENDING → PAYMENT_FAILED), never hard deletes on failure. The record must exist for: customer support lookup, debugging, compliance auditing, and payment retry logic.
