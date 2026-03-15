
## 1. DESIGN TOKENS & COMPONENT LIBRARY

```
Create a design token and component library page for "CraftBrew" — a premium specialty coffee e-commerce webshop.

BRAND: Warm, artisanal, premium but approachable. The joy and community of coffee.

COLOR PALETTE:
- Primary: #78350F (dark coffee brown) — buttons, active nav, CTAs
- Secondary: #D97706 (gold accent) — hover states, links, accents
- Background: #FFFBEB (warm cream) — page background
- Surface: #FFFFFF — cards, panels
- Text: #1C1917 — main text
- Muted: #78716C — secondary text, placeholders
- Border: #E7E5E4 — borders, dividers
- Success: #16A34A — in-stock badges, success states
- Warning: #D97706 — low stock badges
- Error: #DC2626 — out of stock, error states

TYPOGRAPHY:
- Headings (h1-h3): Playfair Display (serif) — h1: 40px bold, h2: 32px semibold, h3: 24px semibold
- Body text: Inter (sans-serif) — body: 16px, small: 14px, caption: 12px
- Monospace (order numbers, codes): JetBrains Mono

COMPONENTS TO DESIGN:
- Buttons: Primary (filled #78350F, white text), Secondary (outlined), Ghost, Disabled. Border-radius: 6px. Min touch target: 44x44px
- Product Card: Image (4:3 aspect), Name, Price ("from 2 490 Ft"), Star rating + count, "New" badge (green), "Out of Stock" badge (red), Heart icon (wishlist). Card padding: 24px, border-radius: 8px
- Badge variants: New, Out of Stock, Low Stock, Discount %, Category
- Input fields: Label above, border #E7E5E4, focus ring #D97706, min 16px font
- Star rating: 5 stars, clickable (1-5), filled gold #D97706
- Toast notifications: success/error/info variants
- Navigation items: Normal, Hover (#D97706), Active (#78350F underline)
- Price display: "2 490 Ft" format (HUF, space separator, Ft suffix)

SPACING: 8px base grid. Card padding 24px. Grid gap 24px desktop, 16px mobile. Container max-width: 1280px.
```

---

## 2. HOMEPAGE — DESKTOP (1280px)

```
Design the homepage for "CraftBrew" specialty coffee webshop at 1280px desktop width. Warm cream background (#FFFBEB), coffee brown primary (#78350F), gold accents (#D97706). Headings in Playfair Display serif, body in Inter sans-serif.

HEADER (sticky):
- Left: CraftBrew logo (text logo, Playfair Display, #78350F)
- Center nav: "Kávék" | "Eszközök" | "Sztorik" | "Előfizetés" — Inter 16px, hover #D97706
- Right: Search icon, Cart icon with badge (item count), "EN" language toggle, User avatar/login

HERO BANNER (full-width, ~500px tall):
- Large atmospheric coffee photo as background (beans/cup/barista)
- Overlay text left-aligned: "Specialty kávé, az asztalodra szállítva." — Playfair Display h1, white
- Subtitle: "Kézzel válogatott, frissen pörkölt kávékülönlegességek Budapestről" — Inter, white
- CTA button: "Fedezd fel kávéinkat →" — filled #78350F, white text, rounded 6px

FEATURED COFFEES SECTION:
- Section title: "Kedvenceink" — Playfair Display h2, centered
- 4 product cards in a row, equal width
- Each card: Coffee image placeholder (4:3), Name (e.g. "Ethiopia Yirgacheffe"), Price "2 490 Ft-tól", Star rating "★★★★★ (12)", Heart icon top-right
- Below grid: "Összes kávé →" link, #D97706

SUBSCRIPTION CTA SECTION:
- Two-column layout: Left = illustration/photo of coffee delivery, Right = text
- Title: "Friss kávé minden reggel" — h2
- Body: "Napi szállítás Budapesten, 15% kedvezménnyel. Válaszd ki a kedvenc kávédat, mi visszük."
- CTA: "Előfizetés részletei →" — outlined button

STORY HIGHLIGHTS:
- Section title: "Sztorik" — h2, centered
- 3 story cards: Cover image (16:9), Category badge, Title, Date
- "Összes sztori →" link

TESTIMONIALS:
- Section title: "Mit mondanak vásárlóink" — h2, centered
- 3 review cards: Stars, Quote text in italics, Customer name, Product name
- White cards on cream background, subtle shadow

FOOTER:
- 3-column on cream background with darker tone
- Col 1: CraftBrew logo, "Specialty Coffee Budapest", © 2026
- Col 2: Links — Kávék, Eszközök, Sztorik, Előfizetés
- Col 3: hello@craftbrew.hu, Address: "CraftBrew Labor, Kazinczy u. 28, 1075 Budapest", Social icons (FB, IG)
```

