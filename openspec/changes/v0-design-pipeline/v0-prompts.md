# v0.dev Prompts — CraftBrew Pages

Per-page prompts for generating CraftBrew designs in v0.dev.

Prompts are ordered by **site flow**: chrome → customer journey → admin → cross-cutting.
Each prompt is tagged:
- **[EDITORIAL]** — give v0 brand vibe + content + functionality, let v0 compose layout. Push for modern editorial design.
- **[FUNCTIONAL]** — keep structural patterns (DataTable, stepper, sidebar) because UX expectations are conventional. v0 still styles freely within the structure.
- **[HYBRID]** — mix of both within the same flow.
- **[HTML]** — static email markup, not React/shadcn.
- **[PATTERNS]** — reusable components shown together.

Paste the **Shared Theme Preamble** as v0 Project Context (not into every prompt).

**Recommended generation order:** start with Prompt 1 (Header + Footer) so subsequent
prompts can reuse it via "Use the previously generated header and footer."

---

## Shared Theme Preamble (paste as v0 Project Context)

```
Brand: CraftBrew — Hungarian specialty coffee e-commerce.
Tech: Next.js 15 App Router, shadcn/ui, Tailwind CSS v4, TypeScript, Framer Motion.
Language: Hungarian (HU) primary, EN secondary. Use HU copy in prompts.
Currency: HUF — format "2 490 Ft" (space thousands separator, no decimals).
All prices gross (27% VAT included). VAT line shown on invoice only.

THEME TOKENS (apply via CSS custom properties / tailwind):
- Primary: #78350F (coffee brown), foreground white
- Secondary / Accent: #D97706 (amber), foreground white
- Background: #FFFBEB (warm cream)
- Surface (cards/inputs): #FFFFFF
- Text: #1C1917, Muted text: #57534E
- Border: #E7E5E4
- Success: #16A34A, Warning: #D97706, Error: #DC2626

Typography:
- Headings: Playfair Display (serif) — lean into bold display sizes
- Body: Inter (sans-serif)
- Mono (codes, order numbers, gift cards): JetBrains Mono

═══════════════════════════════════════════════════════════════
DESIGN VIBE — read carefully, this is the most important context.
═══════════════════════════════════════════════════════════════

CraftBrew is a premium specialty coffee brand. The design must feel
editorial, crafted, and confident — NOT a generic e-commerce template.

References (in spirit, not literal copy):
Aesop · Blue Bottle Coffee · Origin Coffee Roasters · Stumptown ·
Workshop Coffee · MUD\WTR · Apartamento magazine · Kinfolk

Aesthetic principles:
- Bold serif display typography (Playfair) — large, confident, generous line-height
- Full-bleed photography — coffee, beans, brewing, hands, cafés
- Generous whitespace — let elements breathe, don't fill every inch
- Asymmetric, editorial composition — break the grid intentionally
- Subtle scroll-driven motion (Framer Motion fade/slide on enter, parallax hero)
- Storytelling tone — coffee is a craft, not a SKU
- Hierarchy through scale, not borders — one hero element per viewport
- Mobile-first feels designed for thumb (not just shrunk desktop)

AVOID:
- Symmetric 3/4-column card grids as the default for everything
- Dense sidebars
- Generic "Shopify template" look
- Card-on-card-on-card stacking
- Borders everywhere — use whitespace and typography for separation

═══════════════════════════════════════════════════════════════

shadcn rule: ALWAYS use shadcn/ui primitives — never invent custom equivalents.
Common: Button, Card, Sheet, Dialog, Form (react-hook-form + zod), Input,
Label, Select, Checkbox, RadioGroup, Slider, Tabs, Accordion, DataTable
(TanStack), Badge, Toaster (sonner), Avatar, DropdownMenu, Sidebar,
Breadcrumb, Calendar, Popover, Tooltip, Skeleton, Separator, Carousel,
ToggleGroup, AspectRatio.

For every interactive element show ALL relevant states:
default, hover, focus, selected, disabled, loading, error.
Show empty/loading/error data states. Show desktop AND mobile.
Indicate signed-in vs anonymous variants where relevant.

Contrast rule: muted-foreground text MUST be readable on cream background.
```

---

## 1. Header + Footer  [EDITORIAL]

```
PURPOSE: Site-wide chrome that feels like a premium magazine masthead, not a
generic shop nav. Should set the editorial tone immediately.

CONTENT (HU):
- Brand mark: "CraftBrew" — display this with confidence (Playfair, generous size)
- Primary nav links: Kávék · Eszközök · Merch · Csomagok · Előfizetés · Sztorik
- Action affordances: search, language toggle (HU / EN), wishlist, cart (with count), user
- Footer info: tagline, contact (email + Budapest address), social (Instagram/Facebook/YouTube)
- Footer legal row: ÁSZF · Adatvédelmi · Cookie szabályzat · "© 2026 CraftBrew Kft."

FUNCTIONAL:
- Header behavior on scroll is up to you (sticky, hide-on-scroll-down, transparent-over-hero, etc.)
- Search opens command palette OR slide-down panel — your call
- Language toggle persists in session
- Cart badge animates on item-add

STATES (show all):
- A) Anonymous — login link instead of avatar
- B) Signed-in — avatar + DropdownMenu (Fiókom, Rendeléseim, Kedvenceim, Kijelentkezés)
- Active nav link clearly differentiated
- Cart badge: empty (hidden), 1, 99+
- Mobile: thoughtful hamburger experience (Sheet, full-screen overlay — your judgment)

USE shadcn: Avatar, Badge, Button, Command, DropdownMenu, NavigationMenu, Sheet, Separator.
```

