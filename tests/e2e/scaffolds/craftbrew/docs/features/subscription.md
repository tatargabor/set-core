# Subscription & Delivery Feature

> **Figma frames:** Subscription Wizard, User Subscriptions & Calendar — see [design-system.md](../design/design-system.md#frame-mapping)

## Subscription Concept

Registered users can order regular coffee deliveries. A subscription is for a selected coffee, with a specified frequency and delivery time window.

## Subscription Setup

```
┌─────────────────────────────────────────────────────────┐
│  Coffee Subscription                                     │
│                                                          │
│  "Fresh coffee, delivered to your doorstep regularly."   │
│                                                          │
│  1. Choose your coffee:                                  │
│  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐   │
│  │ Ethiopia │ │ Colombia │ │ Brazil   │ │ ...      │   │
│  │ 2490 Ft/ │ │ 2890 Ft/ │ │ 1990 Ft/ │ │          │   │
│  │ 250g     │ │ 250g     │ │ 250g     │ │          │   │
│  └──────────┘ └──────────┘ └──────────┘ └──────────┘   │
│                                                          │
│  2. Form and size:                                       │
│  Form: [Whole Bean ▼]  Size: ○ 250g ● 500g ○ 1kg       │
│  Grind: [— whole bean, not needed —]                     │
│                                                          │
│  3. Frequency:                                           │
│  ○ Daily delivery        -15%    (53 Ft/day shipping)   │
│  ○ Weekly (every Monday) -10%                            │
│  ● Biweekly              -7%                             │
│  ○ Monthly               -5%                             │
│                                                          │
│  4. Delivery time window:                                │
│  ○ Morning (6:00 - 9:00)                                │
│  ● Forenoon (9:00 - 12:00)                              │
│  ○ Afternoon (14:00 - 17:00)                             │
│                                                          │
│  5. Shipping address:                                    │
│  [Select saved address ▼]                                │
│                                                          │
│  6. Start date:                                          │
│  [2026-03-15 ▼] (earliest: tomorrow)                    │
│                                                          │
│  ┌─ Summary ─────────────────────────────────────────┐ │
│  │ Colombia Huila, whole bean, 500g                    │ │
│  │ Delivered biweekly                                  │ │
│  │ Unit price: 5 480 Ft                                │ │
│  │ Subscription discount (-7%): -384 Ft                │ │
│  │ Subscription price: 5 096 Ft / shipment             │ │
│  │ Shipping: 1 490 Ft / shipment (+20km)               │ │
│  │ Total: 6 586 Ft / 2 weeks                           │ │
│  └────────────────────────────────────────────────────┘ │
│                                                          │
│  [████████ Start Subscription ████████]                   │
│  Card payment. Cancel anytime.                           │
│                                                          │
└─────────────────────────────────────────────────────────┘
```

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

```
┌─────────────────────────────────────────────────────────┐
│  My Subscriptions                                        │
│                                                          │
│  ┌─ Colombia Huila, whole bean, 500g ───────────────┐   │
│  │ Status: 🟢 Active                                │   │
│  │ Frequency: Biweekly                               │   │
│  │ Next delivery: 2026-03-15 (Forenoon)              │   │
│  │ Subscription price: 5 096 Ft + 1 490 Ft shipping  │   │
│  │                                                   │   │
│  │ [Modify] [Pause] [Skip Next]                       │   │
│  │ [Cancel]                                          │   │
│  └───────────────────────────────────────────────────┘   │
│                                                          │
│  ┌─ Calendar View ────────────────────────────────────┐│
│  │      March 2026                                      ││
│  │  M   T   W  Th  F  Sat  S                          ││
│  │                          1                          ││
│  │  2   3   4   5  6   7   8                          ││
│  │  9  10  11  12 13  14  ☕15                         ││
│  │ 16  17  18  19 20  21  22                          ││
│  │ 23  24  25  26 27  28  ☕29                         ││
│  │ 30  31                                              ││
│  │                                                     ││
│  │  ☕ = delivery  ⏸ = skipped  ❌ = paused              ││
│  └─────────────────────────────────────────────────────┘│
│                                                          │
└─────────────────────────────────────────────────────────┘
```

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

## Design Reference

Use exact values from `docs/design-system.md` — do NOT use framework defaults.

**Key colors**: primary `#78350F`, secondary `#D97706`, background `#FFFBEB`
**Fonts**: Playfair Display, Inter, JetBrains Mono

**Matched pages:**
- **Checkout**: Uses: Button
- **Admin**: see design-system.md § Page Layouts
- **Auth**: see design-system.md § Page Layouts
- **Subscription**: see design-system.md § Page Layouts