---

## 3. HOMEPAGE — MOBILE (375px)

```
Design the CraftBrew homepage for mobile at 375px width. Same brand: cream #FFFBEB background, brown #78350F primary, gold #D97706 accent.

MOBILE HEADER:
- Height ~56px
- Left: Hamburger icon (☰), Center: "CraftBrew" text logo, Right: Search icon + Cart icon with count badge
- All touch targets minimum 44x44px

HAMBURGER DRAWER (separate frame):
- Slides in from left, overlay on right (semi-transparent #1C1917/50%)
- Top: X close button
- Menu items stacked vertically, 48px row height: Kávék, Eszközök, Sztorik, Előfizetés
- Divider line
- Cart (3), Fiókom, Language toggle "EN"

HERO: Full-width image, text overlay, CTA button full-width below image

FEATURED COFFEES: Title, then 1-column stack of product cards (image top, info below). 4 cards.

SUBSCRIPTION CTA: Stacked layout — image on top, text and CTA button below, full-width

STORIES: 1-column, 3 story cards stacked

TESTIMONIALS: 1-column, 3 review cards stacked, horizontally swipeable optional

FOOTER: Single column, stacked sections

CRITICAL: No horizontal overflow anywhere. All text readable. Minimum 16px for input fonts. 44px minimum touch targets.
```

---

## 4. PRODUCT CATALOG PAGE — COFFEES

```
Design a coffee catalog page for "CraftBrew" webshop. 1280px desktop + 375px mobile.

Colors: cream #FFFBEB bg, brown #78350F primary, gold #D97706 accent. Headings Playfair Display, body Inter.

PAGE TITLE: "Kávék" — h1 Playfair Display

FILTER SIDEBAR (desktop, left, 280px wide):
- "Szűrők" title with "Szűrők törlése" link
- Origin filter: Checkboxes — Etiópia, Kolumbia, Brazília, Guatemala, Kenya, Indonézia, Costa Rica, Ruanda
- Roast level: Checkboxes — Világos, Közepes, Sötét
- Processing: Checkboxes — Mosott, Természetes, Mézes, Wet-hulled
- Price range: Dual-handle slider, 1 990 Ft — 9 380 Ft, with min/max inputs
- Each filter section collapsible with chevron

PRODUCT GRID (desktop, right, 3 columns):
- 8 coffee product cards
- Card: Image (coffee bag photo placeholder), Name, Origin tag ("Etiópia"), Roast tag ("Világos"), Price "2 490 Ft-tól", Stars "★★★★★ (12)", Heart icon
- Hover: subtle shadow lift, gold border

MOBILE VERSION (375px):
- Filters: Collapsed into "Szűrők" button at top, opens as bottom sheet (full screen)
- Products: 1-column full-width cards
- Sticky filter button at top when scrolling

SORTING: Dropdown top-right — "Rendezés: Népszerű | Ár ↑ | Ár ↓ | Legújabb"
```

---

## 5. PRODUCT DETAIL PAGE — COFFEE