## 2. Homepage (`/hu`)  [EDITORIAL]

```
PURPOSE: First impression of the brand. Sell the craft, not the catalog.
This page should feel like the cover of a magazine — bold typography,
hero photography, narrative pacing. Visitors who never buy should still
feel they encountered something premium.

CONTENT (HU) — must include, sequence and composition is your call:
- Hero statement: "Specialty kávé, az asztalodra szállítva."
  Subtitle: "Válogatott szemeskávék a világ legjobb termőterületeiről."
  CTA: "Fedezd fel kávéinkat →"
- Featured coffees showcase (4 products) with title "Kedvenceink" and
  "Összes kávé →" lead-out
- Subscription pitch: title "Friss kávé minden reggel", short body, CTA "Előfizetés részletei →"
- Story highlights (3 stories) under "Sztorik" + "Összes sztori →"
- Customer voice section under "Mit mondanak vásárlóink" (3 testimonials)
- Optional editorial sections you find appropriate: origin spotlight, brewing guide teaser,
  founder note, behind-the-scenes — surprise me

FUNCTIONAL:
- Promo Day Banner (conditional, top of page when active):
  example "Bolt születésnap — minden termékre 20% kedvezmény!" with dismiss
- Subtle scroll-driven motion (fade-in, parallax on hero) — Framer Motion welcomed
- All product/story cards link out to detail pages

STATES:
- Promo banner: visible / dismissed (hidden, restorable from footer)
- Empty featured (no products yet): graceful editorial fallback, not "no data"
- Mobile: re-think hierarchy for thumb navigation, not just stacked sections

USE shadcn: Button, Card, Badge, Carousel, AspectRatio, Separator.
Use Framer Motion for scroll/parallax/fade effects.

DO NOT default to "hero + 4-col grid + 3-col grid + 3-col grid + footer".
Compose like a magazine.
```

## 3. Product Catalog (`/hu/kavek`, `/hu/eszkozok`, `/hu/merch`)  [EDITORIAL]

```
PURPOSE: Browse a category. Filtering must work but should not dominate
visually. Think editorial product index, not a Shopify search results page.

CONTENT (HU):
- Category title (e.g. "Kávék") with confident display typography
- Optional editorial intro paragraph for the category (1-2 sentences setting tone)
- Result count: "32 termék"
- Filtering controls:
  - Eredet: Etiópia, Kolumbia, Kenya, Brazília, Guatemala
  - Pörkölés: Világos, Közepes, Sötét
  - Feldolgozás: Mosott, Természetes, Honey
  - Ár: range slider (HUF) with min/max inputs
  - "Szűrők törlése" affordance
- Sort: Népszerűség, Ár növekvő, Ár csökkenő, Újdonságok
- Per product: image, name, origin (subtitle), price ("2 490 Ft"), star rating

FUNCTIONAL:
- Filters can be a sticky panel, slide-out Sheet, top-bar with chip strip,
  command bar — your judgment on what feels modern. Avoid the default
  "sticky left sidebar of checkboxes" cliché.
- Applied filters visible as removable chips
- Pagination OR "Tovább betöltés" button — pick one
- Loading: thoughtful skeletons that match the editorial layout

STATES:
- Product card: default, hover (subtle motion), "ÚJ" badge (released < 7 days),
  "ELFOGYOTT" badge (all variants out)
- Empty results: editorial illustration + "Nincs találat — próbálj kevesebb szűrőt" + CTA
- Loading skeletons
- Mobile: filter access via Sheet, thumb-friendly product browse

USE shadcn: Accordion, Badge, Button, Card, Checkbox, Input, Label,
Pagination, Select, Sheet, Skeleton, Slider, ToggleGroup.

The product card design is the most important element — make it feel
crafted, not generic. Think editorial product photography presentation.
```

## 4. Product Detail (`/hu/kavek/[slug]`)  [EDITORIAL]

