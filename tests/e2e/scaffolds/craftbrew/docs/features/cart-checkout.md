# Cart & Checkout Feature

## Cart

### Adding to Cart

- "Add to Cart" button on the product details page
- Required: variant selection (if available)
- Quantity selector (default: 1)
- Validation: stock > 0, quantity <= stock
- Toast message on successful addition
- Layout header: cart icon with badge (item count)

### Cart Page

### Cart Mobile

- Items displayed in vertical list
- Quantity +/- buttons minimum 44px touch target

### Cart Business Rules

- Same product+variant added again → quantity increase
- Reducing quantity to 0 → item removal
- Coupon and gift card can be applied simultaneously
- Coupons are NOT stackable (max 1 coupon/order)
- Gift card deducts from the post-coupon amount
- Promo day discount is automatic (not a coupon — stackable with coupons)
- Cart is session-based for anonymous users, user-bound for logged-in users
- On login: anonymous cart merges into the user's cart
- Cart items do NOT reserve stock — stock is checked at checkout time
- When returning to cart, items with changed availability show a warning

## 3-Step Checkout

"Proceed to Checkout" button → login required (redirect to login if not authenticated).

### Step 1: Shipping

**Automatic zone detection based on postal code:**
- 1000-1999: Budapest → 990 Ft (free above 15 000 Ft)
- 2000-2199: +20km → 1 490 Ft (free above 25 000 Ft)
- All others: +40km → 2 490 Ft (no free shipping threshold)
- In-store pickup: always free

### Step 2: Payment

**Zero-amount checkout:** If gift card covers the entire order amount (0 Ft payable), Step 2 (Payment) is skipped — checkout goes directly from Step 1 (Shipping) to Step 3 (Confirmation).

### Step 3: Confirmation

### Checkout Mobile

- Checkout steps arranged vertically (not horizontal stepper)
- All form fields full width
- "Pay" button sticky at bottom of viewport

## Order Processing

Order processing is transactional — the following steps happen atomically:
1. Fetch cart items
2. Stock check for every item
3. Process payment
4. Create order (price snapshot!)
5. Decrease stock
6. Increment coupon usage (if applicable)
7. Decrease gift card balance (if applicable)
8. Clear cart
9. Generate invoice (mock)
10. Send email (order confirmation)

If any step fails → full rollback.

**Stock conflict at checkout:** If any item's requested quantity exceeds available stock at checkout time, an error is shown with current availability. The user returns to cart with updated stock info and can adjust quantities. Items that went out of stock are marked with a warning.

### Order Cancellation

- Admin cancels order → Stripe refund (for card-paid portion only)
- Gift card balance restored
- Coupon usage count decremented
- Stock restored
- Orders in SHIPPING or DELIVERED status cannot be cancelled
- Customers may also request cancellation from their "My Orders" page (orders in NEW or PROCESSING status only)

## Returns & Right of Withdrawal

- EU 14-day right of withdrawal applies to all physical products
- Customer can initiate a return request from "My Orders" page (within 14 days of delivery)
- Return request requires: order number, reason (dropdown: "Changed my mind", "Defective", "Wrong item", "Other"), optional comment
- Admin reviews return requests: approve → provide return shipping instructions, or reject with reason
- Approved returns: once product received back → Stripe refund processed, stock restored
- Food safety: **opened coffee packages cannot be returned** (hygiene exception per EU rules). Only sealed/unopened coffee is eligible.
- Equipment and merch: standard 14-day returns, must be unused and in original packaging
- Gift cards: non-refundable

## Invoicing

- Every completed order generates an invoice via szamlazz.hu
- The invoice PDF is downloadable from both the admin panel and the user's order history
- All prices are gross (VAT-inclusive). Hungarian VAT rate: 27%.
- Invoice must show: net amount, VAT amount (27%), gross amount, per line item and in total

## Shipping Zones

### Zones

| Zone | Postal code range | Shipping fee | Free shipping threshold |
|---|---|---|---|
| Budapest | 1000-1999 | 990 Ft | Above 15 000 Ft |
| +20km | 2000-2199 | 1 490 Ft | Above 25 000 Ft |
| +40km | All others | 2 490 Ft | None |
| In-store Pickup | — | Free | — |

### Zone Detection

The zone is automatically determined upon postal code entry:
- Based on 4-digit Hungarian postal codes
- The zone and shipping fee appear instantly in checkout
- If the postal code is unrecognized: default +40km zone

### Estimated Delivery Time

- **Budapest:** next business day
- **+20km zone:** 1-2 business days
- **+40km zone:** 2-3 business days
- **In-store pickup:** same day if ordered before 14:00, otherwise next business day
- Business days: Monday-Friday (excluding Hungarian public holidays)
- The estimated delivery date is shown at checkout and in the order confirmation email

### In-store Pickup

Pickup location:
- **Name:** CraftBrew Labor
- **Address:** Kazinczy u. 28, 1075 Budapest
- **Hours:** Mon-Fri 7:00-18:00, Sat 8:00-14:00, Sun closed
- **Fee:** Free

When in-store pickup is selected, no shipping address is required (but the billing address is still needed).

### Subscription Shipping

| Zone | Daily delivery | Weekly/biweekly/monthly |
|---|---|---|
| Budapest | 14 990 Ft/month flat | Normal rate/shipment |
| +20km | 24 990 Ft/month flat | Normal rate/shipment |
| +40km | NOT AVAILABLE | Normal rate/shipment |

Daily delivery restriction: if the user's address zone is +40km, the "Daily" frequency option is disabled, with tooltip: "Daily delivery is only available in Budapest and within the 20km zone."

### Free Shipping Logic

1. Calculate cart value (BEFORE discounts, gross amount)
2. Determine zone based on shipping address
3. If cart value >= free shipping threshold → shipping fee = 0 Ft
4. If no free shipping threshold (+40km) → always charged
5. On the cart page: "Only X Ft more for free shipping!" message (if relevant)