```
Design a coffee product detail page for "CraftBrew". Product: "Ethiopia Yirgacheffe". 1280px desktop + 375px mobile.

Colors: cream #FFFBEB, brown #78350F, gold #D97706. Typography: Playfair Display headings, Inter body.

BREADCRUMB: Főoldal > Kávék > Ethiopia Yirgacheffe

DESKTOP LAYOUT (2-column):
LEFT (50%): Large product image, aspect 1:1 or 4:3
RIGHT (50%):
- Product name: "Ethiopia Yirgacheffe" — h1 Playfair Display
- Stars: ★★★★★ (12 értékelés)
- Price: "2 490 Ft" — large, bold, #78350F. Changes based on variant selection.
- Origin: Etiópia | Roast: Világos | Processing: Mosott
- Flavor tags: "Virágos", "Citrusos", "Jázmin", "Bergamott" — small badges, #D97706 bg with white text
- VARIANT SELECTOR:
  - Form: Dropdown — "Szemes" / "Őrölt (filter)" / "Őrölt (eszpresszó)" / "Drip bag"
  - Size: Radio buttons — ○ 250g (2 490 Ft) ● 500g (4 680 Ft) ○ 1kg (6 580 Ft)
  - Stock indicator: "Készleten: 45 db" in green or "Elfogyott" in red (disabled)
- Quantity: [-] 1 [+] controls
- Add to Cart button: Full-width, #78350F filled, white text, "Kosárba"
- Heart icon: "Kedvencekhez" — outlined

DESCRIPTION: Full product description paragraph

RECOMMENDED WITH THIS (below, 3-column):
- Title: "Ajánljuk mellé"
- 3 small product cards (e.g., V60 Dripper, V60 Filters, Timemore Scale)

REVIEWS SECTION:
- Title: "Értékelések" with average "4.8 ★★★★★ (12 értékelés)"
- "Értékelés írása" button (if eligible)
- Review list: Stars, Title, Text, Author name, Date
- Admin reply: indented, "CraftBrew válaszolt:" prefix

MOBILE (375px):
- Image full-width on top
- Info stacked below
- Sticky bottom bar: Price on left, "Kosárba" button on right, always visible
```

---

## 6. CART PAGE

```
Design the shopping cart page for "CraftBrew". 1280px desktop + 375px mobile.

Colors: cream #FFFBEB, brown #78350F, gold #D97706.

PAGE TITLE: "Kosár" — h1

CART ITEMS (desktop — table layout):
| Image | Product + Variant | Unit Price | Quantity | Line Total | Remove |
Each row: 60px thumbnail, "Ethiopia Yirgacheffe — Szemes, 500g", "4 680 Ft", [-] 2 [+] buttons (44px touch), "9 360 Ft", Trash icon

Show 3-4 sample items with different products.

COUPON INPUT (below items):
- Input field: "Kuponkód" placeholder
- "Beváltás" button next to it
- Applied state: Green badge "ELSO10 — 10% kedvezmény" with X to remove

GIFT CARD INPUT:
- Input field: "Ajándékkártya kód" placeholder
- "Beváltás" button
- Applied state: "GC-XXXX-XXXX — Egyenleg: 15 000 Ft, Levonva: 5 000 Ft"

ORDER SUMMARY (desktop — right sidebar 320px):
- Részösszeg: 18 040 Ft
- Kedvezmény (ELSO10): -1 804 Ft (red text)
- Ajándékkártya: -5 000 Ft
- Szállítás: Pénztárnál számítjuk
- Összesen: 11 236 Ft — large, bold
- "Tovább a pénztárhoz" button — full-width, #78350F filled

EMPTY CART STATE:
- Centered: shopping bag icon, "A kosarad üres", "Fedezd fel kávéinkat →" link

MOBILE (375px):
- Items in vertical cards (image left small, info right)
- Quantity buttons prominent, 44px
- Summary fixed at bottom with total and CTA button
```

---

## 7. CHECKOUT — 3-STEP FLOW

```
Design a 3-step checkout flow for "CraftBrew". 1280px desktop + 375px mobile.

Colors: cream #FFFBEB, brown #78350F, gold #D97706.

STEP INDICATOR (top):
- 3 circles connected by lines: ① Szállítás — ② Fizetés — ③ Megerősítés
- Active step: filled #78350F, Completed: filled with checkmark, Upcoming: outlined #E7E5E4

STEP 1 — SZÁLLÍTÁS:
Left (60%):
- Saved addresses: Radio cards — "Otthon: Kiss János, 1052 Budapest, Váci u. 10" with zone badge "Budapest (990 Ft)"
- "Új cím hozzáadása" expandable form: Name, Postal code (auto zone: "Budapest" badge appears), City, Street, Phone
- Shipping method: Radio — "Házhozszállítás (990 Ft)" / "Személyes átvétel (ingyenes) — CraftBrew Labor, Kazinczy u. 28"
- Free shipping note: "Ingyenes szállítás 15 000 Ft felett (Budapest)"
- Estimated delivery: "Holnap (Budapest)"
- "Tovább" button

Right (40%): Order summary card — items, subtotal, discount, shipping fee, total

STEP 2 — FIZETÉS:
- Stripe card element placeholder (card number, expiry, CVC)
- Order summary visible
- "Fizetek — 12 226 Ft" button

STEP 3 — MEGERŐSÍTÉS (success page):
- Green checkmark icon, large
- "Köszönjük a rendelésed!"
- Order number: "#1042" in JetBrains Mono
- Date, Shipping address, Expected delivery
- Line items summary
- Totals breakdown
- "Számla letöltése (PDF)" button — outlined
- "Rendeléseim" link

MOBILE: All steps vertically stacked, full-width inputs, "Fizetek" button sticky at bottom on step 2.
```