```
PURPOSE: Sell one specific coffee through storytelling + product info.
This is where the brand earns the sale — let the photography and
typography lead, then deliver function.

CONTENT (HU):
- Breadcrumb: "Kávék / Etiópia / Yirgacheffe"
- Product name (e.g. "Ethiopia Yirgacheffe") — use display typography
- Star rating + "(12 értékelés)" link to reviews section
- Price (must be prominent, but composition is your call)
- Origin/Roast/Processing metadata
- Flavor tags (e.g. "Áfonya", "Csokoládé", "Citrus")
- Variant selectors:
  - Forma: Szemes / Őrölt — Espresso / Drip Bag
  - Méret: 250g / 500g / 1kg
- Stock indicator: "Készleten: 45 db" / "Hamarosan elfogy" / out-of-stock state
- Quantity stepper
- "Kosárba" primary action
- "Kedvencekhez" secondary
- Below product info (sequence flexible):
  - Long-form description / brewing notes (rich text)
  - Tasting notes section (visual flavor wheel? styled list? your call)
  - "Ajánlott mellé" — 4 cross-sell products
  - "Értékelések" — existing reviews + write-review CTA for buyers

FUNCTIONAL:
- Variant selection updates price + stock dynamically
- Out-of-stock variant: disabled with "Elfogyott" badge
- Product fully out of stock: "Kosárba" replaced by "Értesíts ha újra elérhető"
  → opens RestockNotifyDialog (email pre-filled if signed-in)
- Anonymous heart click → login redirect with toast
- Image: support multiple images, zoomable on desktop, swipeable on mobile

STATES (CRITICAL):
- Variant button: default, hover, selected (clear visual differentiation),
  disabled with "Elfogyott" indicator
- Out-of-stock product: notify-me CTA replaces buy
- Loading skeletons

USE shadcn: Badge, Breadcrumb, Button, Card, Carousel, Dialog, Input, Label,
Separator, Skeleton, Tabs, ToggleGroup (variants), Tooltip.

AVOID the "image left, fixed details right" default 2-column. The
hero/details/story layering should feel like an editorial product feature.
```

## 5. Cart (`/hu/kosar`)  [FUNCTIONAL]

```
PURPOSE: Review cart, apply codes, proceed to checkout.

LAYOUT: 2-column desktop (items left, summary sidebar right). Mobile: stacked + sticky CTA.

CONTENT (HU):
- Page title: "Kosár"
- Items list: thumbnail, name + variant ("Ethiopia Yirgacheffe — Szemes, 500g"),
  quantity stepper, line total, remove (X)
- Summary card:
  - Coupon input + "Beváltás" → applied state shows green chip with X
  - Gift card input + "Beváltás" → applied state shows balance + amount applied
  - Részösszeg
  - Kedvezmény (only if applied — green, negative)
  - Promo nap kedvezmény (only if active promo day)
  - Szállítás (estimate or "kalkuláció pénztárnál")
  - Összesen (large, primary)
  - Primary CTA: "Tovább a pénztárhoz"

STATES:
- Empty cart: branded illustration + "A kosarad üres" + "Vásárlás folytatása" link
- Coupon: empty / valid / invalid ("Érvénytelen kód") / expired ("Lejárt kupon") /
  not applicable ("Csak első rendelésnél")
- Gift card: empty / valid (shows balance) / depleted / expired
- CTA variant: signed-in → "Tovább a pénztárhoz", anonymous → "Bejelentkezés a fizetéshez"
- Mobile: sticky bottom CTA

USE shadcn: Badge, Button, Card, Input, Label, Separator, Skeleton, Toaster.
```

## 6. Checkout (`/hu/penztar`) — 3 steps  [FUNCTIONAL]

```
PURPOSE: Convert cart to paid order. Stepper UX is functional and required.

LAYOUT: Stepper at top (Szállítás → Fizetés → Megerősítés), main form left,
order summary card right (sticky on desktop).

STEP 1 — Szállítás:
- Method radio cards:
  - "Házhozszállítás" — zone-detected cost ("Budapest: 990 Ft")
  - "Személyes átvétel — CraftBrew Labor"
    Address: Kazinczy u. 28, 1075 Budapest
    Hours: H–P 7:00–18:00, Szo 8:00–14:00
    Cost: "Ingyenes"
- Address selector (when "Házhozszállítás"): saved cards with zone badges
  (Budapest / +20km / +40km), "+ Új cím" → AddressDialog
- Free-shipping note: "15 000 Ft felett ingyenes Budapesten"
- Estimated delivery date displayed
- Continue: "Tovább a fizetéshez →"

STEP 2 — Fizetés (Stripe-style):
- Masked/formatted inputs (numeric keyboard, autoComplete):
  - Kártyaszám (spaced groups of 4)
  - Lejárat (MM/YY auto-slash)
  - CVC (masked)
- Stripe security note + logos
- "Fizetés" primary

STEP 3 — Megerősítés:
- Success icon
- "Köszönjük a rendelést!"
- Order number in mono ("#CB-20260415-001")
- Items summary, breakdown, shipping address
- Buttons: "Rendeléseim", "Tovább vásárolok"

STATES:
- Stepper: completed (check), active, upcoming
- Card validation per field
- Payment processing: button spinner + disabled
- Payment failed: red Alert above form, "Próbáld újra"
- ZERO-AMOUNT skip: gift card covers total → Step 2 skipped, stepper shows
  "Szállítás ✓ → Fizetés (átugorva) → Megerősítés"
- Anonymous: redirect to login before Step 1
- Mobile: stepper collapses to "2/3 lépés", summary above form

USE shadcn: Alert, Button, Card, Form, Input, Label, RadioGroup,
Separator, Skeleton.

Apply brand styling but keep stepper UX conventional.
```

## 7. Auth — Login, Register, Password Reset  [FUNCTIONAL]

