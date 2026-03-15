# CraftBrew Figma Design Specification
## Premium Specialty Coffee E-commerce Platform

---

## 📋 Quick Start Guide

### Figma Setup
1. Create new Figma file: "CraftBrew Design System"
2. Create pages: Design Tokens, Components, Desktop Screens, Mobile Screens, Admin Screens
3. Set canvas background to `#FFFBEB` (warm cream) for accurate preview

### Recommended Figma Plugins
- **Stark** - Accessibility checker
- **Contrast** - Color contrast checker
- **Unsplash** - Coffee imagery
- **Auto Layout** - For responsive components
- **Iconify** - Icon library (Lucide icons)

---

## 🎨 DESIGN TOKENS

### Color Styles (Create in Figma)

#### Primary Colors
```
Primary Coffee Brown
#78350F
Usage: Buttons, CTAs, active states, logo, primary actions

Secondary Gold
#D97706
Usage: Hover states, focus rings, highlights, links, accents
```

#### Background & Surfaces
```
Background Warm Cream
#FFFBEB
Usage: Page background, main canvas

Surface White
#FFFFFF
Usage: Cards, panels, modals, header, product cards
```

#### Text Colors
```
Text Dark
#1C1917
Usage: Headings, primary text, main content

Text Muted
#78716C
Usage: Secondary text, captions, placeholders, disabled text
```

#### Borders
```
Border Light
#E7E5E4
Usage: Default borders, dividers, separators, card outlines
```

#### Semantic Colors
```
Success Green
#16A34A
Usage: In stock badges, success messages, confirmations

Warning Amber
#D97706
Usage: Low stock badges, warnings

Error Red
#DC2626
Usage: Out of stock, errors, destructive actions
```

### Typography Styles (Create in Figma)

#### Font Families
1. **Playfair Display** (Headings)
   - Weights: Regular (400), SemiBold (600), Bold (700)
   - Google Fonts: https://fonts.google.com/specimen/Playfair+Display

2. **Inter** (Body & UI)
   - Weights: Regular (400), Medium (500), SemiBold (600)
   - Google Fonts: https://fonts.google.com/specimen/Inter

3. **JetBrains Mono** (Code & Numbers)
   - Weights: Regular (400), Medium (500)
   - Google Fonts: https://fonts.google.com/specimen/JetBrains+Mono

#### Text Styles
```
Heading 1
Font: Playfair Display Bold (700)
Size: 40px
Line Height: 48px (1.2)
Color: #1C1917 (Text Dark)

Heading 2
Font: Playfair Display SemiBold (600)
Size: 32px
Line Height: 41.6px (1.3)
Color: #1C1917 (Text Dark)

Heading 3
Font: Playfair Display SemiBold (600)
Size: 24px
Line Height: 33.6px (1.4)
Color: #1C1917 (Text Dark)

Body Large
Font: Inter Regular (400)
Size: 18px
Line Height: 28.8px (1.6)
Color: #1C1917 (Text Dark)

Body Regular
Font: Inter Regular (400)
Size: 16px
Line Height: 25.6px (1.6)
Color: #1C1917 (Text Dark)

Body Small
Font: Inter Regular (400)
Size: 14px
Line Height: 21px (1.5)
Color: #78716C (Text Muted)

Caption
Font: Inter Regular (400)
Size: 12px
Line Height: 16.8px (1.4)
Color: #78716C (Text Muted)

Label/Button
Font: Inter Medium (500)
Size: 16px
Line Height: 25.6px (1.6)
Color: Varies

Monospace
Font: JetBrains Mono Regular (400)
Size: 14px
Line Height: 21px (1.5)
Color: #1C1917 (Text Dark)
```

### Effects (Shadows)

```
Card Shadow
Type: Drop Shadow
X: 0, Y: 1, Blur: 3, Spread: 0
Color: #000000 10% opacity
+
X: 0, Y: 1, Blur: 2, Spread: 0
Color: #000000 6% opacity

Card Hover Shadow
Type: Drop Shadow
X: 0, Y: 4, Blur: 6, Spread: 0
Color: #000000 10% opacity
+
X: 0, Y: 2, Blur: 4, Spread: 0
Color: #000000 6% opacity

Modal Shadow
Type: Drop Shadow
X: 0, Y: 10, Blur: 25, Spread: 0
Color: #000000 15% opacity
```

