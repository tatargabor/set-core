# Design Brief

Per-page visual specifications for implementing agents.
Each page section describes layout, components, and responsive behavior.

## Page: Home

Container: 1280px max-width, centered
Background: #FFFBEB

Sections (top to bottom):

1. Header Component
   - Sticky, z-index: 50
   - Height: 80px

2. Hero Banner
   - Height: 500px
   - Background: Coffee image (use Unsplash - warm, inviting)
   - Overlay: linear-gradient(to right, rgba(255,251,235,0.95) 0%, rgba(255,251,235,0.3) 100%)
   - Content (left-aligned, 50% width):
     * H1: "Specialty kávé, az asztalodra szállítva." (#1C1917)
     * Subtitle: Inter Regular 18px (#78716C)
     * CTA Button: Primary, "Fedezd fel kávéinkat →"

3. Featured Coffees Section
   - Padding: 96px 0
   - Background: #FFFBEB
   - Title: H2, center-aligned, "Kedvenceink"
   - Grid: 4 columns, gap 24px
   - Product Cards: 4 items
   - View All Link: #D97706, center, "Összes kávé →"

4. Subscription CTA Section
   - Padding: 96px 0
   - Background: #FFFFFF
   - Layout: 2-column (Image 50% | Content 50%)
   - Left: Coffee delivery image
   - Right: 
     * H2: "Friss kávé minden reggel"
     * Body text: #78716C
     * CTA: Outlined Button, "Előfizetés részletei →"

5. Story Highlights
   - Padding: 96px 0
   - Background: #FFFBEB
   - Title: H2, center, "Sztorik"
   - Grid: 3 columns, gap 24px
   - Story Cards: 
     * Image 16:9
     * bg #FFFFFF
     * Category badge
     * Title, date
   - "Összes sztori →" link

6. Testimonials
   - Padding: 96px 0
   - Background: #FFFFFF
   - Title: H2, center, "Mit mondanak vásárlóink"
   - Grid: 3 columns, gap 24px
   - Review Cards:
     * bg #FFFBEB
     * border: 1px solid #E7E5E4
     * padding: 32px
     * Stars, quote (italic), customer name, product name

7. Footer Component
   - See footer component spec

## Page: ProductCatalog

Layout: Sidebar (280px) + Main (remainder)

Sidebar (Filters):
- Background: #FFFFFF
- Padding: 24px
- Border Right: 1px solid #E7E5E4
- Sticky position

Filter Sections:
1. Header
   - "Szűrők" (H3)
   - "Törlés" link (#D97706)

2. Origin (Checkbox group)
   - Label: Inter Medium 16px
   - Checkboxes: 24×24px
   - Gap: 12px
   - Border bottom: 1px solid #E7E5E4
   - Padding: 16px 0

3. Roast Level
4. Processing Method
5. Price Range Slider
   - Track: #E7E5E4
   - Fill: #D97706
   - Thumb: 20×20px circle, #78350F
   - Min/Max inputs below

Main Area:
- Padding: 24px
- Background: #FFFBEB
- Top Row: Sorting dropdown (right-aligned)
- Product Grid: 3 columns, gap 24px
- 9-12 products visible
- Pagination at bottom

## Page: ProductDetail

Layout: 2-column (Image 50% | Info 50%)
Gap: 64px
Padding: 48px
Background: #FFFBEB

Left Column (Image):
- Aspect: 1:1 or 4:3
- Max width: 600px
- Background: #FFFFFF
- Border: 1px solid #E7E5E4
- Border Radius: 8px

Right Column (Info):
Auto Layout Vertical, gap 24px

1. Breadcrumb
   - Inter Regular 14px, #78716C
   - Separator: ">" #78716C
   - Current: #1C1917

2. Product Name (H1)

3. Star Rating + Review Count

4. Price
   - Inter Bold 28px
   - Color: #78350F

5. Metadata Row
   - "Origin: Etiópia | Roast: Világos | Processing: Mosott"
   - Inter Regular 16px, #78716C

6. Flavor Tags
   - Auto Layout Horizontal Wrap, gap 8px
   - Badge: bg #78350F, text white

7. Variant Selector
   - Dropdown (Form)
   - Radio Cards (Size)
     * Card: bg #FFFFFF, border 2px #E7E5E4
     * Selected: border #D97706, bg #FFFBEB

8. Stock Indicator
   - In Stock: "Készleten: 45 db" (#16A34A)
   - Out: "Elfogyott" (#DC2626)

9. Quantity Controls
   - [-] button, input, [+] button
   - Height: 44px each

10. Add to Cart Button
    - Primary Button, full-width

11. Wishlist Button
    - Ghost Button, full-width, heart icon

## Page: Cart

Layout: Main (70%) | Sidebar (30%)
Gap: 32px
Background: #FFFBEB

Main Area (Cart Items):
Table or Card Layout:
- Background: #FFFFFF
- Border: 1px solid #E7E5E4
- Rows with hover state: bg #FFFBEB

Sidebar (Order Summary):
- Background: #FFFFFF
- Border: 1px solid #E7E5E4
- Padding: 24px
- Border Radius: 8px

Summary:
- Részösszeg: #1C1917
- Kedvezmény: #16A34A (green)
- Összesen: Inter Bold 24px, #78350F

CTA: Primary button "Tovább a pénztárhoz"

## Page: Checkout

Progress circles:
- Completed: bg #16A34A, white checkmark
- Active: bg #78350F, white number
- Upcoming: border 2px #E7E5E4, #78716C number

STEP 1 - Szállítás
- Address cards: bg #FFFFFF, border #E7E5E4
- Selected: border #D97706
- Zone badge: bg #D97706, text white

STEP 2 - Fizetés
- Stripe card element
- Summary sidebar

STEP 3 - Megerősítés
- Success checkmark: #16A34A
- Order number: #78350F, JetBrains Mono

## Page: Login

- Centered white card (max 420px) on cream background
- CraftBrew logo at top
- Title: "Bejelentkezés" — h2 Playfair Display
- Email input with label
- Password input with label + show/hide toggle
- "Emlékezz rám" checkbox
- "Bejelentkezés" button — full-width, #78350F filled
- "Elfelejtett jelszó?" link — #D97706
- Divider: "Nincs még fiókod?"
- "Regisztráció" link/button — outlined

- Same centered card style
- Title: "Regisztráció"
- Inputs: Teljes név, Email, Jelszó (min 8 chars helper text), Jelszó megerősítése
- Language preference: HU/EN radio
- Checkbox: "Elfogadom az ÁSZF-et és az Adatvédelmi szabályzatot" — with underlined links
- "Regisztráció" button — full-width
- "Van már fiókod? Bejelentkezés" link
PASSWORD RESET — REQUEST:
- Title: "Elfelejtett jelszó"
- Email input
- "Új jelszó kérése" button
- Success state: "Emailt küldtünk a megadott címre."
PASSWORD RESET — NEW PASSWORD:
- Title: "Új jelszó megadása"
- New password + Confirm password
- "Jelszó mentése" button
ERROR STATES: Red border on inputs, error text below in #DC2626. "Érvénytelen email vagy jelszó" (non-specific).
MOBILE: Card becomes full-width with padding, same vertical layout.
```
---
## 17. PROMO BANNER & SPECIAL STATES
```
Design special UI states for "CraftBrew". 1280px desktop + 375px mobile.

- Centered white card (max 420px) on cream background
- CraftBrew logo at top
- Title: "Bejelentkezés" — h2 Playfair Display
- Email input with label
- Password input with label + show/hide toggle
- "Emlékezz rám" checkbox
- "Bejelentkezés" button — full-width, #78350F filled
- "Elfelejtett jelszó?" link — #D97706
- Divider: "Nincs még fiókod?"
- "Regisztráció" link/button — outlined

- Same centered card style
- Title: "Regisztráció"
- Inputs: Teljes név, Email, Jelszó (min 8 chars helper text), Jelszó megerősítése
- Language preference: HU/EN radio
- Checkbox: "Elfogadom az ÁSZF-et és az Adatvédelmi szabályzatot" — with underlined links
- "Regisztráció" button — full-width
- "Van már fiókod? Bejelentkezés" link
PASSWORD RESET — REQUEST:
- Title: "Elfelejtett jelszó"
- Email input
- "Új jelszó kérése" button
- Success state: "Emailt küldtünk a megadott címre."
PASSWORD RESET — NEW PASSWORD:
- Title: "Új jelszó megadása"
- New password + Confirm password
- "Jelszó mentése" button
ERROR STATES: Red border on inputs, error text below in #DC2626. "Érvénytelen email vagy jelszó" (non-specific).
MOBILE: Card becomes full-width with padding, same vertical layout.
```
---
## 17. PROMO BANNER & SPECIAL STATES
```
Design special UI states for "CraftBrew". 1280px desktop + 375px mobile.

## Page: Register

- h2: "Regisztráció"
  - Layout: gap-4
  - Layout: gap-2
  - Layout: gap-2
  - Layout: gap-2

## Page: Stories

- h1: "Sztorik"

**Category Tabs**
  - Layout: gap-6

**Stories Grid**
  - Layout: grid-cols-1 grid-cols-2 grid-cols-3 gap-6

## Page: StoryDetail

- h3: "A régió története"
  - h3: "Feldolgozás és ízvilág"
  - h3: "Miért különleges?"

**Breadcrumb**
  - Layout: gap-2

**Cover Image**

**Article Header**
  - Layout: gap-4

**Share Buttons**
  - Layout: gap-3

**Article Content**

**Related Products**
  - h2: "Kapcsolódó termékek"
  - Layout: grid-cols-1 grid-cols-2 grid-cols-3 gap-6

## Page: NotFound

- h1: "Hoppá! Ez az oldal nem található"

## Page: SubscriptionWizard

- Two-column layout: Left = illustration/photo of coffee delivery, Right = text
- Title: "Friss kávé minden reggel" — h2
- Body: "Napi szállítás Budapesten, 15% kedvezménnyel. Válaszd ki a kedvenc kávédat, mi visszük."
- CTA: "Előfizetés részletei →" — outlined button

- Active status badge (green)
- Coffee: "Ethiopia Yirgacheffe — Szemes, 500g"
- Frequency: "Naponta, Reggel (6-9)"
- Next delivery: "2026-03-13 (holnap)"
- Price: "3 978 Ft/szállítás (15% kedvezmény)"
- Action buttons: "Módosítás" | "Szüneteltetés" | "Kihagyás" | "Lemondás"

- Two-column layout: Left = illustration/photo of coffee delivery, Right = text
- Title: "Friss kávé minden reggel" — h2
- Body: "Napi szállítás Budapesten, 15% kedvezménnyel. Válaszd ki a kedvenc kávédat, mi visszük."
- CTA: "Előfizetés részletei →" — outlined button

- Active status badge (green)
- Coffee: "Ethiopia Yirgacheffe — Szemes, 500g"
- Frequency: "Naponta, Reggel (6-9)"
- Next delivery: "2026-03-13 (holnap)"
- Price: "3 978 Ft/szállítás (15% kedvezmény)"
- Action buttons: "Módosítás" | "Szüneteltetés" | "Kihagyás" | "Lemondás"

## Page: UserDashboard

- h2: "Adataim"
  - Layout: gap-4
  - Layout: gap-2
  - Layout: gap-2
  - h2: "Címeim"
  - Layout: gap-2
  - h2: "Rendeléseim"
  - h2: "Előfizetéseim"
  - h3: "Ethiopia Yirgacheffe — Szemes, 500g"
  - Layout: gap-3
  - h2: "Kedvenceim"
  - h1: "Fiókom"
  - Layout: grid-cols-4 gap-8

**Sidebar**
  - Layout: gap-3

**Content**

## Page: AdminDashboard

**KPI Cards**
  - Layout: grid-cols-1 grid-cols-2 grid-cols-4 gap-6

**Revenue Chart**
  - h3: "Bevétel (7 nap)"

**Top Products & Low Stock**
  - Layout: grid-cols-2 gap-6
  - h3: "Top termékek ma"
  - h3: "Alacsony készlet ⚠️"
  - h2: "Termékek kezelése"

**Sidebar**
  - Layout: gap-3

**Main Content**

## Page: AdminProducts

- Title "Termékek", filters row (Category dropdown, Status,
Search), "+ Új termék" button #78350F
- DataTable: 40px thumbnail | Név | Kategória | Alapár | Készlet
| Státusz badge (Aktív green / Inaktív gray) | Szerkesztés |
Törlés
- Product editor with 5 tabs: Alap (Name HU/EN side-by-side,
Description HU/EN textarea tabs, Category dropdown, Base price
HUF, Image URLs, Active toggle), Kávé (Origin/Roast/Processing
dropdowns, Flavor tags input), Variánsok (SKU DataTable: Options,
Price modifier, Stock, Active, inline edit), SEO (Slug
auto-generated, Meta title/description HU/EN with 160 char
counter), Keresztértékesítés (recommended products multi-select
max 3)
- Bundle editor variant: component product list with quantities,
calculated "Külön ár" vs "Csomag ár", auto savings badge
"Megtakarítás: 20%"

## Page: AdminOrders

- Filters: Status dropdown, Date range picker, Search by order #
or customer
- DataTable: #Szám | Vásárló | Dátum | Összeg | Állapot badge |
Részletek
- Status badges: Új (blue #3B82F6), Feldolgozás (yellow #EAB308),
Csomagolva (orange #F97316), Szállítás (purple #A855F7),
Kézbesítve (green #16A34A), Lemondva (red #DC2626)
- Order detail slide-in panel: customer info, line items with
thumbnails, coupon/gift card/shipping/total breakdown, Stripe
Payment ID in JetBrains Mono, status flow buttons ("Feldolgozás"
→ "Csomagolva" → "Szállítás" → "Kézbesítve"), "Lemondás" red
danger button with confirmation, vertical status timeline with
timestamps

## Page: AdminDeliveries

- Date picker at top (defaults to today)
- Grouped by time window:
- Section "Reggel (6:00-9:00)" — 5 delivery
- Section "Délelőtt (9:00-12:00)" — 3 delivery
- Section "Délután (14:00-17:00)" — 2 delivery
- Each row: Time, Customer name, Address (short), Product+Variant, Status checkbox (✓ Kézbesítve)
- Summary bar: "Összesen: 10 szállítás | Előfizetés: 7 | Egyszeri: 3 | Budapest: 8 | +20km: 2"
- "Mind kézbesítve" bulk button
```
---
## 14. ADMIN — COUPONS, PROMO DAYS, GIFT CARDS, REVIEWS
```
Design 4 admin management pages for "CraftBrew". 1280px desktop.

- Date picker at top (defaults to today)
- Grouped by time window:
- Section "Reggel (6:00-9:00)" — 5 delivery
- Section "Délelőtt (9:00-12:00)" — 3 delivery
- Section "Délután (14:00-17:00)" — 2 delivery
- Each row: Time, Customer name, Address (short), Product+Variant, Status checkbox (✓ Kézbesítve)
- Summary bar: "Összesen: 10 szállítás | Előfizetés: 7 | Egyszeri: 3 | Budapest: 8 | +20km: 2"
- "Mind kézbesítve" bulk button
```
---
## 14. ADMIN — COUPONS, PROMO DAYS, GIFT CARDS, REVIEWS
```
Design 4 admin management pages for "CraftBrew". 1280px desktop.

- Title "Szállítás", date picker at top (defaults today)
- Sections grouped by time window: "Reggel (6:00-9:00)" — 5
items, "Délelőtt (9:00-12:00)" — 3 items, "Délután (14:00-17:00)"
— 2 items
- Each row: Time, Customer name, Address, Product+Variant, Status
checkbox ✓ Kézbesítve
- Summary bar: "Összesen: 10 | Előfizetés: 7 | Egyszeri: 3 |
Budapest: 8 | +20km: 2"
- "Mind kézbesítve" bulk action button

## Page: AdminCoupons

- Input field: "Kuponkód" placeholder
- "Beváltás" button next to it
- Applied state: Green badge "ELSO10 — 10% kedvezmény" with X to remove

- DataTable: Kód | Típus (%) | Érték | Kategória | Lejárat | Felhasználás/Max | Aktív
- Create/Edit modal: Code (uppercase), Type dropdown (% / fixed Ft), Value, Min order amount, Max uses, Category filter (multi-select or "All"), First order only checkbox, Expiry date picker, Active toggle
- Seeded examples: ELSO10 (10%, first order), NYAR2026 (15%, 500 uses, expires 2026-08-31), BUNDLE20 (20%, bundles only)

- Input field: "Kuponkód" placeholder
- "Beváltás" button next to it
- Applied state: Green badge "ELSO10 — 10% kedvezmény" with X to remove

- DataTable: Kód | Típus (%) | Érték | Kategória | Lejárat | Felhasználás/Max | Aktív
- Create/Edit modal: Code (uppercase), Type dropdown (% / fixed Ft), Value, Min order amount, Max uses, Category filter (multi-select or "All"), First order only checkbox, Expiry date picker, Active toggle
- Seeded examples: ELSO10 (10%, first order), NYAR2026 (15%, 500 uses, expires 2026-08-31), BUNDLE20 (20%, bundles only)

- DataTable: Kód | Típus (%) | Érték | Kategória | Lejárat |
Felhasználás/Max | Aktív toggle
- Create/Edit modal: Code uppercase, Type dropdown (% / fixed
Ft), Value, Min order, Max uses, Category filter multi-select,
First order only checkbox, Expiry date, Active toggle
- Show seeded data: ELSO10 (10%, first order), NYAR2026 (15%, 500
uses, 2026-08-31), BUNDLE20 (20%, bundles only)

## Page: AdminPromoDays

- DataTable: Név | Dátum | Kedvezmény | Email elküldve | Aktív
- Create/Edit: Name HU/EN, Date picker, Discount %, Banner text HU/EN (max 200 chars with counter), Active toggle
- Seeded: "Bolt születésnap" (03-15, 20%), "Kávé Világnapja" (10-01, 15%)

- Full-width bar, background #D97706 (gold)
- Text: "🎉 A CraftBrew 1 éves! 20% kedvezmény mindenből!" — white, Inter semibold
- Dismissible X button on right
- Mobile: Text wraps, smaller font, X still accessible
404 ERROR PAGE:
- Centered layout on cream background
- Large coffee cup illustration/icon (empty cup)
- Title: "Hoppá! Ez az oldal nem található" — h1
- Body: "A keresett oldal nem létezik vagy átköltözött."
- "Vissza a főoldalra" button — #78350F
500 ERROR PAGE:
- Same style
- Title: "Valami hiba történt" — h1
- Body: "Próbáld újra később, vagy lépj kapcsolatba velünk."
- "Főoldal" button + "hello@craftbrew.hu" link

- DataTable: Név | Dátum | Kedvezmény | Email elküldve | Aktív
- Create/Edit: Name HU/EN, Date picker, Discount %, Banner text HU/EN (max 200 chars with counter), Active toggle
- Seeded: "Bolt születésnap" (03-15, 20%), "Kávé Világnapja" (10-01, 15%)

- Full-width bar, background #D97706 (gold)
- Text: "🎉 A CraftBrew 1 éves! 20% kedvezmény mindenből!" — white, Inter semibold
- Dismissible X button on right
- Mobile: Text wraps, smaller font, X still accessible
404 ERROR PAGE:
- Centered layout on cream background
- Large coffee cup illustration/icon (empty cup)
- Title: "Hoppá! Ez az oldal nem található" — h1
- Body: "A keresett oldal nem létezik vagy átköltözött."
- "Vissza a főoldalra" button — #78350F
500 ERROR PAGE:
- Same style
- Title: "Valami hiba történt" — h1
- Body: "Próbáld újra később, vagy lépj kapcsolatba velünk."
- "Főoldal" button + "hello@craftbrew.hu" link

- DataTable: Név | Dátum | Kedvezmény % | Email elküldve | Aktív
- Create/Edit: Name HU/EN, Date picker, Discount %, Banner text
HU/EN (200 char counter), Active toggle
- Seeded: "Bolt születésnap" (03-15, 20%), "Kávé Világnapja"
(10-01, 15%)

## Page: AdminReviews

- DataTable: ★ stars | Termék | Felhasználó | Cím (truncated) |
Státusz (Új blue / Elfogadva green / Elutasítva red) | Dátum
- Filters: Status dropdown, Min stars, Product dropdown
- Expand card: full review (stars, title, text), user info,
product link
- Action buttons: "Elfogadás" green, "Elutasítás" red
- Reply textarea (500 char), "Válasz küldése" button
- Display: "CraftBrew válaszolt:" indented below review

## Page: AdminGiftCards

- Input field: "Ajándékkártya kód" placeholder
- "Beváltás" button
- Applied state: "GC-XXXX-XXXX — Egyenleg: 15 000 Ft, Levonva: 5 000 Ft"

- DataTable: Kód | Eredeti összeg | Egyenleg | Vásárló | Címzett | Lejárat | Státusz (Active/Expired/Depleted)
- Filters: Has balance / Depleted / Expired tabs
- Detail modal: Card info, Transaction log table (Date | Type: PURCHASE/REDEMPTION | Amount | User | Balance after)
- Format: GC-XXXX-XXXX in mono font

- Input field: "Ajándékkártya kód" placeholder
- "Beváltás" button
- Applied state: "GC-XXXX-XXXX — Egyenleg: 15 000 Ft, Levonva: 5 000 Ft"

- DataTable: Kód | Eredeti összeg | Egyenleg | Vásárló | Címzett | Lejárat | Státusz (Active/Expired/Depleted)
- Filters: Has balance / Depleted / Expired tabs
- Detail modal: Card info, Transaction log table (Date | Type: PURCHASE/REDEMPTION | Amount | User | Balance after)
- Format: GC-XXXX-XXXX in mono font

- DataTable: Kód (GC-XXXX-XXXX in JetBrains Mono) | Eredeti
összeg | Egyenleg | Vásárló | Lejárat | Státusz
(Active/Expired/Depleted)
- Tab filters: Has balance / Depleted / Expired
- Detail modal: card info + transaction log table (Date | Type
PURCHASE/REDEMPTION | Amount | User | Balance after)

## Page: AdminStories

- Story list DataTable: Cím | Kategória | Státusz (Vázlat gray /
Publikált green) | Dátum | Szerkesztés
- "+ Új sztori" button
- Editor: HU/EN tabs for content, Title HU/EN, Category dropdown,
Slug auto, Content HU/EN large textarea, Cover image URL,
Author, Related products multi-select (max 4), SEO meta HU/EN,
Status radio (Draft/Published), Publication date picker, "Mentés"
+ "Előnézet" buttons

## Page: AdminSubscriptions

- DataTable: Vásárló | Kávé | Gyakoriság | Következő szállítás |
Státusz badge (Aktív green / Szüneteltetve yellow / Lemondva red)
- Actions: Szüneteltetés, Módosítás, Lemondás on behalf of
customer

## Page: UserProfile

- Left sidebar 240px: photo placeholder, user name, menu (Adataim
active, Címeim, Rendeléseim, Előfizetéseim, Kedvenceim)
- Form: Name input, Email input (read-only with lock icon),
Language toggle HU/EN
- "Mentés" button
- Password change section: Old password, New password, Confirm,
"Módosítás" button
- Mobile: sidebar becomes horizontal scrollable tabs

## Page: UserAddresses

- Address cards: Label "Otthom", Name, Full address, Phone, Zone
badge ("Budapest" #D97706), Default star icon
- Actions: "Szerkesztés" | "Törlés" | "Alapértelmezett"
- "+ Új cím" button at top
- Add/Edit form: Label, Name, Postal code (auto zone detect
badge), City, Street, Phone

## Design Reference

Use exact values from `docs/design-system.md` — do NOT use framework defaults.

**Key colors**: primary `#78350F`, secondary `#D97706`, background `#FFFBEB`
**Fonts**: Playfair Display, Inter, JetBrains Mono

**Matched pages:**
- **Homepage**: see design-system.md § Page Layouts
- **Catalog**: see design-system.md § Page Layouts
- **Product Detail**: see design-system.md § Page Layouts
- **Cart**: Uses: Button, figma
- **Checkout**: Uses: Button
- **Admin**: see design-system.md § Page Layouts
- **Auth**: see design-system.md § Page Layouts
- **Subscription**: see design-system.md § Page Layouts
- **Stories**: Uses: figma
- **Profile**: see design-system.md § Page Layouts
- **Search**: see design-system.md § Page Layouts

