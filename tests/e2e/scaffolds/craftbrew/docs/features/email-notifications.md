# Email Notifications Feature

## General Rules

- **Language:** Emails are sent according to the user's language preference (HU or EN). If there is no logged-in user (e.g., gift card recipient), the default is HU. All example subjects and CTA text below are shown in English.

## Email Types

### 1. Welcome (registration)

**Trigger:** Successful user registration
**Recipient:** The new user

Content:
- Subject: "Welcome to CraftBrew! ☕"
- Welcome text with the user's name
- Brief introduction to CraftBrew
- CTA button: "Browse our coffees" → coffee list page
- Subscription suggestion: "Order your favorite coffee on a regular basis!"

### 2. Password Reset

**Trigger:** User clicks "Forgot password?" and submits their email address
**Recipient:** The user (if the email exists in the system)

Content:
- Subject: "Reset Your CraftBrew Password"
- Brief explanation: "We received a request to reset your password"
- Reset link with a time-limited token (valid for 1 hour)
- Security note: "If you didn't request this, you can safely ignore this email"
- CTA button: "Reset Password" → reset password page with token

### 3. Order Confirmation

**Trigger:** Successful order (payment OK)
**Recipient:** The ordering user

Content:
- Subject: "Order confirmation — #1042"
- Order number and date
- Line items list (product, variant, quantity, price)
- Subtotal, discount (if any), shipping fee, grand total
- Shipping address
- Expected delivery time
- CTA: "View my order" → my orders page
- Invoice PDF attachment (mock)

### 4. Shipping Notification

**Trigger:** Admin sets order status to SHIPPING
**Recipient:** The ordering user

Content:
- Subject: "Your order is on its way! 🚚 — #1042"
- Order number
- Shipping address
- Expected delivery (order + 1-2 business days)
- CTA: "Track my order" → my orders page

### 5. Delivery + Review Request

**Trigger:** Admin sets order status to DELIVERED
**Recipient:** The ordering user

Content:
- Subject: "Your order has arrived! How did you like it? ☕"
- Brief thank you text
- List of ordered products
- For each product: "Rate it!" button → product details page #reviews
- CTA: "Write a review" → first product's review page

### 6. Restock Notification

**Trigger:** Admin restocks inventory (stock 0 → >0) for a product/variant
**Recipient:** Every user who requested a "back in stock" notification for this product

Content:
- Subject: "Back in stock: Ethiopia Yirgacheffe! ☕"
- Product name and image
- CTA: "Order now" → product details page
- After sending: notification is deactivated (one-time notification)

### 7. Promo Day Announcement

**Trigger:** Promo day date matches today, and the email has not been sent yet
**Recipient:** All registered users

Content:
- Subject: "🎉 CraftBrew turns 1! 20% off everything!"
- Banner text
- Discount details
- CTA: "Shop now!" → homepage
- After sending: marked as sent (does not send again)

### 8. Gift Card Delivery

**Trigger:** Successful gift card purchase
**Recipient:** The specified RECIPIENT email (not the buyer!)

Content:
- Subject: "You received a CraftBrew gift card! 🎁"
- Sender name (the buyer's name)
- Personal message (if provided)
- Gift card code: `GC-XXXX-XXXX`
- Amount: e.g., "10 000 Ft"
- CTA: "Redeem in the webshop" → homepage
- Validity: "Valid for 1 year"
