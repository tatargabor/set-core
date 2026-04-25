# User Accounts Feature

## Registration

Form fields:
- **Name** (required, min 2 characters)
- **Email** (required, valid email format, unique)
- **Password** (required, min 8 characters)
- **Password confirmation** (match validation)
- **Language preference** (HU / EN, default: current language)
- **Terms & Conditions** (required checkbox: "I accept the Terms & Conditions and Privacy Policy" — with links)

After successful registration:
- Automatic login
- Welcome email sent (in the chosen language)
- Redirect to the profile page

Inline validation — errors appear below the fields.

## Login

- Email + password
- "Remember me" checkbox (session extension)
- Wrong password: "Invalid email or password" (does not reveal which one is wrong)
- Successful login → redirect to the previous page (or the profile page)

## Password Reset

- "Forgot password?" link on the login page below the password field
- User enters their email → system sends a reset email with a time-limited token (valid for 1 hour)
- Reset page (`/reset-password?token=...`): new password + password confirmation fields
- On success: redirect to login page with a confirmation message ("Password updated successfully")
- Invalid or expired token: error message with a link to request a new reset email

## Profile Page

## My Addresses

Address fields:
- Label (e.g., "Home", "Office") — required
- Name — required
- Postal code — required, automatic zone detection
- City — required
- Street, house number — required
- Phone — required
- Default flag — only one address can be the default

## My Orders

Order list DataTable:
- Order number (#1042)
- Date
- Status badge (New / Processing / Packed / Shipping / Delivered / Cancelled)
- Amount
- [Details] button

Order details (modal or separate page):
- Line items list (product, variant, quantity, unit price, subtotal)
- Shipping address
- Discount/gift card if applicable
- Shipping fee
- Grand total
- Payment identifier
- Invoice download (PDF)
- Status timeline (when it went PROCESSING → PACKED → SHIPPING → DELIVERED)

## Mobile

- Account sidebar collapses into a drawer
- All forms render full width

## Notification Preferences

On the profile page, a "Notifications" section:
- **Promo emails:** opt-in/opt-out toggle (default: on for new users)
- **Restock alerts:** managed per-product via wishlist (see reviews-wishlist.md)
- **Order updates:** always sent (cannot be disabled — transactional)
- Unsubscribe link in every promotional email → directly toggles the preference

## Legal Pages

The following static pages must exist (linked from the footer):
- **Terms & Conditions** (`/hu/aszf`, `/en/terms`) — placeholder content in seed data
- **Privacy Policy** (`/hu/adatvedelem`, `/en/privacy`) — placeholder content in seed data
- **Cookie Policy** — brief banner on first visit: "We use cookies for session management and language preference." Accept / Decline buttons. No tracking cookies in v1.

## Behavior Without Login

- Storefront (products, stories, search): full access
- Cart: session-based, works without login
- Checkout: login required → redirect to login → after successful login, return to cart
- Cart merge: anonymous cart transfers to the user's cart on login
