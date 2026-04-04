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

- h2: "Bejelentkezés"
  - Layout: gap-2

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

**Progress Bar**

**Step 1: Choose Coffee**
  - h2: "Válaszd ki a kávédat"
  - Layout: grid-cols-1 grid-cols-2 grid-cols-4 gap-6

**Step 2: Size**
  - h2: "Forma és méret"
  - Layout: gap-4

**Step 3: Frequency**
  - h2: "Gyakoriság"
  - Layout: grid-cols-1 grid-cols-2 gap-4
  - Layout: gap-4

**Step 4: Delivery Details**
  - h2: "Kiszállítás"
  - Layout: gap-3
  - Layout: gap-4

**Step 5: Summary**
  - h2: "Összegzés"
  - h3: "Kiválasztott kávé"
  - h3: "Szállítás részletei"

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

- h1: "Termékek"

**Filters**
  - Layout: gap-4

**DataTable**
  - Layout: gap-2

**Product Editor Modal**

**Tabs**
  - Layout: gap-6

**Basic Tab**
  - Layout: grid-cols-2 gap-4
  - Layout: grid-cols-2 gap-4
  - Layout: gap-2

**Coffee Tab**
  - Layout: grid-cols-3 gap-4

**Variants Tab**
  - h3: "Variánsok"

**SEO Tab**

**Cross-sell Tab**
  - Layout: gap-3

## Page: AdminOrders

- h1: "Rendelések"

**Filters**
  - Layout: gap-4

**DataTable**

**Order Detail Slide-in Panel**

**Customer Info**
  - h3: "Vásárló"

**Line Items**
  - h3: "Termékek"
  - Layout: gap-4
  - Layout: gap-4

**Price Breakdown**

**Stripe Payment ID**

**Status Flow Buttons**
  - h3: "Állapot módosítása"
  - Layout: gap-2

**Status Timeline**
  - h3: "Állapot történet"
  - Layout: gap-3
  - Layout: gap-3

**Cancel Button**

## Page: AdminDeliveries

- h1: "Szállítás"
  - Layout: gap-3

**Summary Bar**
  - Layout: gap-6

**Morning Section**
  - Layout: gap-2

**Forenoon Section**
  - Layout: gap-2

**Afternoon Section**
  - Layout: gap-2

## Page: AdminCoupons

- h1: "Kuponok"

**DataTable**

**Create/Edit Modal**
  - h2: "Új kupon"
  - Layout: grid-cols-2 gap-4
  - Layout: grid-cols-2 gap-4
  - Layout: gap-2
  - Layout: gap-2
  - Layout: gap-3

## Page: AdminPromoDays

- h1: "Promóciós napok"
  - h2: "Új promóciós nap"
  - Layout: grid-cols-2 gap-4
  - Layout: grid-cols-2 gap-4
  - Layout: gap-2
  - Layout: gap-3

## Page: AdminReviews

- h1: "Értékelések"

**Filters**
  - Layout: gap-4

**DataTable**
  - Layout: gap-1

**Review Content**
  - Layout: gap-1
  - Layout: gap-4

**Action Buttons**
  - Layout: gap-3

**Reply Section**

**Example Reply Display**

## Page: AdminGiftCards

- h1: "Ajándékkártyák"

**Tab Filters**
  - Layout: gap-4

**DataTable**

## Page: AdminStories

- h1: "Sztorik"

**DataTable**

**Story Editor Modal**
  - h2: "Új sztori"

**Language Tabs**
  - Layout: gap-4
  - Layout: grid-cols-2 gap-4
  - Layout: grid-cols-2 gap-4
  - Layout: grid-cols-2 gap-4
  - Layout: gap-4
  - Layout: gap-2
  - Layout: gap-2
  - Layout: gap-3

## Page: AdminSubscriptions

- h1: "Előfizetések"
  - Layout: gap-2

## Page: UserProfile

- Layout: gap-8

**Sidebar - Desktop**
  - h3: "Nagy Petra"
  - Layout: gap-3

**Mobile Menu Tabs**
  - Layout: gap-2
  - Layout: gap-2

**Main Content**
  - h1: "Adataim"
  - Layout: gap-4
  - Layout: gap-2
  - Layout: gap-2

**Password Change Section**
  - h2: "Jelszó módosítása"

## Page: UserAddresses

- Layout: gap-8

**Sidebar**
  - h3: "Nagy Petra"
  - Layout: gap-3

**Main Content**
  - h1: "Címeim"

**Address Cards**
  - Layout: gap-4 grid-cols-2
  - Layout: gap-2

**Add/Edit Modal**
  - h2: "Új cím hozzáadása"
  - Layout: grid-cols-2 gap-4
  - Layout: gap-3