```
PURPOSE: Account access pages.

LAYOUT: Centered card on cream background. Optional: split-screen with
brand photography on one side (your call — make it feel premium not utilitarian).

LOGIN (/hu/belepes):
- Logo, "Bejelentkezés"
- Email + Password (with show/hide toggle) + "Emlékezz rám" checkbox
- Primary: "Bejelentkezés"
- "Elfelejtett jelszó?" link
- Divider: "Nincs még fiókod?"
- Outlined: "Regisztráció"

REGISTER (/hu/regisztracio):
- "Regisztráció"
- Fields: Teljes név, Email, Jelszó (helper "minimum 8 karakter"), Jelszó megerősítése
- Language: HU / EN radio
- Checkbox: "Elfogadom az ÁSZF-et és az Adatvédelmi szabályzatot"
- Primary: "Regisztráció"
- Link: "Van már fiókod? Bejelentkezés"

PASSWORD RESET REQUEST (/hu/jelszo-csere):
- "Elfelejtett jelszó"
- Email + "Új jelszó kérése"
- Success state: success icon + "Emailt küldtünk a megadott címre."

PASSWORD RESET (/hu/jelszo-csere/[token]):
- "Új jelszó beállítása"
- New password + confirm + "Mentés"
- Token expired state: error + "Új link kérése"

STATES:
- Field validation errors
- Generic auth failure: "Érvénytelen email vagy jelszó"
- Loading: button spinner + disabled form
- Mobile: card full-width with padding

USE shadcn: Button, Card, Checkbox, Form, Input, Label, RadioGroup,
Separator, Toaster.
```

## 8. Account Layout + Dashboard (`/hu/fiokom`)  [FUNCTIONAL]

```
PURPOSE: Account hub. Sidebar nav is functional and required.

LAYOUT: 2-column — left sidebar nav, right content. Mobile: horizontal scrollable tab strip.

SIDEBAR NAV (HU):
- Adataim → /fiokom
- Címeim → /fiokom/cimek
- Rendeléseim → /rendeleseink (outside /fiokom — same sidebar still applies)
- Előfizetéseim → /fiokom/elofizetesek
- Kedvenceim → /fiokom/kedvencek

DASHBOARD CONTENT:
- Title: "Fiókom"
- Welcome line: "Üdv újra, [Név]!"
- 4 summary cards:
  - "Adataim" — name, email preview, "Szerkesztés →"
  - "Címeim" — default address preview, "Mind →"
  - "Rendeléseim" — last order status badge, "Mind →"
  - "Kedvenceim" — count + 3 thumbnails, "Mind →"

STATES:
- Active sidebar item visually distinct
- Show 2 variants:
  A) /fiokom active (Adataim highlighted)
  B) /rendeleseink active (Rendeléseim highlighted) — proves sidebar persists
- Mobile: sidebar becomes horizontal tab bar (Tabs)

USE shadcn: Avatar, Button, Card, Sidebar, Tabs (mobile), Separator.

Apply editorial typography + whitespace within the layout.
```

## 9. Profile + Addresses (`/fiokom`, `/fiokom/cimek`)  [FUNCTIONAL]

```
PURPOSE: Personal info management within Account Layout.

PROFILE:
- Form card: Teljes név, Email (read-only with lock), Nyelv (HU/EN toggle),
  Hírlevél preferenciák (checkboxes)
- "Mentés" primary
- Separate section "Jelszó módosítása" (collapsed/expanded):
  Régi jelszó, Új jelszó, Megerősítés + "Módosítás"

ADDRESSES:
- "+ Új cím" button at top
- Address grid:
  - Card: Label ("Otthon"), name, address text, phone,
    zone badge ("Budapest" / "+20km" / "+40km"), default star icon
  - Actions: Szerkesztés, Törlés, Alapértelmezettnek jelölés
- Add/Edit Dialog: Label, Teljes név, Irányítószám (auto zone-detect badge appears live),
  Város, Utca és házszám, Telefon

STATES:
- Empty addresses: illustration + "Még nincs mentett cím" + CTA
- Default address: star icon + "Alapértelmezett" badge
- Form validation per field
- Optimistic delete with undo Toast

USE shadcn: Badge, Button, Card, Dialog, Form, Input, Label,
Separator, Toaster.
```

## 10. Wishlist (`/hu/fiokom/kedvencek`)  [EDITORIAL]

```
PURPOSE: Saved-for-later products inside Account Layout. Should feel like
a curated personal selection, not a database list.

CONTENT (HU):
- Title: "Kedvenceim"
- Sort: Hozzáadás dátuma / Ár / Név
- Per product: image, name, price, rating, stock state
- Each card: heart (filled, click removes with undo Toast), "Kosárba" button,
  "Értesíts" toggle for out-of-stock items
- Bulk actions when items selected: "Mind kosárba" + "Eltávolítás"
- View toggle: gallery / compact list

STATES:
- Empty: editorial illustration + "Nincs még semmi a kedvenceid között." +
  "Vásárlás folytatása" CTA — make this feel inviting, not error-like
- Out-of-stock card: "ELFOGYOTT" badge + "Értesíts" toggle (with active state +
  Tooltip "Értesítünk amint újra elérhető")
- Anonymous: redirect to login with Toast "Jelentkezz be a kedvenceidhez"

USE shadcn: Badge, Button, Card, Checkbox, Select, Toaster, ToggleGroup, Tooltip.
Inside Account Layout (sidebar from Prompt 8).
```