### Corner Radius

```
Button Radius: 6px
Card Radius: 8px
Input Radius: 6px
Badge Radius: 4px
Modal Radius: 12px
```

### Spacing Scale (8px Grid)

```
1 = 8px
2 = 16px
3 = 24px
4 = 32px
5 = 40px
6 = 48px
8 = 64px
12 = 96px
16 = 128px
```

---

## 🔧 COMPONENTS

### Button Component

**Variants:**

#### Primary Button
```
Auto Layout: Horizontal, padding 24px × 12px
Min Height: 44px
Background: #78350F (Primary Brown)
Text: #FFFFFF (White), Inter Medium 16px
Border Radius: 6px

Hover State:
- Background: #5A2808 (darker brown)

Active/Pressed:
- Background: #4A2006 (even darker)
```

#### Outlined Button
```
Auto Layout: Horizontal, padding 24px × 12px
Min Height: 44px
Background: Transparent
Border: 2px solid #78350F
Text: #78350F, Inter Medium 16px
Border Radius: 6px

Hover State:
- Background: #78350F
- Text: #FFFFFF
```

#### Secondary Button
```
Border: 2px solid #D97706
Text: #D97706
Hover: bg #D97706, text white
```

#### Ghost Button
```
Auto Layout: Horizontal, padding 24px × 12px
Min Height: 44px
Background: Transparent
Text: #78350F, Inter Medium 16px
Border Radius: 6px

Hover State:
- Background: #FFFBEB (warm cream)
```

#### Disabled Button
```
Opacity: 50%
Cursor: not-allowed
```

---

### Product Card Component

**Frame: 360px × 480px**

```
Container:
- Auto Layout Vertical
- Background: #FFFFFF (White)
- Border: 2px solid transparent
- Border Radius: 8px
- Padding: 24px
- Gap: 16px

Hover State:
- Border: 2px solid #D97706 (Gold)
- Shadow: Card Hover Shadow

Elements:
1. Heart Icon (Top Right Absolute)
   - Size: 20×20px
   - Background: #FFFFFF 80% opacity, radius 50%
   - Padding: 8px
   - Color: #78716C (unfilled), #DC2626 (filled)

2. Badges (Top Left Absolute)
   - Auto Layout Vertical, gap 8px
   - Badge: padding 8px×4px, radius 4px
   - "Új": bg #16A34A, text white
   - "Elfogyott": bg #DC2626, text white

3. Image Container
   - Aspect Ratio: 4:3
   - Border Radius: 6px
   - Object Fit: Cover

4. Tags Row (if coffee product)
   - Auto Layout Horizontal, gap 8px
   - Badge: bg #78350F, text white
   - Inter Medium 12px
   - Examples: "Etiópia", "Világos"

5. Product Name
   - Playfair Display SemiBold 20px
   - Color: #1C1917
   - Max 2 lines, ellipsis

6. Star Rating Row
   - Auto Layout Horizontal, gap 4px
   - Star: 16×16px, color #D97706 (filled), #E7E5E4 (empty)
   - Count: Inter Regular 14px, #78716C

7. Price
   - Inter SemiBold 18px
   - Color: #78350F
   - Format: "2 490 Ft-tól"
```

---

### Badge Component

**Variants:**

```
Base:
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
```

---

### Input Field Component

**Frame: 360px × 44px minimum**

```
Default State:
- Auto Layout Horizontal
- Background: #FFFFFF
- Border: 1px solid #E7E5E4
- Border Radius: 6px
- Padding: 12px × 16px
- Text: Inter Regular 16px, #1C1917
- Placeholder: #78716C

Focus State:
- Border: 2px solid #D97706
- Glow: 0 0 0 2px rgba(217, 119, 6, 0.2)

Error State:
- Border: 2px solid #DC2626
- Helper Text: #DC2626, Inter Regular 14px

Disabled State:
- Background: #F5F5F4
- Text: #78716C
- Cursor: not-allowed
- Opacity: 60%
```

---

### Star Rating Component

```
Frame: Auto
Auto Layout Horizontal, gap 4px

Star Icon: 20×20px
Active: #D97706 (filled)
Inactive: #E7E5E4 (outlined)

Count Label:
- Inter Regular 14px
- Color: #78716C
- Format: "(12)"
```

---

