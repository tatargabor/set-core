---
description: Transaction safety patterns — payment ordering, price validation, atomic inventory
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

## 3. Atomic Inventory Operations

Stock check and decrement MUST be a single atomic operation. Separate check-then-decrement causes oversell race conditions.

**Wrong — non-atomic check then decrement (two concurrent checkouts both pass):**
```
// FORBIDDEN: separate check and decrement
const variant = await db.productVariant.findUnique({ where: { id } })
if (variant.stock < quantity) throw new Error("Out of stock")
// Race window: another request reads same stock value here
await db.productVariant.update({
  where: { id },
  data: { stock: { decrement: quantity } }
})
```

**Correct — atomic conditional update inside transaction:**
```
const result = await db.$transaction(async (tx) => {
  // Atomic: only decrements if stock >= quantity
  const updated = await tx.productVariant.updateMany({
    where: { id: variantId, stock: { gte: quantity } },
    data: { stock: { decrement: quantity } }
  })

  if (updated.count === 0) {
    throw new Error("Insufficient stock")  // aborts transaction
  }

  return tx.order.create({ data: { ... } })
})
```

**The rule:** Use conditional update (`WHERE stock >= quantity`) inside a database transaction. Check the result count — `0` means insufficient stock. Never separate the check from the decrement.

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
