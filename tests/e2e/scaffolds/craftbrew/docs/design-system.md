# Design System

## Design Tokens

### Colors
- `color-primary`: `#78350F`
- `color-primary-foreground`: `#FFFFFF`
- `color-secondary`: `#D97706`
- `color-secondary-foreground`: `#FFFFFF`
- `color-background`: `#FFFBEB`
- `color-surface`: `#FFFFFF`
- `color-text`: `#1C1917`
- `color-muted`: `#78716C`
- `color-border`: `#E7E5E4`
- `color-success`: `#16A34A`
- `color-warning`: `#D97706`
- `color-error`: `#DC2626`

### Typography
- `font-heading`: `'Playfair Display', serif`
- `font-body`: `'Inter', sans-serif`
- `font-mono`: `'JetBrains Mono', monospace`
- `text-h1`: `40px`
- `text-h2`: `32px`
- `text-h3`: `24px`
- `text-base`: `16px`
- `text-small`: `14px`
- `text-caption`: `12px`

### Spacing
- `spacing-base`: `8px`
- `spacing-card`: `24px`
- `spacing-grid`: `24px`
- `spacing-grid-mobile`: `16px`

### Border Radius
- `radius-button`: `6px`
- `radius-card`: `8px`

### Container
- `container-max`: `1280px`

### Fonts
- Playfair Display
- Inter
- JetBrains Mono

## Components

### Button
- Layout: Auto Layout: Horizontal, padding 24px × 12px
Min Height: 44px
Background: #78350F (Primary Brown)
Text: #FFFFFF (White), Inter Medium 16px
Border Radius: 6px

Hover State:
- Background: #5A2808 (darker brown)

Active/Pressed:
- Background: #4A2006 (even darker)

---
Auto Layout: Horizontal, padding 24px × 12px
Min Height: 44px
Background: Transparent
Border: 2px solid #78350F
Text: #78350F, Inter Medium 16px
Border Radius: 6px

Hover State:
- Background: #78350F
- Text: #FFFFFF

---
Border: 2px solid #D97706
Text: #D97706
Hover: bg #D97706, text white

---
Auto Layout: Horizontal, padding 24px × 12px
Min Height: 44px
Background: Transparent
Text: #78350F, Inter Medium 16px
Border Radius: 6px

Hover State:
- Background: #FFFBEB (warm cream)

---
Opacity: 50%
Cursor: not-allowed

### Badge
- Layout: Base:
- Auto Layout Horizontal
- Padding: 8px × 4px
- Border Radius: 4px
- Inter Medium 12px

New Badge:
- Background: #16A34A
- Text: #FFFFFF

Out of Stock:
- Background: #DC2626
- Text: #FFFFFF

Low Stock:
- Background: #D97706
- Text: #FFFFFF

Discount:
- Background: #DC2626
- Text: #FFFFFF
- Example: "-20%"

Category:
- Background: #78350F
- Text: #FFFFFF
- Example: "Etiópia", "Világos"

### StarRating
- Layout: flexbox

### ProductCard
- Layout: flexbox

### Header
- Layout: Container:
- Background: #FFFFFF
- Border Bottom: 1px solid #E7E5E4
- Shadow: Card Shadow
- Position: Sticky

Layout: 3-column (Logo | Nav | Actions)

Logo:
- Playfair Display Bold 24px
- Color: #78350F
- Left aligned

Navigation (Center):
- Auto Layout Horizontal, gap 32px
- Links: Inter Regular 16px, #1C1917
- Hover: #D97706
- Active: color #78350F with underline 2px solid

Actions (Right):
- Auto Layout Horizontal, gap 16px
- Icons: 20×20px, #1C1917
- Hover: #D97706
- Cart Badge: 20×20px circle, bg #DC2626, white text

---
Layout: 3-column (Hamburger | Logo | Actions)
All icons: 24×24px minimum touch target 44×44px

### Footer
- Layout: Container:
- Background: #F5F1E6 (slightly darker cream)
- Border Top: 1px solid #E7E5E4
- Padding: 48px

Layout: 3-column grid
Gap: 32px

Column 1 (Brand):
- Logo: Playfair Display Bold 24px, #78350F
- Tagline: Inter Regular 16px, #78716C
- Copyright: Inter Regular 14px, #78716C

Column 2 (Links):
- Title: Inter SemiBold 16px, #1C1917
- Links: Inter Regular 16px, #78716C
- Hover: #D97706
- Gap: 12px

Column 3 (Contact):
- Email: Inter Regular 16px, #78716C
- Hover: #D97706
- Address: Inter Regular 14px, #78716C
- Social Icons: 40×40px circles
  - Background: #FFFFFF
  - Icon: #1C1917
  - Hover: bg #D97706, icon white

### PromoBanner

## Page Layouts

### Home
Uses: Button, ProductCard, figma

- **Hero Banner**
- **Featured Coffees**
- **Subscription CTA**
- **Story Highlights**
- **Testimonials**

### ProductCatalog
Uses: ProductCard

- **Page Title**
- **Mobile Filter Button**
- **Filters Sidebar**
- **Price Range**
- **Product Grid**
- **Sorting**
- **Products**

### ProductDetail
Uses: Button, StarRating, Badge, ProductCard, figma

- **Breadcrumb**
- **Product Details**
- **Image**
- **Info**
- **Flavor Notes**
- **Variant Selector**
- **Size Selector**
- **Stock**
- **Quantity**
- **Actions**
- **Description**
- **Recommended Products**
- **Reviews**

### Cart
Uses: Button, figma

- **Cart Items**
- **Desktop Table**
- **Mobile Cards**
- **Coupon**
- **Gift Card**
- **Order Summary**

### Checkout
Uses: Button