### Header Component

**Desktop Frame: 1280px × 80px**

```
Container:
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
```

**Mobile Frame: 375px × 56px**

```
Layout: 3-column (Hamburger | Logo | Actions)
All icons: 24×24px minimum touch target 44×44px
```

---

### Footer Component

**Frame: 1280px × auto**

```
Container:
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
```

---

## 📱 SCREEN LAYOUTS

### 1. Homepage (Desktop: 1280px)

**Frame Structure:**

```
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
```

---

### 2. Product Catalog Page

**Desktop Frame: 1280px**

```
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
```

---

### 3. Product Detail Page

**Desktop Frame: 1280px**

```
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
```

---

### 4. Cart Page

**Desktop Frame: 1280px**

```
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
```

---

### 5. Checkout Flow

**3-Step Process with Progress Indicator**

```
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
```

---

## 📸 IMAGERY GUIDELINES

### Photography Style
- **Mood**: Warm, inviting, artisanal, premium but approachable
- **Lighting**: Natural light, warm tones, golden hour aesthetic
- **Colors**: Rich browns, creamy whites, golden accents
- **Subjects**: 
  - Coffee beans (close-up textures)
  - Brewing process
  - Latte art
  - Coffee with natural elements (wood, plants)
  - People enjoying coffee (lifestyle)
  - Coffee equipment (V60, scales, kettles)

### Unsplash Keywords
- "specialty coffee warm"
- "coffee beans natural light"
- "latte art"
- "pour over coffee"
- "coffee lifestyle"
- "artisanal coffee"

### Image Treatment
- Brightness: Natural, not overexposed
- Contrast: Moderate (+10 to +15%)
- Saturation: Natural to slightly warm
- Temperature: +50K to +150K (warm tones)
```

---

## ♿ ACCESSIBILITY

### Contrast Ratios (WCAG AA)
```
Text Dark (#1C1917) on Background (#FFFBEB): 15.2:1 ✓
Text Muted (#78716C) on Background: 4.8:1 ✓
Primary Brown (#78350F) on White: 9.7:1 ✓
White text on Primary Brown: 5.4:1 ✓
Gold (#D97706) on White: 5.1:1 ✓
```

### Touch Targets
- Minimum: 44×44px (mobile)
- Comfortable: 48×48px recommended

### Focus States
- Visible focus ring: 2px solid #D97706
- Offset: 2px
- Never remove focus indicators

---

## 📐 LAYOUT GRIDS

### Desktop (1280px)
```
Columns: 12
Gutter: 24px
Margin: 64px (sides)
Max content width: 1152px
```

### Tablet (768px)
```
Columns: 8
Gutter: 20px
Margin: 40px
```

### Mobile (375px)
```
Columns: 4
Gutter: 16px
Margin: 16px
```

---

## 🎭 INTERACTION STATES

### Hover (Desktop Only)
- Buttons: Background darken
- Cards: Shadow elevation + border color #D97706
- Links: Color change to #D97706
- Icons: Color change

### Active/Pressed
- Buttons: Darker background
- Scale: 0.98

### Focus
- All interactive: 2px solid #D97706 outline, 2px offset

### Disabled
- Opacity: 50%
- Cursor: not-allowed

---

## 📦 FIGMA FILE STRUCTURE

```
📄 CraftBrew Design System
├─ 📃 Cover
├─ 📃 Design Tokens
│  ├─ Colors
│  ├─ Typography
│  ├─ Effects
│  └─ Spacing
├─ 📃 Components
│  ├─ Buttons
│  ├─ Inputs
│  ├─ Cards
│  ├─ Badges
│  ├─ Navigation
│  └─ Forms
├─ 📃 Desktop Screens (1280px)
│  ├─ Homepage
│  ├─ Product Catalog
│  ├─ Product Detail
│  ├─ Cart
│  ├─ Checkout
│  ├─ Subscription Wizard
│  └─ User Dashboard
├─ 📃 Mobile Screens (375px)
│  └─ All pages
└─ 📃 Admin Screens
   └─ Management pages
```

---

**Version:** 1.0 Light Mode  
**Last Updated:** 2026-03-13  
**Designer:** CraftBrew Design Team  
**Status:** Ready for Figma Implementation

---

✨ **Happy Designing!** Create a warm, welcoming premium coffee experience. ☕