## 11. Subscription — Wizard, Management, Calendar  [HYBRID]

```
PURPOSE: Set up + manage recurring deliveries. Wizard UX required.
The MANAGEMENT page (existing subscriptions) can be more editorial.

WIZARD (/hu/elofizetes/uj) — 5 steps with progress indicator:

STEP 1 — Kávé választás: Coffee product grid (RadioGroup with Card items)
STEP 2 — Méret: 250g / 500g / 1kg radio cards with prices
STEP 3 — Gyakoriság: radio cards with discount badges
- Naponta (-15%) — DISABLED + Tooltip "Csak Budapesten" if zone is +20km/+40km
- Hetente (-10%)
- Kéthetente (-7%)
- Havonta (-5%)
STEP 4 — Szállítási részletek: address selector + time window radio
(Reggel 6–9, Délelőtt 9–12, Délután 14–17)
STEP 5 — Összegzés: summary card + price calc + "Előfizetés indítása"

MANAGEMENT (/hu/fiokom/elofizetesek):
This page can be designed editorially — feel free to skip "Card per subscription"
default. Show active subscriptions with personality (next delivery countdown,
"this week's coffee" feature, calendar visualization).
- Active subscription info: success Badge "Aktív", coffee, "Naponta, Reggel (6-9)",
  next delivery date, price + savings Badge
- Actions per subscription: Módosítás, Szüneteltetés, Kihagyás, Lemondás
- Calendar visualization: month grid with icons per day:
  ✓ delivered, ⏳ scheduled, ⏸ paused, ❌ skipped

DIALOGS:
- PAUSE: Calendar date range picker + reason textarea + "Szüneteltetés"
- SKIP: Calendar of upcoming deliveries — pick date → confirm "Kihagyás"
- MODIFY (Sheet): reuse wizard fields, "Mentés"
- CANCEL: reason dropdown + textarea + "Lemondás" destructive

STATES:
- Wizard progress: completed/active/upcoming
- Pause active: "Szüneteltetve [dátum]-ig" Badge
- Empty: "Még nincs aktív előfizetésed" + "Indíts egyet" CTA

USE shadcn: Alert, Badge, Button, Calendar, Card, Dialog, Form, Popover,
Progress, RadioGroup, Sheet, Separator, Tooltip.
```

## 12. Stories — List + Detail (`/hu/sztorik`, `/hu/sztorik/[slug]`)  [EDITORIAL]

```
PURPOSE: Editorial content hub. This is where CraftBrew's design
language gets its purest expression — magazine-grade article layouts.

LIST PAGE:

CONTENT (HU):
- Section title: "Sztorik"
- Optional: editorial intro line about the publication
- Categories: Mind, Eredetsztorik, Pörkölés, Főzési útmutatók, Egészség, Ajándékötletek
- Per story: cover image, category, title, author, date, excerpt (1-2 lines),
  reading time ("5 perc olvasás")

FUNCTIONAL:
- Category filter (tabs / chips / dropdown — your call)
- Sort: legújabb / legolvasottabb
- Pagination OR infinite scroll

LAYOUT NOTE: This is the page where editorial composition matters most.
Try varied card sizes (featured story = larger), asymmetric grids,
magazine-style mosaics. NOT a uniform 3-column grid.

STATES:
- Active category clearly indicated
- Empty category: "Hamarosan érkeznek sztorik ebben a kategóriában." + illustration
- Mobile: horizontal scroll for categories, single-column story flow

DETAIL PAGE:

CONTENT (HU):
- Breadcrumb: "Sztorik / Eredetsztorik / [Title]"
- Article: title, author, published date, category, reading time, share row
- Cover photography (hero treatment — full-bleed encouraged)
- Body: rich text with H2/H3 sections, blockquotes, inline images, lists
- "Kapcsolódó termékek" — 3 cross-linked products at end
- "További sztorik" — 3 more stories at end

LAYOUT: Treat this like a magazine article. Generous line-length, strong
typography hierarchy, drop caps welcome, inline images that break out of
text width. NOT a constrained narrow blog post template.

USE shadcn: AspectRatio, Avatar, Badge, Breadcrumb, Button, Card,
Pagination, Separator, Tabs.
```

## 13. Search Results (`/hu/kereses?q=...`)  [EDITORIAL]

```
PURPOSE: Search across products + stories. Compose like an editorial
"answers" page — products and stories side by side, feels intentional.

CONTENT (HU):
- Title: "Találatok: '[query]'" + count "32 termék · 5 sztori"
- Filter chips: Mind / Csak termékek / Csak sztorik
- Sort: Relevancia / Ár növekvő / Ár csökkenő / Legújabb
- Products section (cap visible at 12) + "Mind a [n] termék →"
- Stories section (cap visible at 6) + "Mind a [n] sztori →"
- HEADER SEARCH DROPDOWN variant: top 5 products + top 3 stories +
  "Összes találat megtekintése →"

FUNCTIONAL:
- Search query highlighted in result titles
- Empty results: "Nincs találat 'X'-re" + suggestions ("Próbáld meg: kávé, espresso, drip")
- Loading: section Skeletons

USE shadcn: Badge, Button, Card, Command (header dropdown), Input, Select,
Separator, Skeleton.
```