---

## 8. SUBSCRIPTION SETUP WIZARD

```
Design a subscription setup wizard for "CraftBrew" coffee delivery. 1280px desktop + 375px mobile.

Colors: cream #FFFBEB, brown #78350F, gold #D97706.

5-STEP WIZARD with progress bar at top.

STEP 1 — KÁVÉ KIVÁLASZTÁSA:
- Title: "Válaszd ki a kávédat"
- 8 coffee cards in 4x2 grid (desktop), 1 column (mobile)
- Selected card: gold border #D97706, checkmark overlay
- Card: Image, Name, "2 490 Ft-tól", Origin tag

STEP 2 — FORMA ÉS MÉRET:
- Form: Dropdown — Szemes / Őrölt (filter, eszpresszó, french press, török)
- Size: Large radio cards — 250g / 500g / 1kg, showing price for each

STEP 3 — GYAKORISÁG:
- 4 large option cards:
  - Naponta: -15% kedvezmény (banner: "Legjobb ár!")
  - Hetente (hétfő): -10%
  - Kéthetente: -7%
  - Havonta: -5%
- Each shows: calculated price, savings amount

STEP 4 — KISZÁLLÍTÁS:
- Time window: 3 radio cards with clock icons — Reggel (6-9), Délelőtt (9-12), Délután (14-17)
- Address selection (same as checkout)
- Start date picker (calendar, earliest: tomorrow)

STEP 5 — ÖSSZEGZÉS:
- Selected coffee + variant image
- Frequency, time window, address, start date
- Price breakdown: Base price, Discount %, Discounted price, Shipping
- "Előfizetés indítása" CTA button — #78350F filled, large

MOBILE: Steps vertically, wizard card full-width, navigation: "Vissza" + "Tovább" buttons at bottom
```

---

## 9. USER DASHBOARD — SUBSCRIPTIONS & CALENDAR

```
Design the user subscription dashboard for "CraftBrew". 1280px desktop + 375px mobile.

Colors: cream #FFFBEB, brown #78350F, gold #D97706.

LEFT SIDEBAR (desktop, 240px):
- Profile photo placeholder, User name
- Menu: Adataim, Címeim, Rendeléseim, Előfizetéseim (active, gold left border), Kedvenceim

SUBSCRIPTION CARD:
- Active status badge (green)
- Coffee: "Ethiopia Yirgacheffe — Szemes, 500g"
- Frequency: "Naponta, Reggel (6-9)"
- Next delivery: "2026-03-13 (holnap)"
- Price: "3 978 Ft/szállítás (15% kedvezmény)"
- Action buttons: "Módosítás" | "Szüneteltetés" | "Kihagyás" | "Lemondás"

CALENDAR VIEW (below, monthly):
- Month navigation: ← Március 2026 →
- 7-column calendar grid (H K Sz Cs P Sz V)
- Day cells:
  - ☕ = scheduled delivery (brown #78350F badge)
  - ⏸ = skipped (grey, strikethrough)
  - ❌ = paused range (light red background)
  - Today: gold border
- Click on a delivery day: popover with "Kihagyás" option

MOBILE: Sidebar becomes top tabs/dropdown. Calendar scrollable or swipeable. Cards full-width stacked.
```

---

## 10. USER DASHBOARD — ORDERS & PROFILE

