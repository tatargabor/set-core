# Subscription & Delivery Feature

## Subscription Concept

Registered users can order regular coffee deliveries. A subscription is for a selected coffee, with a specified frequency and delivery time window.

## Subscription Setup

## Pricing Rules

| Frequency | Discount | Shipping |
|---|---|---|
| Daily | -15% | Budapest: 14 990 Ft/month flat, +20km: 24 990 Ft/month flat, +40km: NOT AVAILABLE |
| Weekly | -10% | Normal zone rate per shipment |
| Biweekly | -7% | Normal zone rate per shipment |
| Monthly | -5% | Normal zone rate per shipment |

Daily delivery is not available in the +40km zone (zone check based on address).

## Subscription Management

On the logged-in user's dashboard:

## Actions

### Modify
- Swap coffee (to a different coffee)
- Change packaging size
- Change form/grind
- Change frequency
- Change time window
- Change address
- Modification takes effect from the NEXT shipment

### Pause
- Specify from-date to to-date
- No shipments are generated during the pause
- Automatically resumes after the pause ends
- Marked with ❌ icon in the calendar

### Skip Individual Delivery
- "Skip the next shipment" button
- Skips one specific date
- Marked with ⏸ icon in the calendar

### Cancel
- Confirmation dialog: "Are you sure you want to cancel your subscription?"
- Two options: "Cancel immediately" / "At end of cycle"
- After cancellation, the subscription changes to CANCELLED status
- Payment subscription is cancelled

## Billing

- Daily delivery: monthly summary invoice, at end of month
- Weekly/biweekly/monthly: invoice per shipment
- Billing cycle is aligned with the start date
- Invoice generation: same mock system as one-time orders

## Payment Subscription

- Subscription is created at launch
- First payment is charged immediately at subscription creation
- Subsequent payments are charged 1 day before each scheduled delivery
- Modification: when coffee, frequency, address, etc. changes — price difference applied from next billing
- Cancellation: immediate (no further charges) or at end of cycle (last paid delivery still ships)
- Billing cycle start point: the start date
- Successful payment → shipment generation added to the schedule

## Payment Failure

- Failed payment → 3 automatic retries over 7 days (Stripe default)
- After 3 failures → subscription paused automatically, user notified by email
- User can update payment method and reactivate from their dashboard
- Deliveries stop during payment failure period

## Mobile

- Subscription setup wizard steps arranged vertically
- Calendar view in compact format
- All action buttons (pause, skip, modify, cancel) easily tappable

## Out-of-Stock Handling

If the subscribed coffee goes out of stock, the system should handle it gracefully and notify the customer.

## Subscriptions and Promotions

- Coupons are not applicable to subscriptions (subscriptions already have frequency-based discounts)
- Promo day automatic discounts do not apply to subscription deliveries