## 14. Legal Pages + Cookie Consent  [FUNCTIONAL]

```
PURPOSE: ÁSZF, Adatvédelmi szabályzat, Cookie szabályzat + first-visit consent banner.

LEGAL PAGE LAYOUT (single template, 3 routes):
- Centered content, max ~720px, sticky table-of-contents on desktop
- Title (e.g. "Általános Szerződési Feltételek")
- "Utolsó frissítés: 2026-04-01"
- Long-form rich text: H2 sections + numbered subsections
- "Letöltés PDF" button at bottom

ROUTES:
- /hu/aszf, /hu/adatvedelem, /hu/cookie

COOKIE CONSENT BANNER:
- Sticky bottom bar (or bottom-left card on mobile)
- "Süti szabályzat" + body text
- Buttons: "Beállítások" (outlined), "Elfogadás" (primary)
- Dismiss X = decline non-essential

PREFERENCE DIALOG (from "Beállítások"):
- Categories with toggles:
  - Szükséges (locked on)
  - Funkcionális
  - Analitika
  - Marketing
- "Mentés" + "Mind elfogadása"

STATES:
- First visit: banner visible
- After choice: hidden (re-openable from footer link)
- Mobile: banner is bottom Sheet

USE shadcn: Button, Card, Dialog, Sheet, Switch, Tabs, Separator.
```

## 15. Error Pages (`/404`, `/500`)  [EDITORIAL]

```
PURPOSE: Branded error pages that maintain editorial feel even on failure.

404:
- Coffee-themed illustration (empty cup)
- Headline: "Hoppá! Ez az oldal nem található."
- Body: "A keresett oldal nem létezik vagy átköltözött."
- Search input (real search)
- Primary CTA: "Vissza a főoldalra"
- Secondary links: Kávék, Sztorik, Kapcsolat

500:
- Different illustration (cracked cup)
- Headline: "Valami hiba történt."
- Body: "Próbáld újra később, vagy lépj kapcsolatba velünk."
- Primary CTA: "Főoldal"
- Email link: hello@craftbrew.hu

VARIANT — category not-found (e.g. /hu/kavek/nemletezo):
- Same template, copy adapted: "Nem találtuk a terméket"
- "Vissza a kávékhoz" CTA

USE shadcn: Button, Card, Input.

These should feel like part of the brand, not generic Next.js defaults.
```

## 16. Email Templates (transactional)  [HTML]

```
PURPOSE: 7 transactional emails as static HTML templates.
NOT shadcn — design as inline-styled HTML with table-based layout, max 600px wide.
Brand colors but conservative (emails render in many clients).

TEMPLATES (HU + EN parallel):
1. Welcome — "Üdv a CraftBrew-nál!" + brand intro + 3 featured products + CTA
2. Order Confirmation — order # mono, items table, totals, address, "Rendelés követése"
3. Shipping Notification — courier + tracking link, estimated delivery
4. Delivery Confirmation + Review Request — "Hogy ízlett a kávé?" + 5-star CTA → review
5. Back-in-Stock Alert — product card + "Megnézem" + opt-out link
6. Promo Day Announcement — banner + discount %, valid until, CTA
7. Password Reset — "Jelszó visszaállítása" + button (24h expiry note)

EVERY template:
- Header: CraftBrew logo + tagline
- Footer: address, unsubscribe (where applicable), social, "© 2026 CraftBrew Kft."

STATES:
- Show HU + EN side by side for one (Welcome) to demo i18n
- Show dark-mode safe preview for one

OUTPUT: HTML preview (not React) — emails ship as MJML or HTML strings.
```

## 17. Admin Layout + Dashboard (`/admin`)  [FUNCTIONAL]

```
PURPOSE: Admin shell + KPIs. Layout reused on EVERY admin page.

LAYOUT: Persistent left sidebar + top header with breadcrumb + user.

SIDEBAR NAV (HU):
Dashboard, Termékek, Rendelések, Szállítások, Előfizetések, Kuponok,
Akció napok, Ajándékkártyák, Értékelések, Sztorik, Visszaküldések, Felhasználók, Beállítások

DASHBOARD CONTENT:
- 4-column KPI cards: "Mai bevétel", "Rendelések ma", "Aktív előfizetők", "Új regisztráció (7 nap)"
- "Bevétel (7 nap)" — bar/line Chart card
- 2-column row:
  - "Top termékek ma" — ranked list with thumbnail, name, units sold
  - "Alacsony készlet" — list with warning icons + stock count
- "Legutóbbi műveletek" audit log card (admin name, action, timestamp)

REQUIREMENTS:
- Toaster mounted in layout (sonner)
- SessionProvider with server-session

STATES:
- Active sidebar item highlighted
- Empty data states ("Még nincs adat")
- KPI Skeletons loading

USE shadcn: Avatar, Badge, Breadcrumb, Card, Chart (recharts),
DropdownMenu, Sidebar, Separator, Skeleton, Toaster.

Admin can be more conventional — clarity > flair. But still apply brand
typography and color so it feels like CraftBrew, not generic Tailwind UI.
```