- **Step Indicator**
- **Step 1: Shipping**
- **Step 2: Payment**
- **Step 3: Confirmation**
- **Order Summary**

### Login
Uses: Button


### Register
Uses: Button


### Stories
Uses: figma

- **Category Tabs**
- **Stories Grid**

### StoryDetail
Uses: figma, ProductCard

- **Breadcrumb**
- **Cover Image**
- **Article Header**
- **Share Buttons**
- **Article Content**
- **Related Products**

### NotFound
Uses: Button


### SubscriptionWizard
Uses: Button, ProductCard

- **Progress Bar**
- **Step 1: Choose Coffee**
- **Step 2: Size**
- **Step 3: Frequency**
- **Step 4: Delivery Details**
- **Step 5: Summary**

### UserDashboard
Uses: Button

- **Sidebar**
- **Content**

### AdminDashboard
- **KPI Cards**
- **Revenue Chart**
- **Top Products & Low Stock**
- **Sidebar**
- **Main Content**

### AdminProducts
Uses: Button

- **Filters**
- **DataTable**
- **Product Editor Modal**
- **Tabs**
- **Basic Tab**
- **Coffee Tab**
- **Variants Tab**
- **SEO Tab**
- **Cross-sell Tab**

### AdminOrders
Uses: Button

- **Filters**
- **DataTable**
- **Order Detail Slide-in Panel**
- **Customer Info**
- **Line Items**
- **Price Breakdown**
- **Stripe Payment ID**
- **Status Flow Buttons**
- **Status Timeline**
- **Cancel Button**

### AdminDeliveries
Uses: Button

- **Summary Bar**
- **Morning Section**
- **Forenoon Section**
- **Afternoon Section**

### AdminCoupons
Uses: Button

- **DataTable**
- **Create/Edit Modal**

### AdminPromoDays
Uses: Button


### AdminReviews
Uses: Button

- **Filters**
- **DataTable**
- **Review Content**
- **Action Buttons**
- **Reply Section**
- **Example Reply Display**

### AdminGiftCards
- **Tab Filters**
- **DataTable**

### AdminStories
Uses: Button

- **DataTable**
- **Story Editor Modal**
- **Language Tabs**

### AdminSubscriptions
Uses: Button


### UserProfile
Uses: Button

- **Sidebar - Desktop**
- **Mobile Menu Tabs**
- **Main Content**
- **Password Change Section**

### UserAddresses
Uses: Button

- **Sidebar**
- **Main Content**
- **Address Cards**
- **Add/Edit Modal**

## Image References

- **hero**: search "coffee beans barista atmospheric"
- **product**: search "ethiopian coffee beans"
- **product**: search "colombia coffee roasted"
- **product**: search "kenya coffee specialty"
- **product**: search "brazil coffee dark roast"
- **delivery**: search "coffee delivery package"
- **brewing**: search "coffee brewing pour over"
- **roasting**: search "coffee roasting process"
- **lifestyle**: search "coffee health benefits"

## Raw Theme CSS

```css
:root {
  /* CraftBrew Color Palette */
  --color-primary: #78350F;
  --color-primary-foreground: #FFFFFF;
  --color-secondary: #D97706;
  --color-secondary-foreground: #FFFFFF;
  --color-background: #FFFBEB;
  --color-surface: #FFFFFF;
  --color-text: #1C1917;
  --color-muted: #78716C;
  --color-border: #E7E5E4;
  --color-success: #16A34A;
  --color-warning: #D97706;
  --color-error: #DC2626;
  
  /* Typography */
  --font-heading: 'Playfair Display', serif;
  --font-body: 'Inter', sans-serif;
  --font-mono: 'JetBrains Mono', monospace;
  
  /* Font Sizes */
  --text-h1: 40px;
  --text-h2: 32px;
  --text-h3: 24px;
  --text-base: 16px;
  --text-small: 14px;
  --text-caption: 12px;
  
  /* Spacing */
  --spacing-base: 8px;
  --spacing-card: 24px;
  --spacing-grid: 24px;
  --spacing-grid-mobile: 16px;
  
  /* Border Radius */
  --radius-button: 6px;
  --radius-card: 8px;
  
  /* Container */
  --container-max: 1280px;
}

@theme inline {
  --color-primary: var(--color-primary);
  --color-primary-foreground: var(--color-primary-foreground);
  --color-secondary: var(--color-secondary);
  --color-secondary-foreground: var(--color-secondary-foreground);
  --color-background: var(--color-background);
  --color-surface: var(--color-surface);
  --color-text: var(--color-text);
  --color-muted: var(--color-muted);
  --color-border: var(--color-border);
  --color-success: var(--color-success);
  --color-warning: var(--color-warning);
  --color-error: var(--color-error);
}

@layer base {
  * {
    @apply border-[--color-border];
  }

  body {
    background-color: var(--color-background);
    color: var(--color-text);
    font-family: var(--font-body);
  }

  h1 {
    font-family: var(--font-heading);
    font-size: var(--text-h1);
    font-weight: 700;
    line-height: 1.2;
  }

  h2 {
    font-family: var(--font-heading);
    font-size: var(--text-h2);
    font-weight: 600;
    line-height: 1.3;
  }

  h3 {
    font-family: var(--font-heading);
    font-size: var(--text-h3);
    font-weight: 600;
    line-height: 1.4;
  }

  p {
    font-family: var(--font-body);
    font-size: var(--text-base);
    line-height: 1.6;
  }

  label {
    font-family: var(--font-body);
    font-size: var(--text-base);
    font-weight: 500;
  }

  button {
    font-family: var(--font-body);
    font-size: var(--text-base);
    font-weight: 500;
  }

  input, textarea, select {
    font-family: var(--font-body);
    font-size: var(--text-base);
  }
}
```
