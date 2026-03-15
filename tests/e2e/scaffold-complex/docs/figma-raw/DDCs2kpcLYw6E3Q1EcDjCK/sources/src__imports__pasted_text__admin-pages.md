  Add the following missing pages to the existing CraftBrew
  project. Keep the same LIGHT MODE color scheme: cream #FFFBEB
  background, brown #78350F primary, gold #D97706 accent, white
  #FFFFFF cards, #E7E5E4 borders.

  ADMIN PAGES (Hungarian language, desktop 1280px only):

  ADMIN PRODUCTS PAGE:
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

  ADMIN ORDERS PAGE:
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

  ADMIN DAILY DELIVERIES PAGE:
  - Title "Szállítás", date picker at top (defaults today)
  - Sections grouped by time window: "Reggel (6:00-9:00)" — 5
  items, "Délelőtt (9:00-12:00)" — 3 items, "Délután (14:00-17:00)"
   — 2 items
  - Each row: Time, Customer name, Address, Product+Variant, Status
   checkbox ✓ Kézbesítve
  - Summary bar: "Összesen: 10 | Előfizetés: 7 | Egyszeri: 3 |
  Budapest: 8 | +20km: 2"
  - "Mind kézbesítve" bulk action button

  ADMIN COUPONS PAGE:
  - DataTable: Kód | Típus (%) | Érték | Kategória | Lejárat |
  Felhasználás/Max | Aktív toggle
  - Create/Edit modal: Code uppercase, Type dropdown (% / fixed
  Ft), Value, Min order, Max uses, Category filter multi-select,
  First order only checkbox, Expiry date, Active toggle
  - Show seeded data: ELSO10 (10%, first order), NYAR2026 (15%, 500
   uses, 2026-08-31), BUNDLE20 (20%, bundles only)

  ADMIN PROMO DAYS PAGE:
  - DataTable: Név | Dátum | Kedvezmény % | Email elküldve | Aktív
  - Create/Edit: Name HU/EN, Date picker, Discount %, Banner text
  HU/EN (200 char counter), Active toggle
  - Seeded: "Bolt születésnap" (03-15, 20%), "Kávé Világnapja"
  (10-01, 15%)

  ADMIN GIFT CARDS PAGE:
  - DataTable: Kód (GC-XXXX-XXXX in JetBrains Mono) | Eredeti
  összeg | Egyenleg | Vásárló | Lejárat | Státusz
  (Active/Expired/Depleted)
  - Tab filters: Has balance / Depleted / Expired
  - Detail modal: card info + transaction log table (Date | Type
  PURCHASE/REDEMPTION | Amount | User | Balance after)

  ADMIN REVIEWS PAGE:
  - DataTable: ★ stars | Termék | Felhasználó | Cím (truncated) |
  Státusz (Új blue / Elfogadva green / Elutasítva red) | Dátum
  - Filters: Status dropdown, Min stars, Product dropdown
  - Expand card: full review (stars, title, text), user info,
  product link
  - Action buttons: "Elfogadás" green, "Elutasítás" red
  - Reply textarea (500 char), "Válasz küldése" button
  - Display: "CraftBrew válaszolt:" indented below review

  ADMIN STORIES EDITOR:
  - Story list DataTable: Cím | Kategória | Státusz (Vázlat gray /
  Publikált green) | Dátum | Szerkesztés
  - "+ Új sztori" button
  - Editor: HU/EN tabs for content, Title HU/EN, Category dropdown,
   Slug auto, Content HU/EN large textarea, Cover image URL,
  Author, Related products multi-select (max 4), SEO meta HU/EN,
  Status radio (Draft/Published), Publication date picker, "Mentés"
   + "Előnézet" buttons

  ADMIN SUBSCRIPTIONS PAGE:
  - DataTable: Vásárló | Kávé | Gyakoriság | Következő szállítás |
  Státusz badge (Aktív green / Szüneteltetve yellow / Lemondva red)
  - Actions: Szüneteltetés, Módosítás, Lemondás on behalf of
  customer

  USER ACCOUNT PAGES (desktop + mobile):

  USER PROFILE (Adataim):
  - Left sidebar 240px: photo placeholder, user name, menu (Adataim
   active, Címeim, Rendeléseim, Előfizetéseim, Kedvenceim)
  - Form: Name input, Email input (read-only with lock icon),
  Language toggle HU/EN
  - "Mentés" button
  - Password change section: Old password, New password, Confirm,
  "Módosítás" button
  - Mobile: sidebar becomes horizontal scrollable tabs

  USER ADDRESSES (Címeim):
  - Address cards: Label "Otthom", Name, Full address, Phone, Zone
  badge ("Budapest" #D97706), Default star icon
  - Actions: "Szerkesztés" | "Törlés" | "Alapértelmezett"
  - "+ Új cím" button at top
  - Add/Edit form: Label, Name, Postal code (auto zone detect
  badge), City, Street, Phone

  USER ORDERS (Rendeléseim):
  - DataTable: #Szám mono | Dátum | Állapot badge | Összeg |
  Részletek
  - Same status badge colors as admin
  - Order detail expandable: line items with thumbnails, shipping
  address, discount/gift card/shipping/total, vertical status
  timeline with timestamps, "Számla letöltése" button,
  "Visszaküldés kérése" button (within 14 days badge)
  - Mobile: cards instead of table

  USER FAVORITES (Kedvenceim):
  - Product grid 3-column desktop, 1-column mobile
  - Each card with "Eltávolítás" button
  - Empty state: heart icon, "Még nincsenek kedvenceid"

  USER SUBSCRIPTIONS with CALENDAR:
  - Subscription card: Active green badge, "Ethiopia Yirgacheffe —
  Szemes, 500g", "Naponta, Reggel (6-9)", next delivery "2026-03-13
   (holnap)", price "3 978 Ft/szállítás (15% kedvezmény)"
  - Action buttons: "Módosítás" | "Szüneteltetés" | "Kihagyás" |
  "Lemondás"
  - Monthly calendar: ← Március 2026 →, 7-column (H K Sz Cs P Sz
  V), day cells with ☕ brown badge (delivery), ⏸ grey (skipped),
  ❌ light red bg (paused), today gold border
  - Click delivery day: popover with "Kihagyás" option

  OTHER MISSING PAGES:

  PASSWORD RESET:
  - Request page: centered white card like login, "Elfelejtett
  jelszó" h2, email input, "Új jelszó kérése" button, success state
   "Emailt küldtünk a megadott címre."
  - New password page: "Új jelszó megadása" h2, New password +
  Confirm inputs, "Jelszó mentése" button

  EQUIPMENT CATALOG (/eszkozok):
  - Same layout as coffee catalog but without
  Origin/Roast/Processing filters
  - 3-column grid, 7 equipment product cards
  - No flavor tags on cards

  MERCH CATALOG (/merch):
  - Same grid layout, 5 merch items
  - T-shirt shows size variants (S/M/L/XL)
  - Gift card shows denominations (5000/10000/20000 Ft)

  BUNDLE PAGE:
  - Bundle card: component product list with quantities and
  individual prices
  - Total individual price vs bundle price comparison
  - Savings percentage badge: "Megtakarítás: 20%"
  - "Kosárba" button adds all bundle items

  EMAIL TEMPLATES (600px width):
  - All share: CraftBrew logo header centered, thin gold #D97706
  line below, footer with "CraftBrew — Specialty Coffee Budapest",
  Kazinczy u. 28, social icons
  - Welcome email: warm coffee banner, "Kedves [Név]!", welcome
  text, "Fedezd fel kávéinkat" CTA button #78350F
  - Order confirmation: "#1042" large JetBrains Mono, line items
  table, subtotal/discount/shipping/total, shipping address,
  "Holnap (Budapest)" delivery estimate
  - Shipping notification: truck icon, "Rendelésed (#1042) úton
  van!", address, delivery estimate, "Rendelés követése" CTA
  - Gift card email: gift box illustration, "[Küldő neve]
  ajándékkártyát küldött neked!", quote block for personal message,
   "GC-XXXX-XXXX" large mono code, "10 000 Ft" amount, "Beváltás a
  webshopban" CTA, "Érvényes: 1 évig"

  COOKIE CONSENT BANNER:
  - Fixed bottom bar, white bg, shadow-lg
  - Text: "Ez a weboldal sütiket használ a jobb felhasználói
  élményért."
  - Buttons: "Elfogadom" #78350F filled, "Beállítások" outlined
  - Dismiss X button

  LEGAL PAGES (simple text pages):
  - Breadcrumb: Főoldal > ÁSZF / Adatvédelmi szabályzat
  - Title h1, body text Inter 16px line-height 1.8
  - Simple clean layout on cream background