```
Design user account pages for "CraftBrew": Profile, Addresses, Orders. 1280px desktop + 375px mobile.

Colors: cream #FFFBEB, brown #78350F, gold #D97706.

PROFILE PAGE (Adataim):
- Form: Name input, Email input (read-only with lock icon), Language toggle HU/EN
- "Mentés" button
- Separate section: "Jelszó módosítása" — Old password, New password, Confirm, "Módosítás" button

ADDRESSES PAGE (Címeim):
- Address cards: Label ("Otthon"), Name, Full address, Phone, Zone badge ("Budapest"), Default star
- Actions: "Szerkesztés" | "Törlés" | "Alapértelmezett"
- "+ Új cím" button at top
- Add/Edit form: Label, Name, Postal code (zone auto-detect), City, Street, Phone

ORDERS PAGE (Rendeléseim):
- DataTable: #Szám | Dátum | Állapot | Összeg | [Részletek]
- Status badges: Új (blue), Feldolgozás (yellow), Csomagolva (orange), Szállítás (purple), Kézbesítve (green), Lemondva (red)
- Order detail (click/expand):
  - Line items with thumbnails
  - Shipping address
  - Discounts, gift card, shipping fee, total
  - Status timeline: vertical dots with timestamps
  - "Számla letöltése" button
  - "Visszaküldés kérése" button (within 14 days)

FAVORITES PAGE (Kedvenceim):
- Product grid (3 col desktop, 1 col mobile)
- Each with "Eltávolítás" button
- Empty state: Heart icon, "Még nincsenek kedvenceid"

MOBILE: Sidebar → top horizontal scrollable tabs. Tables → card layout. Forms full-width.
```

---

## 11. ADMIN DASHBOARD

```
Design an admin dashboard for "CraftBrew" webshop. 1280px desktop + 375px mobile. Admin uses Hungarian language only.

Colors: cream #FFFBEB, brown #78350F, gold #D97706. Keep warm but professional.

LEFT SIDEBAR (240px, white bg):
- CraftBrew Admin logo
- Menu items with icons: Áttekintés (active), Termékek, Rendelések, Szállítás, Előfizetések, Kuponok, Ajándékkártyák, Értékelések, Promó napok, Tartalom

KPI CARDS (top, 4 in a row):
- Mai bevétel: "234 500 Ft" with "+12%" green arrow
- Mai rendelések: "8" with "+3" green
- Aktív előfizetők: "23" with "+2" green
- Új regisztrációk (7 nap): "15" with "-5%" red arrow
- Each card: White surface, subtle shadow, icon left, big number, small % change

REVENUE CHART (below KPIs, full width):
- 7-day line/bar chart, x-axis: dates, y-axis: HUF
- Title: "Bevétel (7 nap)"
- Gold #D97706 line or bars on cream background

TOP PRODUCTS TODAY (left 50%):
- Simple list: #1 Ethiopia Yirgacheffe (12 db), #2 Starter Bundle (5 db), #3 Colombia Huila (4 db)

LOW STOCK ALERTS (right 50%):
- Warning cards (amber border): "Fellow Stagg EKG Kettle — 8 db" ⚠️, "Rwanda Nyungwe 1kg — 5 db" ⚠️

MOBILE: Sidebar → hamburger drawer. KPIs 2x2 grid. Chart full-width scrollable. Lists stacked.
```

---

## 12. ADMIN — PRODUCT MANAGEMENT

```
Design admin product management pages for "CraftBrew". 1280px desktop.

PRODUCT LIST PAGE:
- Title: "Termékek"
- Filters row: Category dropdown (Kávé/Eszköz/Merch/Csomag), Status (Aktív/Inaktív), Search input
- "+ Új termék" button top-right, #78350F
- DataTable columns: [Image 40px] | Név | Kategória | Alapár | Készlet (összesített) | Státusz (Active/Inactive badge) | [Szerkesztés] [Törlés]
- Pagination: "1-10 / 24 termék" with page controls

PRODUCT EDIT PAGE (tabbed):
Tab 1 — Alap:
- Name HU / Name EN inputs (side by side)
- Description HU / Description EN (textareas, side by side with HU/EN tab toggle)
- Category dropdown
- Base price input (HUF)
- Image URLs list (add/remove)
- Active toggle switch

Tab 2 — Kávé specifikus (only for coffee):
- Origin, Roast level, Processing method dropdowns
- Flavor notes tag input
- Altitude, Farm name inputs

Tab 3 — Variánsok:
- DataTable: SKU | Options (e.g. "Szemes, 500g") | Price modifier (+Ft) | Stock | Active
- "+ Új variáns" button
- Inline edit or modal for each variant
- Stock change log (timestamp, old → new, reason)

Tab 4 — SEO:
- Slug input (auto-generated, editable)
- Meta title HU/EN
- Meta description HU/EN (with character counter, max 160)

Tab 5 — Keresztértékesítés:
- "Ajánlott termékek" multi-select (max 3), with product search

BUNDLE EDIT (special):
- Components list: Product + Variant + Quantity rows, removable
- Calculated "Külön ár": sum of components
- "Csomag ár" input
- Auto-calculated "Megtakarítás: 20%" badge
```