## 18. Admin Products (`/admin/termekek`)  [FUNCTIONAL]

```
PURPOSE: CRUD for catalog (coffees, equipment, merch, bundles).

LAYOUT: Filters + DataTable + product editor as Sheet.

CONTENT (HU):
- Toolbar: Category Select, Status Select, Search, "+ Új termék" primary
- DataTable columns: thumbnail, Név, Kategória, Alapár, Készlet, Státusz Badge,
  Műveletek (DropdownMenu — Szerkesztés, Másolás, Törlés)
- Bulk action bar when rows selected: "X kijelölve" + "Aktiválás" / "Inaktiválás" / "Törlés"

PRODUCT EDITOR SHEET — 5 tabs:
1. Alap: Név HU/EN, Leírás HU/EN, Kategória, Alapár, Képek (URL list with reorder), Aktív Switch
2. Kávé (only for coffee): Eredet/Pörkölés/Feldolgozás Selects, Ízjegyek tag input
3. Variánsok: SKU DataTable (Opciók, Ár módosító, Készlet, Aktív Switch — inline edit)
4. SEO: auto-generated slug + override, Meta cím / leírás HU/EN with 160-char counter, OG image
5. Keresztértékesítés: Termék multi-select (max 3)

BUNDLE EDITOR variant: components list with quantities, "Külön ár" vs "Csomag ár",
auto savings Badge "Megtakarítás: 20%".

STATES:
- DataTable empty / loading (Skeleton rows) / error
- Form unsaved-changes warning when closing Sheet
- Image URL invalid → red border + "Érvénytelen URL"
- Stock = 0 → row Badge "ELFOGYOTT"

USE shadcn: Badge, Button, Card, Checkbox, DataTable, DropdownMenu,
Form, Input, Label, Select, Sheet, Switch, Tabs, Textarea, Toaster.
```

## 19. Admin Orders (`/admin/rendelesek`)  [FUNCTIONAL]

```
PURPOSE: View, manage, fulfill orders.

LAYOUT: Filters + DataTable + slide-in detail Sheet.

TOOLBAR: Status Select, Date range Calendar Popover, Search (order # or customer)

DATATABLE: #Szám (mono), Vásárló, Dátum, Összeg, Állapot Badge, Részletek

STATUS BADGES (distinct colors):
Új (info blue), Feldolgozás (warning yellow), Csomagolva (orange),
Szállítás (purple), Kézbesítve (success green), Lemondva (error red),
Visszaküldés folyamatban (gray)

ORDER DETAIL SHEET:
- Header: order # + status Badge + Stripe Payment ID (mono, copy button)
- Customer Card: name, email, phone, "Korábbi rendelések: 5" link
- Shipping Card: address, zone, delivery method, estimated date
- Items: thumbnail + name + variant + qty + line total
- Totals: részösszeg, kupon, ajándékkártya, szállítás, ÁFA, összesen
- Status timeline (vertical, left side): icon + status + timestamp + admin name
- Action buttons (next-step enabled by current status):
  "Feldolgozás" → "Csomagolva" → "Szállítás" → "Kézbesítve"
- Destructive: "Lemondás" → confirmation Dialog with reason textarea
- "Visszaküldés indítása" if delivered

STATES:
- DataTable empty / loading / error
- Status flow buttons enabled/disabled by current status
- Lemondás confirmation requires typed "LEMONDÁS"

USE shadcn: Alert, AlertDialog, Badge, Button, Calendar, Card, DataTable,
Dialog, Input, Label, Popover, Select, Separator, Sheet, Skeleton, Textarea, Toaster.
```

## 20. Admin Deliveries (`/admin/szallitasok`)  [FUNCTIONAL]

```
PURPOSE: Daily delivery roster — courier-friendly view.

LAYOUT: Date picker + grouped delivery rows + summary bar.

CONTENT (HU):
- Title: "Szállítások"
- Date Calendar Popover (default today)
- Sections grouped by time window with sticky group headers:
  - "Reggel (6:00–9:00)"
  - "Délelőtt (9:00–12:00)"
  - "Délután (14:00–17:00)"
- Each delivery row: Checkbox, idő, vásárló, rövid cím, termék + variáns,
  zona Badge, Status (✓ Kézbesítve)
- Bottom summary: "Összesen: 10 | Előfizetés: 7 | Egyszeri: 3 | Budapest: 8 | +20km: 2"
- Top-right: "Mind kézbesítve" bulk button

STATES:
- Row checkbox: unchecked / checked → status update with Toast
- Bulk confirmation Dialog → success Toast: "10 szállítás kézbesítettnek jelölve"
- Empty day: "Nincs ütemezett szállítás erre a napra"
- Print-friendly view: "Nyomtatás" button (clean printable layout)

USE shadcn: Badge, Button, Calendar, Card, Checkbox, Dialog, Popover, Separator, Toaster.
```

## 21. Admin Coupons + Promo Days + Gift Cards + Reviews  [FUNCTIONAL]

