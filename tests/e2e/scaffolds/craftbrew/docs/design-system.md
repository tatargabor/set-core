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

### Badge
- Layout: flexbox

### StarRating
- Layout: flexbox

### ProductCard
- Layout: flexbox

### Header
- **colors**: color-primary, font-heading
- Layout: flexbox

### Footer
- **colors**: color-primary, font-heading
- Layout: flexbox

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