---

## 13. ADMIN — ORDERS & DAILY DELIVERIES

```
Design admin order management for "CraftBrew". 1280px desktop.

ORDERS LIST:
- Filters: Status dropdown, Date range picker, Search (order #, customer name)
- DataTable: #Szám | Vásárló | Dátum | Összeg | Állapot | [Részletek]
- Status badges with colors: Új (blue), Feldolgozás (yellow), Csomagolva (orange), Szállítás (purple), Kézbesítve (green), Lemondva (red)

ORDER DETAIL (slide-in panel or page):
- Customer info
- Line items: Image, Name+Variant, Qty, Unit price, Line total
- Coupon: "ELSO10 — 10%" or none
- Gift card deduction
- Shipping fee + zone
- Grand total (bold, large)
- Stripe Payment ID (mono font)
- "Számla letöltése" button
- Status flow buttons: "Feldolgozás" → "Csomagolva" → "Szállítás" → "Kézbesítve"
- "Lemondás" button (danger red, with confirmation)
- Status timeline: vertical line with dots, timestamps

DAILY DELIVERIES PAGE (Szállítás):
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

COUPONS (Kuponok):
- DataTable: Kód | Típus (%) | Érték | Kategória | Lejárat | Felhasználás/Max | Aktív
- Create/Edit modal: Code (uppercase), Type dropdown (% / fixed Ft), Value, Min order amount, Max uses, Category filter (multi-select or "All"), First order only checkbox, Expiry date picker, Active toggle
- Seeded examples: ELSO10 (10%, first order), NYAR2026 (15%, 500 uses, expires 2026-08-31), BUNDLE20 (20%, bundles only)

PROMO DAYS (Promó napok):
- DataTable: Név | Dátum | Kedvezmény | Email elküldve | Aktív
- Create/Edit: Name HU/EN, Date picker, Discount %, Banner text HU/EN (max 200 chars with counter), Active toggle
- Seeded: "Bolt születésnap" (03-15, 20%), "Kávé Világnapja" (10-01, 15%)

GIFT CARDS (Ajándékkártyák):
- DataTable: Kód | Eredeti összeg | Egyenleg | Vásárló | Címzett | Lejárat | Státusz (Active/Expired/Depleted)
- Filters: Has balance / Depleted / Expired tabs
- Detail modal: Card info, Transaction log table (Date | Type: PURCHASE/REDEMPTION | Amount | User | Balance after)
- Format: GC-XXXX-XXXX in mono font

REVIEWS (Értékelések):
- DataTable: ★ | Termék | Felhasználó | Cím (truncated) | Státusz (Új/Elfogadva/Elutasítva) | Dátum
- Filters: Status dropdown, Min stars, Product dropdown
- Moderation card (click to expand): Full review (stars, title, text), User info, Product link
- Action buttons: "Elfogadás" (green), "Elutasítás" (red)
- Reply section: textarea (max 500), "Válasz küldése" button
- Display format: "CraftBrew válaszolt:" — indented below review
```

---

## 15. CONTENT/STORIES MANAGEMENT + STORY PAGES