```
PURPOSE: 4 management pages, identical Admin Layout.

COUPONS (/admin/kuponok):
- DataTable: Kód (mono), Típus (% / Ft Badge), Érték, Kategória, Lejárat,
  Felhasználás (used/max), Aktív Switch
- Editor Dialog: Kód (uppercase), Típus Select, Érték, Min. rendelés, Max. felhasználás,
  Kategória multi-select, "Csak első rendelés" Checkbox, Lejárat Calendar, Aktív Switch
- Seeded: ELSO10, NYAR2026, BUNDLE20

PROMO DAYS (/admin/akcio-napok):
- DataTable: Név, Dátum, Kedvezmény %, Email küldve Badge, Aktív Switch
- Editor Dialog: Név HU/EN, Dátum Calendar, Kedvezmény %, Banner szöveg HU/EN
  (200-char counter), Aktív Switch
- Banner Preview Card: full-width amber band + dismiss X
- Seeded: "Bolt születésnap" (03-15, 20%), "Kávé Világnapja" (10-01, 15%)

GIFT CARDS (/admin/ajandekkartyak):
- Tabs: Aktív / Lemerült / Lejárt
- DataTable: Kód (mono GC-XXXX-XXXX), Eredeti összeg, Egyenleg, Vásárló, Lejárat, Státusz Badge
- Detail Dialog: card info + transaction log (Dátum, Típus PURCHASE/REDEMPTION,
  Összeg, Felhasználó, Egyenleg utána)

REVIEWS (/admin/ertekelesek):
- DataTable: Csillagok, Termék, Felhasználó, Cím (truncated), Státusz Badge
  (Új blue / Elfogadva green / Elutasítva red), Dátum
- Filters: Status, Min. csillag Slider, Termék
- Expanded detail Card: full review, user info, product link
- Actions: "Elfogadás" (success), "Elutasítás" (destructive)
- Reply Textarea (500-char) + "Válasz küldése"
- After reply: "CraftBrew válaszolt:" indented Card on customer-facing PRODUCT page (show this variant)

USE shadcn: Badge, Button, Calendar, Card, DataTable, Dialog, Form, Input, Label,
Popover, Select, Separator, Slider, Switch, Tabs, Textarea, Toaster.
```

## 22. Shared Modals + Toaster Patterns  [PATTERNS]

```
PURPOSE: Reusable interactive components referenced across multiple pages.

DESIGN AS A SINGLE PAGE showcasing each:

A) Toaster (sonner):
- Position: top-right desktop, top-center mobile
- Variants: Success (green border-left), Error (red), Info (blue), Warning (amber)
- Optional action button ("Visszavonás", "Megnézés")
- Show 4 examples stacked + auto-dismiss progress bar

B) Restock Notify Dialog (from out-of-stock product):
- "Értesítés újra elérhetőségről"
- Email input (pre-filled if signed-in)
- "Szólunk amint újra raktáron lesz."
- Mégsem / "Feliratkozás"

C) Return Request Dialog (from past order):
- "Visszaküldés kérése"
- Order # display (read-only)
- Items list with Checkboxes (pick which to return)
- Reason Select (Hibás termék / Nem felel meg / Téves rendelés / Egyéb)
- Comment Textarea
- Photo upload (drag-drop, max 3 images)
- Mégsem / "Kérelem küldése"

D) Confirmation Dialogs (destructive AlertDialog pattern):
- Standard: title + body + Cancel + destructive primary
- Type-to-confirm: requires typing "TÖRLÉS" before delete enables

E) Empty States (showcase as cards):
- Empty cart, empty wishlist, no results, no orders, no subscriptions
- Each: editorial illustration + headline + body + CTA — feel inviting, not error-like

USE shadcn: AlertDialog, Button, Card, Checkbox, Dialog, Form,
Input, Label, Select, Separator, Textarea, Toaster.
```

---

## Iteration Tips for v0.dev

1. **Set the preamble as v0 Project Context** — every prompt then inherits tokens, language, conventions, vibe, shadcn rule. Don't paste it per prompt.

2. **For [EDITORIAL] prompts: if the first generation looks too template-y, push back**:
   - "Compose this more editorially — less symmetric, larger typography, more whitespace."
   - "Make this feel like Aesop / Blue Bottle, not Shopify."
   - "The hero should occupy the full viewport with one statement — break the grid below."

3. **For [FUNCTIONAL] prompts: if v0 invents weird structure, pull back**:
   - "Use a standard left sidebar + content layout."
   - "DataTable with sortable columns — don't replace with cards."

4. **Iterate on states, not from scratch**:
   - "Show the disabled variant of the Naponta option."
   - "Add the empty state for this list."
   - "Show the mobile breakpoint with sticky CTA at bottom."

5. **Enforce shadcn**: if v0 invents a custom component, ask "Replace with shadcn [Component]."

6. **Cross-page consistency**: generate Header + Footer (Prompt 1) FIRST, then in subsequent prompts say "Use the previously generated header and footer."

7. **Verify contrast manually**: muted text on cream background. If unreadable: "Increase muted-foreground contrast to AA on cream."

8. **Save screenshots** as `docs/v0-screenshots/[page].png` alongside markdown specs as visual ground truth.

9. **The output is a design reference, not final code** — extract layout patterns into design-brief.md for the orchestration agents.
```