```
Design blog/stories pages for "CraftBrew". Both public-facing AND admin management. 1280px desktop + 375px mobile.

PUBLIC — STORY LIST (/hu/sztorik):
- Title: "Sztorik" — h1 Playfair Display
- Category tabs: [Mind] [Eredet] [Pörkölés] [Főzés] [Egészség] [Ajándék]
- Active tab: underline #D97706
- Story cards in 3-column grid (desktop), 1-column (mobile):
  - Cover image (16:9), Category badge (small, colored), Title (h3 Playfair Display), Date, Short excerpt
  - Hover: subtle shadow, image slight zoom

PUBLIC — STORY DETAIL:
- Breadcrumb: Főoldal > Sztorik > Eredet > "Yirgacheffe: A kávé szülőföldje"
- Cover image full-width (max 600px height)
- Category badge + Date + Author ("CraftBrew csapat")
- Title: h1 Playfair Display
- Article body: well-formatted paragraphs, Inter 16px, line-height 1.8
- "Kapcsolódó termékek" section at bottom: 3-4 product cards
- Share buttons: Facebook, Twitter/X, Copy link — icon buttons in a row
- Mobile: All stacked, full-width

ADMIN — STORIES LIST (Tartalom):
- DataTable: Cím | Kategória | Státusz (Vázlat/Publikált) | Dátum | [Szerkesztés]
- "+ Új sztori" button

ADMIN — STORY EDITOR:
- HU/EN tabs for content editing
- Title HU/EN, Category dropdown, Slug (auto, editable)
- Content HU/EN: Large textarea (markdown support hint)
- Cover image URL
- Author
- Related products: Multi-select searchable (max 4)
- SEO: Meta title HU/EN, Meta description HU/EN
- Status: Draft / Published radio
- Publication date: Date picker
- "Mentés" and "Előnézet" buttons
```

---

## 16. AUTH PAGES — LOGIN, REGISTER, PASSWORD RESET

```
Design authentication pages for "CraftBrew". 1280px desktop + 375px mobile.

Colors: cream #FFFBEB, brown #78350F, gold #D97706. Centered card layout.

LOGIN (/hu/belepes):
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

REGISTER (/hu/regisztracio):
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

PROMO DAY BANNER (top of homepage, above header):
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

EMPTY STATES:
- Cart empty: Shopping bag icon, "A kosarad üres"
- No search results: Magnifying glass icon, "Nincs találat erre: 'xyz'"
- No reviews: Star icon, "Még nincs értékelés"
- No favorites: Heart icon, "Még nincsenek kedvenceid"

OUT OF STOCK PRODUCT:
- Product image with faded overlay
- "Elfogyott" red badge on card
- Detail page: "Add to cart" replaced with "Értesíts, ha újra elérhető" button (outlined)

LOADING STATES:
- Skeleton screens for product cards (grey shimmer rectangles for image, title, price)
- Spinner for checkout processing

TOAST NOTIFICATIONS:
- Success (green left border): "Termék hozzáadva a kosárhoz"
- Error (red left border): "Hiba történt, próbáld újra"
- Info (blue left border): "Kupon sikeresen aktiválva"
- Position: top-right, auto-dismiss 5s
```

---

## 18. EMAIL TEMPLATES

```
Design 4 email templates for "CraftBrew". Width: 600px (email standard). Mobile-responsive.

Brand: cream #FFFBEB, brown #78350F, gold #D97706. Inter font (web-safe fallback: Arial).

ALL EMAILS share:
- Header: CraftBrew logo centered, thin gold line below
- Footer: "CraftBrew — Specialty Coffee Budapest", Kazinczy u. 28, Unsubscribe link, Social icons
- Max width 600px, centered

EMAIL 1 — WELCOME:
- Subject line preview: "Üdvözlünk a CraftBrew-nál! ☕"
- Hero: Warm coffee image banner
- "Kedves [Név]!" greeting
- Welcome text (2-3 lines about CraftBrew)
- CTA button: "Fedezd fel kávéinkat" — #78350F filled
- Secondary: "Vagy próbáld ki az előfizetést!" text link

EMAIL 2 — ORDER CONFIRMATION:
- Subject: "Rendelés visszaigazolás — #1042"
- Order # in large mono font
- Line items table: Product, Variant, Qty, Price
- Subtotal, Discount, Gift card, Shipping, TOTAL (bold)
- Shipping address block
- Expected delivery: "Holnap (Budapest)"
- CTA: "Rendelésem megtekintése"

EMAIL 3 — SHIPPING NOTIFICATION:
- Subject: "Úton van a rendelésed! 🚚"
- Truck icon/illustration
- "Rendelésed (#1042) úton van!"
- Shipping address, Expected delivery
- CTA: "Rendelés követése"

EMAIL 4 — GIFT CARD:
- Subject: "Ajándékkártyát kaptál! 🎁"
- Gift box illustration
- "[Küldő neve] ajándékkártyát küldött neked!"
- Personal message in quote block (if provided)
- Gift card code: "GC-XXXX-XXXX" — large, mono, prominent box
- Amount: "10 000 Ft"
- CTA: "Beváltás a webshopban"
- "Érvényes: 1 évig" note
```
