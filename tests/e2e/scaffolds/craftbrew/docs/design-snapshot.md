# Design Snapshot

File key: DDCs2kpcLYw6E3Q1EcDjCK
Type: make

## Pages & Frames

*Make file (file key: DDCs2kpcLYw6E3Q1EcDjCK)*

## Design Tokens

### Colors (from Tailwind classes)
- `bg-black/50` (×7)
- `bg-gray-200` (×2)
- `bg-green-100` (×1)
- `bg-green-50` (×2)
- `bg-white` (×74)
- `bg-white/80` (×1)
- `text-white` (×19)
### Typography
- `font-bold` (×16)
- `font-medium` (×105)
- `font-mono` (×2)
- `font-semibold` (×105)
- `text-2xl` (×7)
- `text-3xl` (×3)
- `text-lg` (×9)
- `text-sm` (×85)
- `text-xl` (×9)
- `text-xs` (×21)
### Spacing
- `gap-1` (×4)
- `gap-12` (×2)
- `gap-2` (×36)
- `gap-3` (×17)
- `gap-4` (×39)
- `gap-6` (×12)
- `gap-8` (×9)
- `mb-1` (×9)
- `mb-12` (×5)
- `mb-16` (×4)
- `mb-2` (×100)
- `mb-3` (×22)
- `mb-4` (×37)
- `mb-6` (×48)
- `mb-8` (×35)
- `ml-1` (×3)
- `ml-2` (×4)
- `ml-8` (×1)
- `ml-auto` (×1)
- `mr-1` (×1)
- `mr-2` (×6)
- `mr-3` (×1)
- `mt-1` (×9)
- `mt-16` (×1)
- `mt-2` (×7)
- `mt-3` (×1)
- `mt-4` (×4)
- `mt-6` (×6)
- `mt-8` (×3)
- `mx-4` (×1)
- `mx-auto` (×42)
- `p-1` (×1)
- `p-2` (×17)
- `p-3` (×16)
- `p-4` (×160)
- `p-6` (×60)
- `p-8` (×5)
- `pb-2` (×2)
- `pb-3` (×7)
- `pb-4` (×3)
- `pb-6` (×2)
- `pl-10` (×2)
- `pl-4` (×1)
- `pl-6` (×4)
- `pr-10` (×1)
- `pr-12` (×3)
- `pr-4` (×2)
- `pt-2` (×1)
- `pt-3` (×4)
- `pt-4` (×2)
- `pt-6` (×2)
- `pt-8` (×1)
- `px-2` (×4)
- `px-3` (×13)
- `px-4` (×109)
- `px-6` (×7)
- `py-0.5` (×1)
- `py-1` (×17)
- `py-12` (×6)
- `py-16` (×6)
- `py-2` (×68)
- `py-3` (×29)
- `py-4` (×10)
- `py-8` (×8)
- `space-y-1` (×4)
- `space-y-2` (×4)
- `space-y-3` (×8)
- `space-y-4` (×11)
- `space-y-6` (×12)
### Borders & Radius
- `border` (×107)
- `border-2` (×2)
- `border-[--color-border]` (×181)
- `border-[--color-secondary]` (×2)
- `border-[--color-warning]` (×2)
- `border-b` (×48)
- `border-green-200` (×2)
- `border-l` (×4)
- `border-l-2` (×1)
- `border-l-4` (×3)
- `border-r` (×1)
- `border-t` (×19)
- `border-transparent` (×1)
- `rounded` (×30)
- `rounded-[8px]` (×1)
- `rounded-full` (×20)
- `rounded-lg` (×102)
- `rounded-md` (×66)
### Shadows
- `shadow-lg` (×3)
- `shadow-md` (×2)
- `shadow-sm` (×24)
- `shadow-xl` (×1)

## Component Hierarchy

This contains the resource links for all the source files in the Figma Make. Start with App.tsx to understand the code.

## Source Files

### ATTRIBUTIONS.md
```
This Figma Make file includes components from [shadcn/ui](https://ui.shadcn.com/) used under [MIT license](https://github.com/shadcn-ui/ui/blob/main/LICENSE.md).

This Figma Make file includes photos from [Unsplash](https://unsplash.com) used under [license](https://unsplash.com/license).

```

### craftbrew-design-system.json
```
{
  "name": "CraftBrew Design System",
  "version": "1.0.0",
  "description": "Comprehensive design system for CraftBrew premium specialty coffee e-commerce platform",
  "language": "hu",
  "brand": {
    "name": "CraftBrew",
    "tagline": "Specialty Coffee Budapest",
    "description": "Warm, artisanal, light mode with cream tones. Premium specialty coffee experience with inviting, natural aesthetic.",
    "personality": [
      "Premium quality",
      "Artisanal craftsmanship",
      "Warm and inviting",
      "Community-focused",
      "Expert knowledge"
    ]
  },
  "designTokens": {
    "colors": {
      "primary": {
        "value": "#78350F",
        "name": "Coffee Brown",
        "usage": "Buttons, CTAs, primary actions, logo, brand color"
      },
      "secondary": {
        "value": "#D97706",
        "name": "Gold Accent",
        "usage": "Hover states, links, accents, highlights, focus states"
      },
      "background": {
        "value": "#FFFBEB",
        "name": "Warm Cream",
        "usage": "Page background, app background, main canvas"
      },
      "surface": {
        "value": "#FFFFFF",
        "name": "White Surface",
        "usage": "Cards, panels, modals, header, product cards"
      },
      "surfaceElevated": {
        "value": "#F5F1E6",
        "name": "Light Cream",
        "usage": "Footer, alternate sections, subtle backgrounds"
      },
      "text": {
        "value": "#1C1917",
        "name": "Dark Text",
        "usage": "Main text, headings, primary content"
      },
      "textSecondary": {
        "value": "#78716C",
        "name": "Muted Text",
        "usage": "Secondary text, descriptions, captions, placeholders"
      },
      "muted": {
        "value": "#78716C",
        "name": "Muted Gray",
        "usage": "Placeholders, disabled states, subtle text"
      },
      "border": {
        "value": "#E7E5E4",
        "name": "Light Border",
        "usage": "Borders, dividers, separators, card outlines"
      },
      "borderLight": {
        "value": "#E7E5E4",
        "name": "Light Border",
        "usage": "Same as border for consistency"
      },
      "success": {
        "value": "#16A34A",
        "name": "Green",
        "usage": "In-stock badges, success states, confirmations"
      },
      "warning": {
        "value": "#D97706",
        "name": "Amber",
        "usage": "Low stock badges, warnings"
      },
      "error": {
        "value": "#DC2626",
        "name": "Red",
        "usage": "Out of stock, error states, destructive actions"
      },
      "accent": {
        "value": "#D97706",
        "name": "Gold Accent",
        "usage": "Interactive elements, highlights"
      },
      "highlight": {
        "value": "#78350F",
        "name": "Coffee Brown",
        "usage": "Special emphasis, primary highlights"
      }
    },
    "typography": {
      "fontFamilies": {
        "heading": {
          "value": "'Playfair Display', serif",
          "usage": "Headings (h1-h3), logo, titles"
        },
        "body": {
          "value": "'Inter', sans-serif",
          "usage": "Body text, UI elements, buttons"
        },
        "mono": {
          "value": "'JetBrains Mono', monospace",
          "usage": "Order numbers, codes, technical data"
        }
      },
      "fontSizes": {
        "h1": {
          "value": "40px",
          "weight": "700",
          "lineHeight": "1.2"
        },
        "h2": {
          "value": "32px",
          "weight": "600",
          "lineHeight": "1.3"
        },
        "h3": {
          "value": "24px",
          "weight": "600",
          "lineHeight": "1.4"
        },
        "base": {
          "value": "16px",
          "weight": "400",
          "lineHeight": "1.6"
        },
        "small": {
          "value": "14px",
          "weight": "400",
          "lineHeight": "1.5"
        },
        "caption": {
          "value": "12px",
          "weight": "400",
          "lineHeight": "1.4"
        }
      }
    },
    "spacing": {
      "base": "8px",
      "card": "24px",
      "gridDesktop": "24px",
      "gridMobile": "16px",
      "containerMax": "1280px",
      "scale": {
        "1": "8px",
        "2": "16px",
        "3": "24px",
        "4": "32px",
        "5": "40px",
        "6": "48px",
        "8": "64px",
        "12": "96px",
        "16": "128px"
      }
    },
    "borderRadius": {
      "button": "6px",
      "card": "8px",
      "input": "6px",
      "badge": "4px"
    },
    "shadows": {
      "card": "0 1px 3px rgba(0, 0, 0, 0.1), 0 1px 2px rgba(0, 0, 0, 0.06)",
      "cardHover": "0 4px 6px rgba(0, 0, 0, 0.1), 0 2px 4px rgba(0, 0, 0, 0.06)",
      "modal": "0 10px 25px rgba(0, 0, 0, 0.15)"
    },
    "breakpoints": {
      "mobile": "375px",
      "tablet": "768px",
      "desktop": "1280px",
      "wide": "1536px"
    }
  },
  "components": {
    "button": {
      "variants": {
        "primary": {
          "background": "#78350F",
          "color": "#FFFFFF",
    
... (18637 chars truncated)
```

### craftbrew-figma-design-spec.md
```
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
   - Back
... (10873 chars truncated)
```

### guidelines/Guidelines.md
```
**Add your own guidelines here**
<!--

System Guidelines

Use this file to provide the AI with rules and guidelines you want it to follow.
This template outlines a few examples of things you can add. You can add your own sections and format it to suit your needs

TIP: More context isn't always better. It can confuse the LLM. Try and add the most important rules you need

# General guidelines

Any general rules you want the AI to follow.
For example:

* Only use absolute positioning when necessary. Opt for responsive and well structured layouts that use flexbox and grid by default
* Refactor code as you go to keep code clean
* Keep file sizes small and put helper functions and components in their own files.

--------------

# Design system guidelines
Rules for how the AI should make generations look like your company's design system

Additionally, if you select a design system to use in the prompt box, you can reference
your design system's components, tokens, variables and components.
For example:

* Use a base font-size of 14px
* Date formats should always be in the format “Jun 10”
* The bottom toolbar should only ever have a maximum of 4 items
* Never use the floating action button with the bottom toolbar
* Chips should always come in sets of 3 or more
* Don't use a dropdown if there are 2 or fewer options

You can also create sub sections and add more specific details
For example:


## Button
The Button component is a fundamental interactive element in our design system, designed to trigger actions or navigate
users through the application. It provides visual feedback and clear affordances to enhance user experience.

### Usage
Buttons should be used for important actions that users need to take, such as form submissions, confirming choices,
or initiating processes. They communicate interactivity and should have clear, action-oriented labels.

### Variants
* Primary Button
  * Purpose : Used for the main action in a section or page
  * Visual Style : Bold, filled with the primary brand color
  * Usage : One primary button per section to guide users toward the most important action
* Secondary Button
  * Purpose : Used for alternative or supporting actions
  * Visual Style : Outlined with the primary color, transparent background
  * Usage : Can appear alongside a primary button for less important actions
* Tertiary Button
  * Purpose : Used for the least important actions
  * Visual Style : Text-only with no border, using primary color
  * Usage : For actions that should be available but not emphasized
-->

```

### package.json
```
{
  "name": "@figma/my-make-file",
  "private": true,
  "version": "0.0.1",
  "type": "module",
  "scripts": {
    "build": "vite build"
  },
  "dependencies": {
    "@emotion/react": "11.14.0",
    "@emotion/styled": "11.14.1",
    "@mui/icons-material": "7.3.5",
    "@mui/material": "7.3.5",
    "@popperjs/core": "2.11.8",
    "@radix-ui/react-accordion": "1.2.3",
    "@radix-ui/react-alert-dialog": "1.1.6",
    "@radix-ui/react-aspect-ratio": "1.1.2",
    "@radix-ui/react-avatar": "1.1.3",
    "@radix-ui/react-checkbox": "1.1.4",
    "@radix-ui/react-collapsible": "1.1.3",
    "@radix-ui/react-context-menu": "2.2.6",
    "@radix-ui/react-dialog": "1.1.6",
    "@radix-ui/react-dropdown-menu": "2.1.6",
    "@radix-ui/react-hover-card": "1.1.6",
    "@radix-ui/react-label": "2.1.2",
    "@radix-ui/react-menubar": "1.1.6",
    "@radix-ui/react-navigation-menu": "1.2.5",
    "@radix-ui/react-popover": "1.1.6",
    "@radix-ui/react-progress": "1.1.2",
    "@radix-ui/react-radio-group": "1.2.3",
    "@radix-ui/react-scroll-area": "1.2.3",
    "@radix-ui/react-select": "2.1.6",
    "@radix-ui/react-separator": "1.1.2",
    "@radix-ui/react-slider": "1.2.3",
    "@radix-ui/react-slot": "1.1.2",
    "@radix-ui/react-switch": "1.1.3",
    "@radix-ui/react-tabs": "1.1.3",
    "@radix-ui/react-toggle-group": "1.1.2",
    "@radix-ui/react-toggle": "1.1.2",
    "@radix-ui/react-tooltip": "1.1.8",
    "canvas-confetti": "1.9.4",
    "class-variance-authority": "0.7.1",
    "clsx": "2.1.1",
    "cmdk": "1.1.1",
    "date-fns": "3.6.0",
    "embla-carousel-react": "8.6.0",
    "input-otp": "1.4.2",
    "lucide-react": "0.487.0",
    "motion": "12.23.24",
    "next-themes": "0.4.6",
    "react-day-picker": "8.10.1",
    "react-dnd": "16.0.1",
    "react-dnd-html5-backend": "16.0.1",
    "react-hook-form": "7.55.0",
    "react-popper": "2.3.0",
    "react-resizable-panels": "2.1.7",
    "react-responsive-masonry": "2.7.1",
    "react-router": "7.13.0",
    "react-slick": "0.31.0",
    "recharts": "2.15.2",
    "sonner": "2.0.3",
    "tailwind-merge": "3.2.0",
    "tw-animate-css": "1.3.8",
    "vaul": "1.1.2"
  },
  "devDependencies": {
    "@tailwindcss/vite": "4.1.12",
    "@vitejs/plugin-react": "4.7.0",
    "tailwindcss": "4.1.12",
    "vite": "6.3.5"
  },
  "peerDependencies": {
    "react": "18.3.1",
    "react-dom": "18.3.1"
  },
  "peerDependenciesMeta": {
    "react": {
      "optional": true
    },
    "react-dom": {
      "optional": true
    }
  },
  "pnpm": {
    "overrides": {
      "vite": "6.3.5"
    }
  }
}

```

### postcss.config.mjs
```
/**
 * PostCSS Configuration
 *
 * Tailwind CSS v4 (via @tailwindcss/vite) automatically sets up all required
 * PostCSS plugins — you do NOT need to include `tailwindcss` or `autoprefixer` here.
 *
 * This file only exists for adding additional PostCSS plugins, if needed.
 * For example:
 *
 * import postcssNested from 'postcss-nested'
 * export default { plugins: [postcssNested()] }
 *
 * Otherwise, you can leave this file empty.
 */
export default {}

```

### src/app/App.tsx
```
import { RouterProvider } from 'react-router';
import { router } from './routes';
import { Toaster } from 'sonner';

function App() {
  return (
    <>
      <RouterProvider router={router} />
      <Toaster position="top-right" />
    </>
  );
}

export default App;

```

### src/app/components/Badge.tsx
```
import { cn } from '../../lib/utils';

interface BadgeProps {
  variant: 'new' | 'outOfStock' | 'lowStock' | 'discount' | 'category' | 'status';
  children: React.ReactNode;
  className?: string;
}

export function Badge({ variant = 'category', className, children }: BadgeProps) {
  return (
    <span
      className={cn(
        'inline-flex items-center px-2.5 py-0.5 rounded text-xs font-medium',
        {
          'bg-[--color-success] text-white': variant === 'new',
          'bg-[--color-error] text-white': variant === 'outOfStock',
          'bg-[--color-warning] text-white': variant === 'lowStock' || variant === 'discount',
          'bg-[--color-primary] text-white': variant === 'category',
          'bg-[--color-muted] text-white': variant === 'status',
        },
        className
      )}
    >
      {children}
    </span>
  );
}
```

### src/app/components/Button.tsx
```
import { ButtonHTMLAttributes, forwardRef } from 'react';
import { cn } from '../../lib/utils';

interface ButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: 'primary' | 'secondary' | 'ghost' | 'outlined';
  fullWidth?: boolean;
}

export const Button = forwardRef<HTMLButtonElement, ButtonProps>(
  ({ className, variant = 'primary', fullWidth, children, disabled, ...props }, ref) => {
    return (
      <button
        ref={ref}
        disabled={disabled}
        className={cn(
          'min-h-[44px] px-6 py-3 rounded-[6px] transition-all duration-200 font-medium',
          {
            'bg-[--color-primary] text-white hover:bg-[#5a2808] active:bg-[#4a2006]': variant === 'primary' && !disabled,
            'border-2 border-[--color-primary] text-[--color-primary] hover:bg-[--color-primary] hover:text-white': variant === 'outlined' && !disabled,
            'border-2 border-[--color-secondary] text-[--color-secondary] hover:bg-[--color-secondary] hover:text-white': variant === 'secondary' && !disabled,
            'text-[--color-primary] hover:bg-[--color-background]': variant === 'ghost' && !disabled,
            'opacity-50 cursor-not-allowed': disabled,
            'w-full': fullWidth,
          },
          className
        )}
        {...props}
      >
        {children}
      </button>
    );
  }
);

Button.displayName = 'Button';
```

### src/app/components/Footer.tsx
```
import { Link } from 'react-router';
import { Facebook, Instagram } from 'lucide-react';

export function Footer() {
  return (
    <footer className="bg-[#F5F1E6] border-t border-[--color-border] mt-16">
      <div className="max-w-[--container-max] mx-auto px-4 sm:px-6 py-12">
        <div className="grid grid-cols-1 md:grid-cols-3 gap-8">
          {/* Column 1 */}
          <div>
            <h3 className="text-2xl mb-4" style={{ fontFamily: 'var(--font-heading)', color: 'var(--color-primary)' }}>
              CraftBrew
            </h3>
            <p className="text-[--color-muted] mb-4">Specialty Coffee Budapest</p>
            <p className="text-sm text-[--color-muted]">© 2026 CraftBrew</p>
          </div>

          {/* Column 2 */}
          <div>
            <h4 className="font-semibold mb-4">Linkek</h4>
            <ul className="space-y-2">
              <li>
                <Link to="/kavek" className="text-[--color-muted] hover:text-[--color-secondary] transition-colors">
                  Kávék
                </Link>
              </li>
              <li>
                <Link to="/eszkozok" className="text-[--color-muted] hover:text-[--color-secondary] transition-colors">
                  Eszközök
                </Link>
              </li>
              <li>
                <Link to="/sztorik" className="text-[--color-muted] hover:text-[--color-secondary] transition-colors">
                  Sztorik
                </Link>
              </li>
              <li>
                <Link to="/elofizetés" className="text-[--color-muted] hover:text-[--color-secondary] transition-colors">
                  Előfizetés
                </Link>
              </li>
            </ul>
          </div>

          {/* Column 3 */}
          <div>
            <h4 className="font-semibold mb-4">Kapcsolat</h4>
            <p className="text-[--color-muted] mb-2">
              <a href="mailto:hello@craftbrew.hu" className="hover:text-[--color-secondary] transition-colors">
                hello@craftbrew.hu
              </a>
            </p>
            <p className="text-[--color-muted] mb-4">
              CraftBrew Labor<br />
              Kazinczy u. 28<br />
              1075 Budapest
            </p>
            <div className="flex gap-3">
              <a
                href="https://facebook.com"
                target="_blank"
                rel="noopener noreferrer"
                className="p-2 bg-white rounded-full hover:bg-[--color-secondary] hover:text-white transition-colors"
              >
                <Facebook className="w-5 h-5" />
              </a>
              <a
                href="https://instagram.com"
                target="_blank"
                rel="noopener noreferrer"
                className="p-2 bg-white rounded-full hover:bg-[--color-secondary] hover:text-white transition-colors"
              >
                <Instagram className="w-5 h-5" />
              </a>
            </div>
          </div>
        </div>
      </div>
    </footer>
  );
}
```

### src/app/components/Header.tsx
```
import { useState } from 'react';
import { Link } from 'react-router';
import { Search, ShoppingCart, Menu, X, User } from 'lucide-react';

export function Header() {
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false);
  const [cartCount] = useState(3);

  return (
    <>
      {/* Desktop Header */}
      <header className="sticky top-0 z-50 bg-white border-b border-[--color-border] shadow-sm">
        <div className="max-w-[--container-max] mx-auto px-4 sm:px-6">
          {/* Desktop */}
          <div className="hidden md:flex items-center justify-between h-20">
            {/* Logo */}
            <Link to="/" className="text-2xl font-bold" style={{ fontFamily: 'var(--font-heading)', color: 'var(--color-primary)' }}>
              CraftBrew
            </Link>

            {/* Navigation */}
            <nav className="flex items-center gap-8">
              <Link to="/kavek" className="hover:text-[--color-secondary] transition-colors">
                Kávék
              </Link>
              <Link to="/eszkozok" className="hover:text-[--color-secondary] transition-colors">
                Eszközök
              </Link>
              <Link to="/sztorik" className="hover:text-[--color-secondary] transition-colors">
                Sztorik
              </Link>
              <Link to="/elofizetés" className="hover:text-[--color-secondary] transition-colors">
                Előfizetés
              </Link>
            </nav>

            {/* Right Icons */}
            <div className="flex items-center gap-4">
              <button className="p-2 hover:text-[--color-secondary] transition-colors">
                <Search className="w-5 h-5" />
              </button>
              <Link to="/kosar" className="relative p-2 hover:text-[--color-secondary] transition-colors">
                <ShoppingCart className="w-5 h-5" />
                {cartCount > 0 && (
                  <span className="absolute -top-1 -right-1 bg-[--color-error] text-white text-xs rounded-full w-5 h-5 flex items-center justify-center">
                    {cartCount}
                  </span>
                )}
              </Link>
              <button className="px-3 py-1 text-sm hover:text-[--color-secondary] transition-colors">
                EN
              </button>
              <Link to="/fiokom" className="p-2 hover:text-[--color-secondary] transition-colors">
                <User className="w-5 h-5" />
              </Link>
            </div>
          </div>

          {/* Mobile */}
          <div className="md:hidden flex items-center justify-between h-14">
            <button onClick={() => setMobileMenuOpen(true)} className="p-2">
              <Menu className="w-6 h-6" />
            </button>
            <Link to="/" className="text-xl font-bold" style={{ fontFamily: 'var(--font-heading)', color: 'var(--color-primary)' }}>
              CraftBrew
            </Link>
            <div className="flex items-center gap-2">
              <button className="p-2">
                <Search className="w-5 h-5" />
              </button>
              <Link to="/kosar" className="relative p-2">
                <ShoppingCart className="w-5 h-5" />
                {cartCount > 0 && (
                  <span className="absolute -top-1 -right-1 bg-[--color-error] text-white text-xs rounded-full w-5 h-5 flex items-center justify-center">
                    {cartCount}
                  </span>
                )}
              </Link>
            </div>
          </div>
        </div>
      </header>

      {/* Mobile Menu Drawer */}
      {mobileMenuOpen && (
        <div className="fixed inset-0 z-50 md:hidden">
          <div className="absolute inset-0 bg-black/50" onClick={() => setMobileMenuOpen(false)} />
          <div className="absolute left-0 top-0 bottom-0 w-80 max-w-[85vw] bg-white shadow-xl">
            <div className="p-4 border-b border-[--color-border]">
              <button onClick={() => setMobileMenuOpen(false)} className="p-2">
                <X className="w-6 h-6" />
              </button>
            </div>
            <nav className="flex flex-col">
              <Link
                to="/kavek"
                className="px-6 py-4 hover:bg-[--color-background] transition-colors border-b border-[--color-border]"
                onClick={() => setMobileMenuOpen(false)}
              >
                Kávék
              </Link>
              <Link
                to="/eszkozok"
                className="px-6 py-4 hover:bg-[--color-background] transition-colors border-b border-[--color-border]"
                onClick={() => setMobileMenuOpen(false)}
              >
                Eszközök
              </Link>
              <Link
                to="/sztorik"
                className="px-6 py-4 hover:bg-[--color-background] transition-colors border-b border-[--color-border]"
                onClick={() => setMobileMenuOpen(false)}
              >
                Sztorik
             
... (1118 chars truncated)
```

### src/app/components/Layout.tsx
```
import { Outlet } from 'react-router';
import { Header } from './Header';
import { Footer } from './Footer';
import { PromoBanner } from './PromoBanner';

export default function Layout() {
  return (
    <div className="min-h-screen flex flex-col">
      <PromoBanner />
      <Header />
      <main className="flex-1">
        <Outlet />
      </main>
      <Footer />
    </div>
  );
}
```

### src/app/components/ProductCard.tsx
```
import { Heart } from 'lucide-react';
import { useState } from 'react';
import { Link } from 'react-router';
import { Badge } from './Badge';
import { StarRating } from './StarRating';
import { formatPrice } from '../../lib/utils';
import { ImageWithFallback } from './figma/ImageWithFallback';

interface ProductCardProps {
  id: string;
  name: string;
  image: string;
  price: number;
  rating?: number;
  reviewCount?: number;
  isNew?: boolean;
  isOutOfStock?: boolean;
  origin?: string;
  roast?: string;
}

export function ProductCard({
  id,
  name,
  image,
  price,
  rating = 5,
  reviewCount = 0,
  isNew,
  isOutOfStock,
  origin,
  roast,
}: ProductCardProps) {
  const [isFavorite, setIsFavorite] = useState(false);

  return (
    <div className="bg-white rounded-[8px] p-6 relative group hover:shadow-lg hover:border-[--color-secondary] border-2 border-transparent transition-all duration-200">
      {/* Heart Icon */}
      <button
        onClick={(e) => {
          e.preventDefault();
          setIsFavorite(!isFavorite);
        }}
        className="absolute top-4 right-4 z-10 p-2 rounded-full bg-white/80 hover:bg-white transition-colors"
      >
        <Heart
          className={`w-5 h-5 ${
            isFavorite ? 'fill-[--color-error] text-[--color-error]' : 'text-[--color-muted]'
          }`}
        />
      </button>

      {/* Badges */}
      <div className="absolute top-4 left-4 z-10 flex flex-col gap-2">
        {isNew && <Badge variant="new">Új</Badge>}
        {isOutOfStock && <Badge variant="outOfStock">Elfogyott</Badge>}
      </div>

      <Link to={`/kavek/${id}`} className="block">
        {/* Image */}
        <div className="aspect-[4/3] mb-4 overflow-hidden rounded">
          <ImageWithFallback
            src={image}
            alt={name}
            className="w-full h-full object-cover group-hover:scale-105 transition-transform duration-300"
          />
        </div>

        {/* Tags */}
        {(origin || roast) && (
          <div className="flex gap-2 mb-2">
            {origin && <Badge variant="category">{origin}</Badge>}
            {roast && <Badge variant="category">{roast}</Badge>}
          </div>
        )}

        {/* Name */}
        <h3 className="text-xl mb-2">{name}</h3>

        {/* Rating */}
        <div className="mb-3">
          <StarRating rating={rating} count={reviewCount} />
        </div>

        {/* Price */}
        <p className="text-lg font-semibold text-[--color-primary]">
          {formatPrice(price)}-tól
        </p>
      </Link>
    </div>
  );
}
```

### src/app/components/PromoBanner.tsx
```
import { X } from 'lucide-react';
import { useState } from 'react';

export function PromoBanner() {
  const [isVisible, setIsVisible] = useState(true);

  if (!isVisible) return null;

  return (
    <div className="bg-[--color-secondary] text-white py-3 px-4 relative">
      <div className="max-w-[--container-max] mx-auto text-center">
        <p className="font-medium">
          🎉 A CraftBrew 1 éves! 20% kedvezmény mindenből!
        </p>
      </div>
      <button
        onClick={() => setIsVisible(false)}
        className="absolute right-4 top-1/2 -translate-y-1/2 p-1 hover:bg-white/20 rounded"
      >
        <X className="w-5 h-5" />
      </button>
    </div>
  );
}

```

### src/app/components/StarRating.tsx
```
import { Star } from 'lucide-react';
import { cn } from '../../lib/utils';

interface StarRatingProps {
  rating: number;
  count?: number;
  size?: 'sm' | 'md' | 'lg';
  interactive?: boolean;
  onRate?: (rating: number) => void;
}

export function StarRating({ rating, count, size = 'md', interactive = false, onRate }: StarRatingProps) {
  const sizeClasses = {
    sm: 'w-3 h-3',
    md: 'w-4 h-4',
    lg: 'w-5 h-5',
  };

  const handleClick = (index: number) => {
    if (interactive && onRate) {
      onRate(index + 1);
    }
  };

  return (
    <div className="flex items-center gap-1">
      {[0, 1, 2, 3, 4].map((index) => (
        <Star
          key={index}
          className={cn(
            sizeClasses[size],
            index < rating ? 'fill-[--color-secondary] text-[--color-secondary]' : 'text-[--color-border]',
            interactive && 'cursor-pointer hover:scale-110 transition-transform'
          )}
          onClick={() => handleClick(index)}
        />
      ))}
      {count !== undefined && (
        <span className="ml-1 text-sm text-[--color-muted]">({count})</span>
      )}
    </div>
  );
}

```

### src/app/components/figma/ImageWithFallback.tsx
```
import React, { useState } from 'react'

const ERROR_IMG_SRC =
  'data:image/svg+xml;base64,PHN2ZyB3aWR0aD0iODgiIGhlaWdodD0iODgiIHhtbG5zPSJodHRwOi8vd3d3LnczLm9yZy8yMDAwL3N2ZyIgc3Ryb2tlPSIjMDAwIiBzdHJva2UtbGluZWpvaW49InJvdW5kIiBvcGFjaXR5PSIuMyIgZmlsbD0ibm9uZSIgc3Ryb2tlLXdpZHRoPSIzLjciPjxyZWN0IHg9IjE2IiB5PSIxNiIgd2lkdGg9IjU2IiBoZWlnaHQ9IjU2IiByeD0iNiIvPjxwYXRoIGQ9Im0xNiA1OCAxNi0xOCAzMiAzMiIvPjxjaXJjbGUgY3g9IjUzIiBjeT0iMzUiIHI9IjciLz48L3N2Zz4KCg=='

export function ImageWithFallback(props: React.ImgHTMLAttributes<HTMLImageElement>) {
  const [didError, setDidError] = useState(false)

  const handleError = () => {
    setDidError(true)
  }

  const { src, alt, style, className, ...rest } = props

  return didError ? (
    <div
      className={`inline-block bg-gray-100 text-center align-middle ${className ?? ''}`}
      style={style}
    >
      <div className="flex items-center justify-center w-full h-full">
        <img src={ERROR_IMG_SRC} alt="Error loading image" {...rest} data-original-url={src} />
      </div>
    </div>
  ) : (
    <img src={src} alt={alt} className={className} style={style} {...rest} onError={handleError} />
  )
}

```

### src/app/pages/AdminDashboard.tsx
```
import { Routes, Route, Link, useLocation } from 'react-router';
import { LayoutDashboard, Package, ShoppingCart, Truck, Calendar, Tag, Gift, Star, Megaphone, FileText } from 'lucide-react';
import { BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer } from 'recharts';
import { formatPrice } from '../../lib/utils';

function Overview() {
  const chartData = [
    { date: '03-06', revenue: 156000 },
    { date: '03-07', revenue: 189000 },
    { date: '03-08', revenue: 145000 },
    { date: '03-09', revenue: 223000 },
    { date: '03-10', revenue: 198000 },
    { date: '03-11', revenue: 267000 },
    { date: '03-12', revenue: 234500 },
  ];

  return (
    <div className="space-y-6">
      {/* KPI Cards */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-6">
        <div className="bg-white rounded-lg p-6 shadow-sm">
          <div className="flex items-center justify-between mb-2">
            <span className="text-sm text-[--color-muted]">Mai bevétel</span>
            <span className="text-xs text-[--color-success]">+12%</span>
          </div>
          <p className="text-2xl font-bold text-[--color-primary]">234 500 Ft</p>
        </div>
        <div className="bg-white rounded-lg p-6 shadow-sm">
          <div className="flex items-center justify-between mb-2">
            <span className="text-sm text-[--color-muted]">Mai rendelések</span>
            <span className="text-xs text-[--color-success]">+3</span>
          </div>
          <p className="text-2xl font-bold text-[--color-primary]">8</p>
        </div>
        <div className="bg-white rounded-lg p-6 shadow-sm">
          <div className="flex items-center justify-between mb-2">
            <span className="text-sm text-[--color-muted]">Aktív előfizetők</span>
            <span className="text-xs text-[--color-success]">+2</span>
          </div>
          <p className="text-2xl font-bold text-[--color-primary]">23</p>
        </div>
        <div className="bg-white rounded-lg p-6 shadow-sm">
          <div className="flex items-center justify-between mb-2">
            <span className="text-sm text-[--color-muted]">Új regisztrációk (7 nap)</span>
            <span className="text-xs text-[--color-error]">-5%</span>
          </div>
          <p className="text-2xl font-bold text-[--color-primary]">15</p>
        </div>
      </div>

      {/* Revenue Chart */}
      <div className="bg-white rounded-lg p-6 shadow-sm">
        <h3 className="text-lg font-semibold mb-6">Bevétel (7 nap)</h3>
        <ResponsiveContainer width="100%" height={300}>
          <BarChart data={chartData}>
            <CartesianGrid strokeDasharray="3 3" stroke="#E7E5E4" />
            <XAxis dataKey="date" stroke="#78716C" />
            <YAxis stroke="#78716C" />
            <Tooltip formatter={(value) => `${formatPrice(value as number)}`} />
            <Bar dataKey="revenue" fill="#D97706" radius={[4, 4, 0, 0]} />
          </BarChart>
        </ResponsiveContainer>
      </div>

      {/* Top Products & Low Stock */}
      <div className="grid md:grid-cols-2 gap-6">
        <div className="bg-white rounded-lg p-6 shadow-sm">
          <h3 className="text-lg font-semibold mb-4">Top termékek ma</h3>
          <div className="space-y-3">
            <div className="flex justify-between items-center pb-3 border-b border-[--color-border]">
              <span>#1 Ethiopia Yirgacheffe</span>
              <span className="font-semibold">12 db</span>
            </div>
            <div className="flex justify-between items-center pb-3 border-b border-[--color-border]">
              <span>#2 Starter Bundle</span>
              <span className="font-semibold">5 db</span>
            </div>
            <div className="flex justify-between items-center">
              <span>#3 Colombia Huila</span>
              <span className="font-semibold">4 db</span>
            </div>
          </div>
        </div>

        <div className="bg-white rounded-lg p-6 shadow-sm">
          <h3 className="text-lg font-semibold mb-4">Alacsony készlet ⚠️</h3>
          <div className="space-y-3">
            <div className="p-3 border-l-4 border-[--color-warning] bg-amber-50 rounded">
              <p className="font-medium">Fellow Stagg EKG Kettle</p>
              <p className="text-sm text-[--color-muted]">8 db</p>
            </div>
            <div className="p-3 border-l-4 border-[--color-warning] bg-amber-50 rounded">
              <p className="font-medium">Rwanda Nyungwe 1kg</p>
              <p className="text-sm text-[--color-muted]">5 db</p>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

function Products() {
  return (
    <div className="bg-white rounded-lg p-6">
      <h2 className="mb-6">Termékek kezelése</h2>
      <p className="text-[--color-muted]">Termék kezelési funkciók itt jelennek meg...</p>
    </div>
  );
}

export default function AdminDashboard() {
  const location = useLocation();
  
... (2476 chars truncated)
```

### src/app/pages/Cart.tsx
```
import { useState } from 'react';
import { Link } from 'react-router';
import { Trash2, Minus, Plus, ShoppingBag } from 'lucide-react';
import { Button } from '../components/Button';
import { ImageWithFallback } from '../components/figma/ImageWithFallback';
import { formatPrice } from '../../lib/utils';

export default function Cart() {
  const [cartItems, setCartItems] = useState([
    {
      id: '1',
      productId: 'ethiopia-yirgacheffe',
      name: 'Ethiopia Yirgacheffe',
      variant: 'Szemes, 500g',
      image: 'https://images.unsplash.com/photo-1772391264887-50a9e650e0fd?w=200',
      price: 4680,
      quantity: 2,
    },
    {
      id: '2',
      productId: 'colombia-huila',
      name: 'Colombia Huila',
      variant: 'Őrölt (filter), 250g',
      image: 'https://images.unsplash.com/photo-1772141614991-eea2a95e770c?w=200',
      price: 2790,
      quantity: 1,
    },
    {
      id: '3',
      productId: 'v60-dripper',
      name: 'Hario V60 Dripper',
      variant: 'Fehér',
      image: 'https://images.unsplash.com/photo-1550559256-32644b7a2993?w=200',
      price: 3990,
      quantity: 1,
    },
  ]);

  const [couponCode, setCouponCode] = useState('');
  const [appliedCoupon, setAppliedCoupon] = useState<{ code: string; discount: number } | null>(null);
  const [giftCardCode, setGiftCardCode] = useState('');
  const [appliedGiftCard, setAppliedGiftCard] = useState<{ code: string; amount: number } | null>(null);

  const updateQuantity = (id: string, newQuantity: number) => {
    if (newQuantity < 1) return;
    setCartItems(cartItems.map((item) => (item.id === id ? { ...item, quantity: newQuantity } : item)));
  };

  const removeItem = (id: string) => {
    setCartItems(cartItems.filter((item) => item.id !== id));
  };

  const applyCoupon = () => {
    if (couponCode.toUpperCase() === 'ELSO10') {
      setAppliedCoupon({ code: 'ELSO10', discount: 0.1 });
      setCouponCode('');
    }
  };

  const applyGiftCard = () => {
    if (giftCardCode.startsWith('GC-')) {
      setAppliedGiftCard({ code: giftCardCode, amount: 5000 });
      setGiftCardCode('');
    }
  };

  const subtotal = cartItems.reduce((sum, item) => sum + item.price * item.quantity, 0);
  const discount = appliedCoupon ? subtotal * appliedCoupon.discount : 0;
  const giftCardDeduction = appliedGiftCard ? Math.min(appliedGiftCard.amount, subtotal - discount) : 0;
  const total = subtotal - discount - giftCardDeduction;

  if (cartItems.length === 0) {
    return (
      <div className="max-w-[--container-max] mx-auto px-4 sm:px-6 py-16">
        <div className="text-center py-16">
          <ShoppingBag className="w-24 h-24 mx-auto text-[--color-muted] mb-6" />
          <h2 className="mb-4">A kosarad üres</h2>
          <Link to="/kavek" className="text-[--color-secondary] hover:underline font-medium">
            Fedezd fel kávéinkat →
          </Link>
        </div>
      </div>
    );
  }

  return (
    <div className="max-w-[--container-max] mx-auto px-4 sm:px-6 py-8">
      <h1 className="mb-8">Kosár</h1>

      <div className="grid md:grid-cols-3 gap-8">
        {/* Cart Items */}
        <div className="md:col-span-2">
          <div className="bg-white rounded-lg overflow-hidden">
            {/* Desktop Table */}
            <div className="hidden md:block">
              <table className="w-full">
                <thead className="border-b border-[--color-border]">
                  <tr className="text-left text-sm text-[--color-muted]">
                    <th className="p-4">Termék</th>
                    <th className="p-4">Egységár</th>
                    <th className="p-4">Mennyiség</th>
                    <th className="p-4">Összesen</th>
                    <th className="p-4"></th>
                  </tr>
                </thead>
                <tbody>
                  {cartItems.map((item) => (
                    <tr key={item.id} className="border-b border-[--color-border]">
                      <td className="p-4">
                        <div className="flex items-center gap-4">
                          <ImageWithFallback
                            src={item.image}
                            alt={item.name}
                            className="w-16 h-16 object-cover rounded"
                          />
                          <div>
                            <p className="font-medium">{item.name}</p>
                            <p className="text-sm text-[--color-muted]">{item.variant}</p>
                          </div>
                        </div>
                      </td>
                      <td className="p-4">{formatPrice(item.price)}</td>
                      <td className="p-4">
                        <div className="flex items-center gap-2">
                          <button
                            onClick={() => updateQuantity(item.id, item.quantity - 1)}
                            className="w-11 h-11 border border-[--color-border] rounded flex items-center 
... (7178 chars truncated)
```

### src/app/pages/Checkout.tsx
```
import { useState } from 'react';
import { Check } from 'lucide-react';
import { Button } from '../components/Button';
import { formatPrice } from '../../lib/utils';
import { useNavigate } from 'react-router';

export default function Checkout() {
  const navigate = useNavigate();
  const [step, setStep] = useState(1);
  const [formData, setFormData] = useState({
    name: 'Kiss János',
    postalCode: '1052',
    city: 'Budapest',
    street: 'Váci u. 10',
    phone: '+36 20 123 4567',
    shippingMethod: 'delivery',
  });

  const orderItems = [
    { name: 'Ethiopia Yirgacheffe — Szemes, 500g', quantity: 2, price: 4680 },
    { name: 'Colombia Huila — Őrölt (filter), 250g', quantity: 1, price: 2790 },
  ];

  const subtotal = 11236;
  const shippingFee = formData.shippingMethod === 'delivery' ? 990 : 0;
  const total = subtotal + shippingFee;

  const handleComplete = () => {
    setStep(3);
  };

  return (
    <div className="max-w-[--container-max] mx-auto px-4 sm:px-6 py-8">
      {/* Step Indicator */}
      <div className="flex items-center justify-center mb-12">
        <div className="flex items-center gap-4">
          {[1, 2, 3].map((s) => (
            <div key={s} className="flex items-center">
              <div
                className={`w-10 h-10 rounded-full flex items-center justify-center ${
                  s < step
                    ? 'bg-[--color-primary] text-white'
                    : s === step
                    ? 'bg-[--color-primary] text-white'
                    : 'border-2 border-[--color-border] text-[--color-muted]'
                }`}
              >
                {s < step ? <Check className="w-5 h-5" /> : s}
              </div>
              <span className="ml-2 hidden sm:inline">
                {s === 1 ? 'Szállítás' : s === 2 ? 'Fizetés' : 'Megerősítés'}
              </span>
              {s < 3 && <div className="w-16 h-0.5 bg-[--color-border] mx-4" />}
            </div>
          ))}
        </div>
      </div>

      <div className="grid md:grid-cols-3 gap-8">
        <div className="md:col-span-2">
          {/* Step 1: Shipping */}
          {step === 1 && (
            <div className="bg-white rounded-lg p-6">
              <h2 className="mb-6">Szállítási cím</h2>
              <div className="space-y-4">
                <div>
                  <label className="block mb-2">Név</label>
                  <input
                    type="text"
                    value={formData.name}
                    onChange={(e) => setFormData({ ...formData, name: e.target.value })}
                    className="w-full border border-[--color-border] rounded-lg px-4 py-3"
                  />
                </div>
                <div className="grid grid-cols-2 gap-4">
                  <div>
                    <label className="block mb-2">Irányítószám</label>
                    <input
                      type="text"
                      value={formData.postalCode}
                      onChange={(e) => setFormData({ ...formData, postalCode: e.target.value })}
                      className="w-full border border-[--color-border] rounded-lg px-4 py-3"
                    />
                    <span className="text-xs text-[--color-success] mt-1 inline-block">Budapest</span>
                  </div>
                  <div>
                    <label className="block mb-2">Város</label>
                    <input
                      type="text"
                      value={formData.city}
                      onChange={(e) => setFormData({ ...formData, city: e.target.value })}
                      className="w-full border border-[--color-border] rounded-lg px-4 py-3"
                    />
                  </div>
                </div>
                <div>
                  <label className="block mb-2">Utca, házszám</label>
                  <input
                    type="text"
                    value={formData.street}
                    onChange={(e) => setFormData({ ...formData, street: e.target.value })}
                    className="w-full border border-[--color-border] rounded-lg px-4 py-3"
                  />
                </div>
                <div>
                  <label className="block mb-2">Telefonszám</label>
                  <input
                    type="tel"
                    value={formData.phone}
                    onChange={(e) => setFormData({ ...formData, phone: e.target.value })}
                    className="w-full border border-[--color-border] rounded-lg px-4 py-3"
                  />
                </div>

                <div className="mt-6">
                  <h3 className="font-semibold mb-4">Szállítási mód</h3>
                  <label className="flex items-center gap-3 p-4 border border-[--color-border] rounded-lg mb-3 cursor-pointer hover:bg-[--color-background]">
                    <input
                      type="radio"
                      name="shipping"
                      value="deli
... (6132 chars truncated)
```

### src/app/pages/Home.tsx
```
import { Link } from 'react-router';
import { ArrowRight } from 'lucide-react';
import { Button } from '../components/Button';
import { ProductCard } from '../components/ProductCard';
import { ImageWithFallback } from '../components/figma/ImageWithFallback';

export default function Home() {
  // Mock product data
  const featuredCoffees = [
    {
      id: 'ethiopia-yirgacheffe',
      name: 'Ethiopia Yirgacheffe',
      image: 'https://images.unsplash.com/photo-1772391264887-50a9e650e0fd?crop=entropy&cs=tinysrgb&fit=max&fm=jpg&ixid=M3w3Nzg4Nzd8MHwxfHNlYXJjaHwxfHxldGhpb3BpYW4lMjBjb2ZmZWUlMjBiZWFuc3xlbnwxfHx8fDE3NzMzNDgxNjN8MA&ixlib=rb-4.1.0&q=80&w=1080',
      price: 2490,
      rating: 5,
      reviewCount: 12,
      origin: 'Etiópia',
      roast: 'Világos',
      isNew: true,
    },
    {
      id: 'colombia-huila',
      name: 'Colombia Huila',
      image: 'https://images.unsplash.com/photo-1772141614991-eea2a95e770c?crop=entropy&cs=tinysrgb&fit=max&fm=jpg&ixid=M3w3Nzg4Nzd8MHwxfHNlYXJjaHwxfHxjb2xvbWJpYSUyMGNvZmZlZSUyMHJvYXN0ZWR8ZW58MXx8fHwxNzczMzQ4MTYzfDA&ixlib=rb-4.1.0&q=80&w=1080',
      price: 2790,
      rating: 5,
      reviewCount: 8,
      origin: 'Kolumbia',
      roast: 'Közepes',
    },
    {
      id: 'kenya-aa',
      name: 'Kenya AA',
      image: 'https://images.unsplash.com/photo-1770326965745-079ca2abbc06?crop=entropy&cs=tinysrgb&fit=max&fm=jpg&ixid=M3w3Nzg4Nzd8MHwxfHNlYXJjaHwxfHxrZW55YSUyMGNvZmZlZSUyMHNwZWNpYWx0eXxlbnwxfHx8fDE3NzMzNDgxNjN8MA&ixlib=rb-4.1.0&q=80&w=1080',
      price: 3190,
      rating: 5,
      reviewCount: 15,
      origin: 'Kenya',
      roast: 'Világos',
    },
    {
      id: 'brazil-santos',
      name: 'Brazil Santos',
      image: 'https://images.unsplash.com/photo-1708362524830-989c281f5159?crop=entropy&cs=tinysrgb&fit=max&fm=jpg&ixid=M3w3Nzg4Nzd8MHwxfHNlYXJjaHwxfHxicmF6aWwlMjBjb2ZmZWUlMjBkYXJrJTIwcm9hc3R8ZW58MXx8fHwxNzczMzQ4MTY0fDA&ixlib=rb-4.1.0&q=80&w=1080',
      price: 2290,
      rating: 4,
      reviewCount: 10,
      origin: 'Brazília',
      roast: 'Sötét',
    },
  ];

  const stories = [
    {
      id: 'yirgacheffe-origin',
      title: 'Yirgacheffe: A kávé szülőföldje',
      category: 'Eredet',
      image: 'https://images.unsplash.com/photo-1625465115622-4a265061db77?crop=entropy&cs=tinysrgb&fit=max&fm=jpg&ixid=M3w3Nzg4Nzd8MHwxfHNlYXJjaHwxfHxjb2ZmZWUlMjByb2FzdGluZyUyMHByb2Nlc3N8ZW58MXx8fHwxNzczMjg3OTQyfDA&ixlib=rb-4.1.0&q=80&w=1080',
      date: '2026-03-10',
    },
    {
      id: 'brewing-guide',
      title: 'Tökéletes főzési útmutató',
      category: 'Főzés',
      image: 'https://images.unsplash.com/photo-1550559256-32644b7a2993?crop=entropy&cs=tinysrgb&fit=max&fm=jpg&ixid=M3w3Nzg4Nzd8MHwxfHNlYXJjaHwxfHxjb2ZmZWUlMjBicmV3aW5nJTIwcG91ciUyMG92ZXJ8ZW58MXx8fHwxNzczMjg2Njg5fDA&ixlib=rb-4.1.0&q=80&w=1080',
      date: '2026-03-08',
    },
    {
      id: 'coffee-health',
      title: 'A kávé egészségügyi előnyei',
      category: 'Egészség',
      image: 'https://images.unsplash.com/photo-1713742000733-f038b0bf61cd?crop=entropy&cs=tinysrgb&fit=max&fm=jpg&ixid=M3w3Nzg4Nzd8MHwxfHNlYXJjaHwxfHxjb2ZmZWUlMjBoZWFsdGglMjBiZW5lZml0c3xlbnwxfHx8fDE3NzMzNDgxNjV8MA&ixlib=rb-4.1.0&q=80&w=1080',
      date: '2026-03-05',
    },
  ];

  const testimonials = [
    {
      id: 1,
      stars: 5,
      quote: 'Fantasztikus minőség! Az Ethiopia Yirgacheffe a kedvencem, olyan virágos és citrusos ízvilága van.',
      name: 'Nagy Petra',
      product: 'Ethiopia Yirgacheffe',
    },
    {
      id: 2,
      stars: 5,
      quote: 'A szállítás mindig pontos, a csomagolás gyönyörű. Ajándékba is gyakran veszem.',
      name: 'Kovács András',
      product: 'Colombia Huila',
    },
    {
      id: 3,
      stars: 5,
      quote: 'Az előfizetés megváltoztatta a reggeli rutinom. Friss kávé minden nap, egyszerű és kényelmes!',
      name: 'Szabó Eszter',
      product: 'Kenya AA',
    },
  ];

  return (
    <div>
      {/* Hero Banner */}
      <section className="relative h-[500px] overflow-hidden">
        <ImageWithFallback
          src="https://images.unsplash.com/photo-1736813133035-6baf4762fd3d?crop=entropy&cs=tinysrgb&fit=max&fm=jpg&ixid=M3w3Nzg4Nzd8MHwxfHNlYXJjaHwxfHxjb2ZmZWUlMjBiZWFucyUyMGJhcmlzdGElMjBhdG1vc3BoZXJpY3xlbnwxfHx8fDE3NzMzNDgxNjJ8MA&ixlib=rb-4.1.0&q=80&w=1080"
          alt="Coffee Hero"
          className="w-full h-full object-cover"
        />
        <div className="absolute inset-0 bg-gradient-to-r from-black/60 to-black/30">
          <div className="max-w-[--container-max] mx-auto px-4 sm:px-6 h-full flex items-center">
            <div className="max-w-2xl text-white">
              <h1 className="mb-4" style={{ color: 'white' }}>
                Specialty kávé, az asztalodra szállítva.
              </h1>
              <p className="text-xl mb-8 opacity-90">
                Kézzel válogatott, frissen pörkölt kávékülönlegességek Budapestről
              </p>
              <Button variant="primary">
                Fedezd fel kávéinkat <ArrowRi
... (4529 chars truncated)
```

### src/app/pages/Login.tsx
```
import { useState } from 'react';
import { Link } from 'react-router';
import { Eye, EyeOff } from 'lucide-react';
import { Button } from '../components/Button';

export default function Login() {
  const [showPassword, setShowPassword] = useState(false);
  const [formData, setFormData] = useState({
    email: '',
    password: '',
    remember: false,
  });

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    // Handle login
  };

  return (
    <div className="min-h-[80vh] flex items-center justify-center py-12 px-4">
      <div className="w-full max-w-md bg-white rounded-lg p-8 shadow-lg">
        <div className="text-center mb-8">
          <h2 className="text-3xl font-bold" style={{ fontFamily: 'var(--font-heading)', color: 'var(--color-primary)' }}>
            CraftBrew
          </h2>
        </div>

        <h2 className="mb-6">Bejelentkezés</h2>

        <form onSubmit={handleSubmit} className="space-y-4">
          <div>
            <label className="block mb-2">Email</label>
            <input
              type="email"
              value={formData.email}
              onChange={(e) => setFormData({ ...formData, email: e.target.value })}
              className="w-full border border-[--color-border] rounded-lg px-4 py-3"
              required
            />
          </div>

          <div>
            <label className="block mb-2">Jelszó</label>
            <div className="relative">
              <input
                type={showPassword ? 'text' : 'password'}
                value={formData.password}
                onChange={(e) => setFormData({ ...formData, password: e.target.value })}
                className="w-full border border-[--color-border] rounded-lg px-4 py-3 pr-12"
                required
              />
              <button
                type="button"
                onClick={() => setShowPassword(!showPassword)}
                className="absolute right-3 top-1/2 -translate-y-1/2 text-[--color-muted]"
              >
                {showPassword ? <EyeOff className="w-5 h-5" /> : <Eye className="w-5 h-5" />}
              </button>
            </div>
          </div>

          <div className="flex items-center justify-between">
            <label className="flex items-center gap-2 cursor-pointer">
              <input
                type="checkbox"
                checked={formData.remember}
                onChange={(e) => setFormData({ ...formData, remember: e.target.checked })}
                className="w-4 h-4 rounded border-[--color-border]"
              />
              <span className="text-sm">Emlékezz rám</span>
            </label>
            <Link to="/jelszo-elfelejtve" className="text-sm text-[--color-secondary] hover:underline">
              Elfelejtett jelszó?
            </Link>
          </div>

          <Button type="submit" variant="primary" fullWidth>
            Bejelentkezés
          </Button>
        </form>

        <div className="mt-6 text-center">
          <p className="text-[--color-muted] mb-3">Nincs még fiókod?</p>
          <Link to="/regisztracio">
            <Button variant="outlined" fullWidth>
              Regisztráció
            </Button>
          </Link>
        </div>
      </div>
    </div>
  );
}

```

### src/app/pages/NotFound.tsx
```
import { Link } from 'react-router';
import { Coffee } from 'lucide-react';
import { Button } from '../components/Button';

export default function NotFound() {
  return (
    <div className="min-h-[70vh] flex items-center justify-center px-4">
      <div className="text-center max-w-md">
        <Coffee className="w-32 h-32 mx-auto text-[--color-muted] mb-6 opacity-50" />
        <h1 className="mb-4">Hoppá! Ez az oldal nem található</h1>
        <p className="text-[--color-muted] mb-8">
          A keresett oldal nem létezik vagy átköltözött.
        </p>
        <Link to="/">
          <Button variant="primary">Vissza a főoldalra</Button>
        </Link>
      </div>
    </div>
  );
}

```

### src/app/pages/ProductCatalog.tsx
```
import { useState } from 'react';
import { ChevronDown, ChevronUp, SlidersHorizontal } from 'lucide-react';
import { ProductCard } from '../components/ProductCard';

export default function ProductCatalog() {
  const [showFilters, setShowFilters] = useState(true);
  const [filters, setFilters] = useState({
    origin: [] as string[],
    roast: [] as string[],
    processing: [] as string[],
    priceMin: 1990,
    priceMax: 9380,
  });

  const origins = ['Etiópia', 'Kolumbia', 'Brazília', 'Guatemala', 'Kenya', 'Indonézia', 'Costa Rica', 'Ruanda'];
  const roastLevels = ['Világos', 'Közepes', 'Sötét'];
  const processingMethods = ['Mosott', 'Természetes', 'Mézes', 'Wet-hulled'];

  const products = [
    {
      id: 'ethiopia-yirgacheffe',
      name: 'Ethiopia Yirgacheffe',
      image: 'https://images.unsplash.com/photo-1772391264887-50a9e650e0fd?w=400',
      price: 2490,
      rating: 5,
      reviewCount: 12,
      origin: 'Etiópia',
      roast: 'Világos',
      isNew: true,
    },
    {
      id: 'colombia-huila',
      name: 'Colombia Huila',
      image: 'https://images.unsplash.com/photo-1772141614991-eea2a95e770c?w=400',
      price: 2790,
      rating: 5,
      reviewCount: 8,
      origin: 'Kolumbia',
      roast: 'Közepes',
    },
    {
      id: 'kenya-aa',
      name: 'Kenya AA',
      image: 'https://images.unsplash.com/photo-1770326965745-079ca2abbc06?w=400',
      price: 3190,
      rating: 5,
      reviewCount: 15,
      origin: 'Kenya',
      roast: 'Világos',
    },
    {
      id: 'brazil-santos',
      name: 'Brazil Santos',
      image: 'https://images.unsplash.com/photo-1708362524830-989c281f5159?w=400',
      price: 2290,
      rating: 4,
      reviewCount: 10,
      origin: 'Brazília',
      roast: 'Sötét',
    },
    {
      id: 'guatemala-antigua',
      name: 'Guatemala Antigua',
      image: 'https://images.unsplash.com/photo-1772391264887-50a9e650e0fd?w=400',
      price: 2990,
      rating: 5,
      reviewCount: 7,
      origin: 'Guatemala',
      roast: 'Közepes',
    },
    {
      id: 'costa-rica-tarrazu',
      name: 'Costa Rica Tarrazú',
      image: 'https://images.unsplash.com/photo-1772141614991-eea2a95e770c?w=400',
      price: 3290,
      rating: 5,
      reviewCount: 9,
      origin: 'Costa Rica',
      roast: 'Világos',
    },
    {
      id: 'indonesia-sumatra',
      name: 'Indonesia Sumatra',
      image: 'https://images.unsplash.com/photo-1708362524830-989c281f5159?w=400',
      price: 2590,
      rating: 4,
      reviewCount: 11,
      origin: 'Indonézia',
      roast: 'Sötét',
    },
    {
      id: 'rwanda-nyungwe',
      name: 'Rwanda Nyungwe',
      image: 'https://images.unsplash.com/photo-1770326965745-079ca2abbc06?w=400',
      price: 3390,
      rating: 5,
      reviewCount: 6,
      origin: 'Ruanda',
      roast: 'Világos',
      isNew: true,
    },
  ];

  const FilterSection = ({ title, items, filterKey }: { title: string; items: string[]; filterKey: string }) => {
    const [expanded, setExpanded] = useState(true);

    return (
      <div className="border-b border-[--color-border] pb-4 mb-4">
        <button
          onClick={() => setExpanded(!expanded)}
          className="flex items-center justify-between w-full mb-3 font-medium"
        >
          {title}
          {expanded ? <ChevronUp className="w-4 h-4" /> : <ChevronDown className="w-4 h-4" />}
        </button>
        {expanded && (
          <div className="space-y-2">
            {items.map((item) => (
              <label key={item} className="flex items-center gap-2 cursor-pointer">
                <input
                  type="checkbox"
                  className="w-4 h-4 rounded border-[--color-border] text-[--color-primary] focus:ring-[--color-secondary]"
                  onChange={(e) => {
                    const key = filterKey as keyof typeof filters;
                    if (e.target.checked) {
                      setFilters({
                        ...filters,
                        [key]: [...(filters[key] as string[]), item],
                      });
                    } else {
                      setFilters({
                        ...filters,
                        [key]: (filters[key] as string[]).filter((i) => i !== item),
                      });
                    }
                  }}
                />
                <span className="text-sm">{item}</span>
              </label>
            ))}
          </div>
        )}
      </div>
    );
  };

  return (
    <div className="max-w-[--container-max] mx-auto px-4 sm:px-6 py-8">
      {/* Page Title */}
      <h1 className="mb-8">Kávék</h1>

      <div className="flex flex-col md:flex-row gap-8">
        {/* Mobile Filter Button */}
        <button
          className="md:hidden flex items-center justify-center gap-2 bg-white border border-[--color-border] rounded-lg px-4 py-3"
          onClick={() => setShowFilters(!showFilters)}
        >
          <SlidersHorizontal className="w-5 h-5" 
... (3088 chars truncated)
```

### src/app/pages/ProductDetail.tsx
```
import { useState } from 'react';
import { Link } from 'react-router';
import { Heart, Minus, Plus, ChevronRight } from 'lucide-react';
import { Button } from '../components/Button';
import { StarRating } from '../components/StarRating';
import { Badge } from '../components/Badge';
import { ProductCard } from '../components/ProductCard';
import { ImageWithFallback } from '../components/figma/ImageWithFallback';
import { formatPrice } from '../../lib/utils';
import { toast } from 'sonner';

export default function ProductDetail() {
  const [selectedForm, setSelectedForm] = useState('beans');
  const [selectedSize, setSelectedSize] = useState('500g');
  const [quantity, setQuantity] = useState(1);
  const [isFavorite, setIsFavorite] = useState(false);

  const product = {
    id: 'ethiopia-yirgacheffe',
    name: 'Ethiopia Yirgacheffe',
    image: 'https://images.unsplash.com/photo-1772391264887-50a9e650e0fd?w=800',
    rating: 5,
    reviewCount: 12,
    origin: 'Etiópia',
    roast: 'Világos',
    processing: 'Mosott',
    flavorNotes: ['Virágos', 'Citrusos', 'Jázmin', 'Bergamott'],
    description:
      'Az Ethiopia Yirgacheffe különleges minőségű specialty kávé, amely a legendás etióp Yirgacheffe régióból származik. Mosott feldolgozású, világos pörkölésű kávénk virágos, citrusos aromákkal és egyedi jázmin-bergamott ízvilággal rendelkezik. Tökéletes választás filter kávéhoz és pour over módszerekhez.',
    stock: 45,
    prices: {
      beans: {
        '250g': 2490,
        '500g': 4680,
        '1kg': 6580,
      },
      'ground-filter': {
        '250g': 2490,
        '500g': 4680,
        '1kg': 6580,
      },
      'ground-espresso': {
        '250g': 2490,
        '500g': 4680,
        '1kg': 6580,
      },
      'drip-bag': {
        '250g': 2990,
        '500g': 5480,
        '1kg': 7580,
      },
    },
  };

  const recommendedProducts = [
    {
      id: 'v60-dripper',
      name: 'Hario V60 Dripper',
      image: 'https://images.unsplash.com/photo-1550559256-32644b7a2993?w=400',
      price: 3990,
      rating: 5,
      reviewCount: 24,
    },
    {
      id: 'v60-filters',
      name: 'V60 Papír Filterek',
      image: 'https://images.unsplash.com/photo-1550559256-32644b7a2993?w=400',
      price: 1290,
      rating: 5,
      reviewCount: 18,
    },
    {
      id: 'timemore-scale',
      name: 'Timemore Mérleg',
      image: 'https://images.unsplash.com/photo-1550559256-32644b7a2993?w=400',
      price: 12990,
      rating: 5,
      reviewCount: 32,
    },
  ];

  const reviews = [
    {
      id: 1,
      stars: 5,
      title: 'Csodálatos kávé!',
      text: 'Az Ethiopia Yirgacheffe a kedvencem lett! Olyan finom virágos íze van, amit még soha nem tapasztaltam. Minden reggel ezt iszom.',
      author: 'Nagy Petra',
      date: '2026-03-10',
      reply: 'Köszönjük szépen a visszajelzést, Petra! Örülünk, hogy tetszik! 🙂',
    },
    {
      id: 2,
      stars: 5,
      title: 'Friss és finom',
      text: 'Nagyon frissen érkezett, az illat csodálatos volt már a kinyitáskor. V60-ban készítem, tökéletes!',
      author: 'Kovács András',
      date: '2026-03-08',
    },
  ];

  const currentPrice = product.prices[selectedForm as keyof typeof product.prices][selectedSize as keyof typeof product.prices.beans];

  const handleAddToCart = () => {
    toast.success('Termék hozzáadva a kosárhoz');
  };

  return (
    <div className="max-w-[--container-max] mx-auto px-4 sm:px-6 py-8">
      {/* Breadcrumb */}
      <nav className="flex items-center gap-2 text-sm text-[--color-muted] mb-8">
        <Link to="/" className="hover:text-[--color-secondary]">
          Főoldal
        </Link>
        <ChevronRight className="w-4 h-4" />
        <Link to="/kavek" className="hover:text-[--color-secondary]">
          Kávék
        </Link>
        <ChevronRight className="w-4 h-4" />
        <span className="text-[--color-text]">{product.name}</span>
      </nav>

      {/* Product Details */}
      <div className="grid md:grid-cols-2 gap-12 mb-16">
        {/* Image */}
        <div className="aspect-square bg-white rounded-lg overflow-hidden">
          <ImageWithFallback src={product.image} alt={product.name} className="w-full h-full object-cover" />
        </div>

        {/* Info */}
        <div>
          <h1 className="mb-4">{product.name}</h1>
          <div className="mb-4">
            <StarRating rating={product.rating} count={product.reviewCount} size="lg" />
          </div>

          <p className="text-3xl font-bold text-[--color-primary] mb-6">{formatPrice(currentPrice)}</p>

          <div className="flex gap-4 mb-4 text-sm">
            <span>
              <strong>Eredet:</strong> {product.origin}
            </span>
            <span>
              <strong>Pörkölés:</strong> {product.roast}
            </span>
            <span>
              <strong>Feldolgozás:</strong> {product.processing}
            </span>
          </div>

          {/* Flavor Notes */}
          <div className="
... (5613 chars truncated)
```

### src/app/pages/Register.tsx
```
import { useState } from 'react';
import { Link } from 'react-router';
import { Eye, EyeOff } from 'lucide-react';
import { Button } from '../components/Button';

export default function Register() {
  const [showPassword, setShowPassword] = useState(false);
  const [showConfirmPassword, setShowConfirmPassword] = useState(false);
  const [formData, setFormData] = useState({
    name: '',
    email: '',
    password: '',
    confirmPassword: '',
    language: 'HU',
    acceptTerms: false,
  });

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    // Handle registration
  };

  return (
    <div className="min-h-[80vh] flex items-center justify-center py-12 px-4">
      <div className="w-full max-w-md bg-white rounded-lg p-8 shadow-lg">
        <div className="text-center mb-8">
          <h2 className="text-3xl font-bold" style={{ fontFamily: 'var(--font-heading)', color: 'var(--color-primary)' }}>
            CraftBrew
          </h2>
        </div>

        <h2 className="mb-6">Regisztráció</h2>

        <form onSubmit={handleSubmit} className="space-y-4">
          <div>
            <label className="block mb-2">Teljes név</label>
            <input
              type="text"
              value={formData.name}
              onChange={(e) => setFormData({ ...formData, name: e.target.value })}
              className="w-full border border-[--color-border] rounded-lg px-4 py-3"
              required
            />
          </div>

          <div>
            <label className="block mb-2">Email</label>
            <input
              type="email"
              value={formData.email}
              onChange={(e) => setFormData({ ...formData, email: e.target.value })}
              className="w-full border border-[--color-border] rounded-lg px-4 py-3"
              required
            />
          </div>

          <div>
            <label className="block mb-2">Jelszó</label>
            <div className="relative">
              <input
                type={showPassword ? 'text' : 'password'}
                value={formData.password}
                onChange={(e) => setFormData({ ...formData, password: e.target.value })}
                className="w-full border border-[--color-border] rounded-lg px-4 py-3 pr-12"
                required
              />
              <button
                type="button"
                onClick={() => setShowPassword(!showPassword)}
                className="absolute right-3 top-1/2 -translate-y-1/2 text-[--color-muted]"
              >
                {showPassword ? <EyeOff className="w-5 h-5" /> : <Eye className="w-5 h-5" />}
              </button>
            </div>
            <p className="text-xs text-[--color-muted] mt-1">Minimum 8 karakter</p>
          </div>

          <div>
            <label className="block mb-2">Jelszó megerősítése</label>
            <div className="relative">
              <input
                type={showConfirmPassword ? 'text' : 'password'}
                value={formData.confirmPassword}
                onChange={(e) => setFormData({ ...formData, confirmPassword: e.target.value })}
                className="w-full border border-[--color-border] rounded-lg px-4 py-3 pr-12"
                required
              />
              <button
                type="button"
                onClick={() => setShowConfirmPassword(!showConfirmPassword)}
                className="absolute right-3 top-1/2 -translate-y-1/2 text-[--color-muted]"
              >
                {showConfirmPassword ? <EyeOff className="w-5 h-5" /> : <Eye className="w-5 h-5" />}
              </button>
            </div>
          </div>

          <div>
            <label className="block mb-2">Nyelv</label>
            <div className="flex gap-4">
              <label className="flex items-center gap-2 cursor-pointer">
                <input
                  type="radio"
                  name="language"
                  value="HU"
                  checked={formData.language === 'HU'}
                  onChange={(e) => setFormData({ ...formData, language: e.target.value })}
                />
                <span>HU</span>
              </label>
              <label className="flex items-center gap-2 cursor-pointer">
                <input
                  type="radio"
                  name="language"
                  value="EN"
                  checked={formData.language === 'EN'}
                  onChange={(e) => setFormData({ ...formData, language: e.target.value })}
                />
                <span>EN</span>
              </label>
            </div>
          </div>

          <label className="flex items-start gap-2 cursor-pointer">
            <input
              type="checkbox"
              checked={formData.acceptTerms}
              onChange={(e) => setFormData({ ...formData, acceptTerms: e.target.checked })}
              className="w-4 h-4 mt-1 rounded border-[--color-border]"
              required
            />
... (834 chars truncated)
```

### src/app/pages/Stories.tsx
```
import { Link } from 'react-router';
import { useState } from 'react';
import { ImageWithFallback } from '../components/figma/ImageWithFallback';

export default function Stories() {
  const [activeCategory, setActiveCategory] = useState('Mind');
  const categories = ['Mind', 'Eredet', 'Pörkölés', 'Főzés', 'Egészség', 'Ajándék'];

  const stories = [
    {
      id: 'yirgacheffe-origin',
      title: 'Yirgacheffe: A kávé szülőföldje',
      category: 'Eredet',
      image: 'https://images.unsplash.com/photo-1625465115622-4a265061db77?w=600',
      date: '2026-03-10',
      excerpt: 'Fedezd fel az etióp Yirgacheffe régió egyedi kávékultúráját és történetét...',
    },
    {
      id: 'brewing-guide',
      title: 'Tökéletes főzési útmutató',
      category: 'Főzés',
      image: 'https://images.unsplash.com/photo-1550559256-32644b7a2993?w=600',
      date: '2026-03-08',
      excerpt: 'Lépésről lépésre guide a tökéletes pour over kávé elkészítéséhez...',
    },
    {
      id: 'coffee-health',
      title: 'A kávé egészségügyi előnyei',
      category: 'Egészség',
      image: 'https://images.unsplash.com/photo-1713742000733-f038b0bf61cd?w=600',
      date: '2026-03-05',
      excerpt: 'Tudományos kutatások a kávé pozitív hatásairól a szervezetre...',
    },
    {
      id: 'roasting-process',
      title: 'A pörkölés művészete',
      category: 'Pörkölés',
      image: 'https://images.unsplash.com/photo-1625465115622-4a265061db77?w=600',
      date: '2026-03-01',
      excerpt: 'Betekintés a specialty kávé pörkölésének rejtelmeibe...',
    },
    {
      id: 'gift-guide',
      title: 'Kávé ajándékozási útmutató',
      category: 'Ajándék',
      image: 'https://images.unsplash.com/photo-1772200514909-c0ba6cba34f0?w=600',
      date: '2026-02-28',
      excerpt: 'Tippek és ötletek kávékedvelőknek szóló ajándékokhoz...',
    },
    {
      id: 'colombia-farms',
      title: 'Kolumbiai kávéültetvények',
      category: 'Eredet',
      image: 'https://images.unsplash.com/photo-1772141614991-eea2a95e770c?w=600',
      date: '2026-02-25',
      excerpt: 'Látogatás a kolumbiai Huila régió kávéfarmjain...',
    },
  ];

  const filteredStories = activeCategory === 'Mind' 
    ? stories 
    : stories.filter(story => story.category === activeCategory);

  return (
    <div className="max-w-[--container-max] mx-auto px-4 sm:px-6 py-8">
      <h1 className="mb-8">Sztorik</h1>

      {/* Category Tabs */}
      <div className="flex gap-6 mb-8 overflow-x-auto pb-2">
        {categories.map((category) => (
          <button
            key={category}
            onClick={() => setActiveCategory(category)}
            className={`whitespace-nowrap pb-2 border-b-2 transition-colors ${
              activeCategory === category
                ? 'border-[--color-secondary] text-[--color-secondary] font-medium'
                : 'border-transparent text-[--color-muted] hover:text-[--color-text]'
            }`}
          >
            {category}
          </button>
        ))}
      </div>

      {/* Stories Grid */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
        {filteredStories.map((story) => (
          <Link
            key={story.id}
            to={`/sztorik/${story.id}`}
            className="group bg-white rounded-lg overflow-hidden shadow-md hover:shadow-xl transition-shadow"
          >
            <div className="aspect-video overflow-hidden">
              <ImageWithFallback
                src={story.image}
                alt={story.title}
                className="w-full h-full object-cover group-hover:scale-105 transition-transform duration-300"
              />
            </div>
            <div className="p-6">
              <span className="inline-block px-3 py-1 bg-[--color-secondary] text-white text-xs rounded-full mb-3">
                {story.category}
              </span>
              <h3 className="mb-2">{story.title}</h3>
              <p className="text-sm text-[--color-muted] mb-3">{story.date}</p>
              <p className="text-sm text-[--color-muted]">{story.excerpt}</p>
            </div>
          </Link>
        ))}
      </div>
    </div>
  );
}

```

### src/app/pages/StoryDetail.tsx
```
import { Link, useParams } from 'react-router';
import { ChevronRight, Facebook, Share2 } from 'lucide-react';
import { ImageWithFallback } from '../components/figma/ImageWithFallback';
import { ProductCard } from '../components/ProductCard';

export default function StoryDetail() {
  const { slug } = useParams();

  const story = {
    id: slug || 'yirgacheffe-origin',
    title: 'Yirgacheffe: A kávé szülőföldje',
    category: 'Eredet',
    image: 'https://images.unsplash.com/photo-1625465115622-4a265061db77?w=1200',
    date: '2026-03-10',
    author: 'CraftBrew csapat',
    content: `
      <p>Az etióp Yirgacheffe régió a világ egyik legkülönlegesebb kávétermő vidéke. A magas tengerszint feletti magasságban, ideális klímában termelt kávé egyedi virágos és citrusos aromáival hódította meg a specialty kávé szerelmeseit világszerte.</p>
      
      <h3>A régió története</h3>
      <p>Yirgacheffe Etiópia délnyugati részén található, ahol a kávé természetes élőhelyén nő. A helyi közösségek generációk óta foglalkoznak kávétermesztéssel, és büszkék egyedi feldolgozási módszereikre.</p>
      
      <h3>Feldolgozás és ízvilág</h3>
      <p>A Yirgacheffe kávét jellemzően mosott (washed) módszerrel dolgozzák fel, ami hozzájárul tiszta, komplex ízprofiljához. A jellegzetes jázmin, bergamott és citrusos jegyek különösen filter kávéban érvényesülnek.</p>
      
      <h3>Miért különleges?</h3>
      <p>A régió egyedi terroir-ja - a talaj, klíma és magasság kombinációja - olyan kávét eredményez, amely egyedülálló a világon. Érdemes kipróbálni pour over vagy V60 módszerrel, hogy teljes mértékben élvezhessük a finomságokat.</p>
    `,
  };

  const relatedProducts = [
    {
      id: 'ethiopia-yirgacheffe',
      name: 'Ethiopia Yirgacheffe',
      image: 'https://images.unsplash.com/photo-1772391264887-50a9e650e0fd?w=400',
      price: 2490,
      rating: 5,
      reviewCount: 12,
      origin: 'Etiópia',
      roast: 'Világos',
    },
    {
      id: 'v60-dripper',
      name: 'Hario V60 Dripper',
      image: 'https://images.unsplash.com/photo-1550559256-32644b7a2993?w=400',
      price: 3990,
      rating: 5,
      reviewCount: 24,
    },
  ];

  return (
    <div className="max-w-[--container-max] mx-auto px-4 sm:px-6 py-8">
      {/* Breadcrumb */}
      <nav className="flex items-center gap-2 text-sm text-[--color-muted] mb-8">
        <Link to="/" className="hover:text-[--color-secondary]">
          Főoldal
        </Link>
        <ChevronRight className="w-4 h-4" />
        <Link to="/sztorik" className="hover:text-[--color-secondary]">
          Sztorik
        </Link>
        <ChevronRight className="w-4 h-4" />
        <Link to="/sztorik" className="hover:text-[--color-secondary]">
          {story.category}
        </Link>
        <ChevronRight className="w-4 h-4" />
        <span className="text-[--color-text]">{story.title}</span>
      </nav>

      {/* Cover Image */}
      <div className="aspect-video md:aspect-[21/9] overflow-hidden rounded-lg mb-8">
        <ImageWithFallback src={story.image} alt={story.title} className="w-full h-full object-cover" />
      </div>

      {/* Article Header */}
      <div className="max-w-3xl mx-auto mb-8">
        <div className="flex items-center gap-4 mb-4">
          <span className="px-3 py-1 bg-[--color-secondary] text-white text-sm rounded-full">{story.category}</span>
          <span className="text-sm text-[--color-muted]">{story.date}</span>
          <span className="text-sm text-[--color-muted]">{story.author}</span>
        </div>
        <h1 className="mb-6">{story.title}</h1>

        {/* Share Buttons */}
        <div className="flex items-center gap-3 pb-6 border-b border-[--color-border]">
          <span className="text-sm text-[--color-muted]">Megosztás:</span>
          <button className="p-2 rounded-full hover:bg-[--color-background] transition-colors">
            <Facebook className="w-5 h-5 text-[--color-muted]" />
          </button>
          <button className="p-2 rounded-full hover:bg-[--color-background] transition-colors">
            <Share2 className="w-5 h-5 text-[--color-muted]" />
          </button>
        </div>
      </div>

      {/* Article Content */}
      <article className="max-w-3xl mx-auto prose prose-lg mb-16">
        <div
          className="text-[--color-text] leading-relaxed"
          dangerouslySetInnerHTML={{ __html: story.content }}
          style={{ lineHeight: 1.8 }}
        />
      </article>

      {/* Related Products */}
      <div className="max-w-5xl mx-auto">
        <h2 className="mb-8">Kapcsolódó termékek</h2>
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-6">
          {relatedProducts.map((product) => (
            <ProductCard key={product.id} {...product} />
          ))}
        </div>
      </div>
    </div>
  );
}

```

### src/app/pages/SubscriptionWizard.tsx
```
import { useState } from 'react';
import { Button } from '../components/Button';
import { ProductCard } from '../components/ProductCard';
import { Check } from 'lucide-react';

export default function SubscriptionWizard() {
  const [step, setStep] = useState(1);
  const [selectedCoffee, setSelectedCoffee] = useState('');
  const [selectedSize, setSelectedSize] = useState('500g');
  const [selectedFrequency, setSelectedFrequency] = useState('daily');

  const coffees = [
    {
      id: 'ethiopia-yirgacheffe',
      name: 'Ethiopia Yirgacheffe',
      image: 'https://images.unsplash.com/photo-1772391264887-50a9e650e0fd?w=400',
      price: 2490,
      rating: 5,
      reviewCount: 12,
      origin: 'Etiópia',
    },
    {
      id: 'colombia-huila',
      name: 'Colombia Huila',
      image: 'https://images.unsplash.com/photo-1772141614991-eea2a95e770c?w=400',
      price: 2790,
      rating: 5,
      reviewCount: 8,
      origin: 'Kolumbia',
    },
  ];

  const frequencies = [
    { id: 'daily', name: 'Naponta', discount: 15, badge: 'Legjobb ár!' },
    { id: 'weekly', name: 'Hetente (hétfő)', discount: 10 },
    { id: 'biweekly', name: 'Kéthetente', discount: 7 },
    { id: 'monthly', name: 'Havonta', discount: 5 },
  ];

  return (
    <div className="max-w-[--container-max] mx-auto px-4 sm:px-6 py-8">
      {/* Progress Bar */}
      <div className="mb-12">
        <div className="flex items-center justify-between max-w-3xl mx-auto">
          {[1, 2, 3, 4, 5].map((s) => (
            <div key={s} className="flex items-center flex-1">
              <div
                className={`w-10 h-10 rounded-full flex items-center justify-center ${
                  s <= step ? 'bg-[--color-primary] text-white' : 'bg-[--color-border] text-[--color-muted]'
                }`}
              >
                {s < step ? <Check className="w-5 h-5" /> : s}
              </div>
              {s < 5 && (
                <div
                  className={`flex-1 h-1 mx-2 ${
                    s < step ? 'bg-[--color-primary]' : 'bg-[--color-border]'
                  }`}
                />
              )}
            </div>
          ))}
        </div>
      </div>

      <div className="max-w-4xl mx-auto">
        {/* Step 1: Choose Coffee */}
        {step === 1 && (
          <div>
            <h2 className="mb-8 text-center">Válaszd ki a kávédat</h2>
            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-6 mb-8">
              {coffees.map((coffee) => (
                <div
                  key={coffee.id}
                  onClick={() => setSelectedCoffee(coffee.id)}
                  className={`cursor-pointer ${
                    selectedCoffee === coffee.id ? 'ring-2 ring-[--color-secondary] rounded-lg' : ''
                  }`}
                >
                  <ProductCard {...coffee} />
                </div>
              ))}
            </div>
            <div className="flex justify-center">
              <Button variant="primary" onClick={() => setStep(2)} disabled={!selectedCoffee}>
                Tovább
              </Button>
            </div>
          </div>
        )}

        {/* Step 2: Size */}
        {step === 2 && (
          <div>
            <h2 className="mb-8 text-center">Forma és méret</h2>
            <div className="max-w-md mx-auto space-y-4 mb-8">
              <div>
                <label className="block mb-2 font-medium">Forma</label>
                <select className="w-full border border-[--color-border] rounded-lg px-4 py-3 bg-white">
                  <option>Szemes</option>
                  <option>Őrölt (filter)</option>
                  <option>Őrölt (eszpresszó)</option>
                </select>
              </div>

              <div>
                <label className="block mb-3 font-medium">Méret</label>
                {['250g', '500g', '1kg'].map((size) => (
                  <label
                    key={size}
                    className={`flex items-center justify-between p-4 border-2 rounded-lg mb-3 cursor-pointer ${
                      selectedSize === size ? 'border-[--color-secondary] bg-[--color-background]' : 'border-[--color-border]'
                    }`}
                  >
                    <input
                      type="radio"
                      name="size"
                      value={size}
                      checked={selectedSize === size}
                      onChange={(e) => setSelectedSize(e.target.value)}
                      className="mr-3"
                    />
                    <span className="flex-1">{size}</span>
                    <span className="font-semibold">
                      {size === '250g' ? '2 490 Ft' : size === '500g' ? '4 680 Ft' : '6 580 Ft'}
                    </span>
                  </label>
                ))}
              </div>
            </div>
            <div className="flex justify-center gap-4">
              <Button variant="outlined" onClick={() => 
... (6311 chars truncated)
```

### src/app/pages/UserDashboard.tsx
```
import { Routes, Route, Link, useLocation } from 'react-router';
import { User, MapPin, ShoppingBag, Calendar, Heart } from 'lucide-react';
import { Button } from '../components/Button';
import { formatPrice } from '../../lib/utils';

function Profile() {
  return (
    <div className="bg-white rounded-lg p-6">
      <h2 className="mb-6">Adataim</h2>
      <div className="space-y-4 max-w-md">
        <div>
          <label className="block mb-2">Név</label>
          <input type="text" defaultValue="Kiss János" className="w-full border border-[--color-border] rounded-lg px-4 py-3" />
        </div>
        <div>
          <label className="block mb-2">Email</label>
          <input type="email" defaultValue="kiss.janos@example.com" className="w-full border border-[--color-border] rounded-lg px-4 py-3" readOnly />
        </div>
        <div>
          <label className="block mb-2">Nyelv</label>
          <div className="flex gap-4">
            <label className="flex items-center gap-2">
              <input type="radio" name="lang" defaultChecked />
              <span>HU</span>
            </label>
            <label className="flex items-center gap-2">
              <input type="radio" name="lang" />
              <span>EN</span>
            </label>
          </div>
        </div>
        <Button variant="primary">Mentés</Button>
      </div>
    </div>
  );
}

function Addresses() {
  const addresses = [
    { id: 1, label: 'Otthon', name: 'Kiss János', address: '1052 Budapest, Váci u. 10', phone: '+36 20 123 4567', zone: 'Budapest', isDefault: true },
    { id: 2, label: 'Iroda', name: 'Kiss János', address: '1075 Budapest, Kazinczy u. 28', phone: '+36 20 123 4567', zone: 'Budapest', isDefault: false },
  ];

  return (
    <div className="bg-white rounded-lg p-6">
      <div className="flex items-center justify-between mb-6">
        <h2>Címeim</h2>
        <Button variant="primary">+ Új cím</Button>
      </div>
      <div className="space-y-4">
        {addresses.map((addr) => (
          <div key={addr.id} className="border border-[--color-border] rounded-lg p-4">
            <div className="flex items-start justify-between mb-2">
              <div>
                <p className="font-semibold mb-1">{addr.label} {addr.isDefault && <span className="text-xs text-[--color-secondary]">★ Alapértelmezett</span>}</p>
                <p className="text-sm text-[--color-muted]">{addr.name}</p>
                <p className="text-sm text-[--color-muted]">{addr.address}</p>
                <p className="text-sm text-[--color-muted]">{addr.phone}</p>
                <span className="inline-block mt-2 px-2 py-1 bg-[--color-success] text-white text-xs rounded">{addr.zone}</span>
              </div>
              <div className="flex gap-2">
                <button className="text-sm text-[--color-secondary] hover:underline">Szerkesztés</button>
                <button className="text-sm text-[--color-error] hover:underline">Törlés</button>
              </div>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}

function Orders() {
  const orders = [
    { id: '#1042', date: '2026-03-12', status: 'Szállítás', total: 11236, items: 3 },
    { id: '#1041', date: '2026-03-05', status: 'Kézbesítve', total: 8970, items: 2 },
    { id: '#1040', date: '2026-02-28', status: 'Kézbesítve', total: 15420, items: 4 },
  ];

  const statusColors: Record<string, string> = {
    'Új': 'bg-blue-100 text-blue-800',
    'Feldolgozás': 'bg-yellow-100 text-yellow-800',
    'Szállítás': 'bg-purple-100 text-purple-800',
    'Kézbesítve': 'bg-green-100 text-green-800',
  };

  return (
    <div className="bg-white rounded-lg p-6">
      <h2 className="mb-6">Rendeléseim</h2>
      <div className="overflow-x-auto">
        <table className="w-full">
          <thead className="border-b border-[--color-border]">
            <tr className="text-left">
              <th className="pb-3">Szám</th>
              <th className="pb-3">Dátum</th>
              <th className="pb-3">Állapot</th>
              <th className="pb-3">Összeg</th>
              <th className="pb-3"></th>
            </tr>
          </thead>
          <tbody>
            {orders.map((order) => (
              <tr key={order.id} className="border-b border-[--color-border]">
                <td className="py-4 font-mono">{order.id}</td>
                <td className="py-4">{order.date}</td>
                <td className="py-4">
                  <span className={`px-2 py-1 rounded text-xs ${statusColors[order.status] || 'bg-gray-100 text-gray-800'}`}>
                    {order.status}
                  </span>
                </td>
                <td className="py-4">{formatPrice(order.total)}</td>
                <td className="py-4">
                  <button className="text-sm text-[--color-secondary] hover:underline">Részletek</button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
... (3863 chars truncated)
```

### src/app/pages/admin/AdminCoupons.tsx
```
import { useState } from 'react';
import { Plus, X } from 'lucide-react';
import { Button } from '../../components/Button';

interface Coupon {
  id: string;
  code: string;
  type: '%' | 'Ft';
  value: number;
  category: string;
  expiry: string;
  used: number;
  maxUses: number;
  active: boolean;
}

export default function AdminCoupons() {
  const [isEditing, setIsEditing] = useState(false);

  const coupons: Coupon[] = [
    {
      id: '1',
      code: 'ELSO10',
      type: '%',
      value: 10,
      category: 'Minden',
      expiry: '—',
      used: 124,
      maxUses: 0,
      active: true,
    },
    {
      id: '2',
      code: 'NYAR2026',
      type: '%',
      value: 15,
      category: 'Minden',
      expiry: '2026-08-31',
      used: 87,
      maxUses: 500,
      active: true,
    },
    {
      id: '3',
      code: 'BUNDLE20',
      type: '%',
      value: 20,
      category: 'Csomagok',
      expiry: '—',
      used: 42,
      maxUses: 0,
      active: true,
    },
  ];

  return (
    <div className="min-h-screen bg-[--color-background] p-6">
      <div className="max-w-[1280px] mx-auto">
        <div className="flex items-center justify-between mb-8">
          <h1>Kuponok</h1>
          <Button onClick={() => setIsEditing(true)}>
            <Plus className="w-5 h-5 mr-2" />
            Új kupon
          </Button>
        </div>

        {/* DataTable */}
        <div className="bg-white rounded-lg overflow-hidden shadow-sm">
          <table className="w-full">
            <thead className="bg-[--color-background] border-b border-[--color-border]">
              <tr>
                <th className="text-left p-4 font-semibold">Kód</th>
                <th className="text-left p-4 font-semibold">Típus</th>
                <th className="text-left p-4 font-semibold">Érték</th>
                <th className="text-left p-4 font-semibold">Kategória</th>
                <th className="text-left p-4 font-semibold">Lejárat</th>
                <th className="text-left p-4 font-semibold">Felhasználás</th>
                <th className="text-left p-4 font-semibold">Aktív</th>
              </tr>
            </thead>
            <tbody>
              {coupons.map((coupon) => (
                <tr key={coupon.id} className="border-b border-[--color-border] hover:bg-[--color-background]">
                  <td className="p-4 font-semibold" style={{ fontFamily: 'var(--font-mono)' }}>
                    {coupon.code}
                  </td>
                  <td className="p-4">{coupon.type === '%' ? 'Százalék' : 'Fix összeg'}</td>
                  <td className="p-4 font-medium">
                    {coupon.value}
                    {coupon.type}
                  </td>
                  <td className="p-4 text-[--color-muted]">{coupon.category}</td>
                  <td className="p-4 text-[--color-muted]">{coupon.expiry}</td>
                  <td className="p-4">
                    {coupon.used} / {coupon.maxUses === 0 ? '∞' : coupon.maxUses}
                  </td>
                  <td className="p-4">
                    <label className="relative inline-flex items-center cursor-pointer">
                      <input type="checkbox" defaultChecked={coupon.active} className="sr-only peer" />
                      <div className="w-11 h-6 bg-gray-200 peer-focus:outline-none peer-focus:ring-2 peer-focus:ring-[--color-secondary] rounded-full peer peer-checked:after:translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-white after:border-gray-300 after:border after:rounded-full after:h-5 after:w-5 after:transition-all peer-checked:bg-[--color-primary]"></div>
                    </label>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      {/* Create/Edit Modal */}
      {isEditing && (
        <div className="fixed inset-0 bg-black/50 z-50 flex items-center justify-center p-4">
          <div className="bg-white rounded-lg w-full max-w-2xl">
            <div className="border-b border-[--color-border] p-6 flex items-center justify-between">
              <h2>Új kupon</h2>
              <button onClick={() => setIsEditing(false)}>
                <X className="w-6 h-6" />
              </button>
            </div>

            <div className="p-6 space-y-6">
              <div>
                <label className="block mb-2 font-medium">Kuponkód (nagybetűs)</label>
                <input
                  type="text"
                  placeholder="NYAR2026"
                  className="w-full px-4 py-2 border border-[--color-border] rounded-md uppercase"
                  style={{ fontFamily: 'var(--font-mono)' }}
                />
              </div>

              <div className="grid grid-cols-2 gap-4">
                <div>
                  <label className="block mb-2 font-medium">Típus</label>
                  <select className="w-
... (2737 chars truncated)
```

### src/app/pages/admin/AdminDeliveries.tsx
```
import { useState } from 'react';
import { Calendar, Check } from 'lucide-react';
import { Button } from '../../components/Button';

interface Delivery {
  id: string;
  time: string;
  customer: string;
  address: string;
  product: string;
  delivered: boolean;
}

export default function AdminDeliveries() {
  const [selectedDate, setSelectedDate] = useState('2026-03-15');
  const [deliveries, setDeliveries] = useState<Delivery[]>([
    {
      id: '1',
      time: '7:30',
      customer: 'Nagy Petra',
      address: '1075 Budapest, Kazinczy u. 28.',
      product: 'Ethiopia Yirgacheffe — Szemes, 500g',
      delivered: true,
    },
    {
      id: '2',
      time: '8:15',
      customer: 'Kovács András',
      address: '1061 Budapest, Andrássy út 45.',
      product: 'Colombia Huila — Őrölt, 250g',
      delivered: false,
    },
    {
      id: '3',
      time: '8:45',
      customer: 'Szabó Eszter',
      address: '1073 Budapest, Erzsébet krt. 12.',
      product: 'Kenya AA — Szemes, 500g',
      delivered: true,
    },
  ]);

  const morningDeliveries = deliveries.filter((d) => d.time >= '6:00' && d.time < '9:00');
  const forenoonDeliveries = deliveries.filter((d) => d.time >= '9:00' && d.time < '12:00');
  const afternoonDeliveries = deliveries.filter((d) => d.time >= '14:00' && d.time < '17:00');

  const toggleDelivered = (id: string) => {
    setDeliveries((prev) =>
      prev.map((d) => (d.id === id ? { ...d, delivered: !d.delivered } : d))
    );
  };

  const markAllDelivered = () => {
    setDeliveries((prev) => prev.map((d) => ({ ...d, delivered: true })));
  };

  const totalDeliveries = deliveries.length;
  const subscriptionCount = 7; // mock
  const singleOrderCount = 3; // mock
  const budapestCount = 8; // mock
  const outsideCount = 2; // mock

  return (
    <div className="min-h-screen bg-[--color-background] p-6">
      <div className="max-w-[1280px] mx-auto">
        <div className="flex items-center justify-between mb-8">
          <h1>Szállítás</h1>
          <div className="flex items-center gap-3">
            <Calendar className="w-5 h-5 text-[--color-muted]" />
            <input
              type="date"
              value={selectedDate}
              onChange={(e) => setSelectedDate(e.target.value)}
              className="px-4 py-2 border border-[--color-border] rounded-md"
            />
          </div>
        </div>

        {/* Summary Bar */}
        <div className="bg-white rounded-lg p-4 mb-6 flex gap-6 text-sm">
          <div>
            <span className="text-[--color-muted]">Összesen:</span>{' '}
            <span className="font-semibold">{totalDeliveries}</span>
          </div>
          <div className="border-l border-[--color-border] pl-6">
            <span className="text-[--color-muted]">Előfizetés:</span>{' '}
            <span className="font-semibold">{subscriptionCount}</span>
          </div>
          <div className="border-l border-[--color-border] pl-6">
            <span className="text-[--color-muted]">Egyszeri:</span>{' '}
            <span className="font-semibold">{singleOrderCount}</span>
          </div>
          <div className="border-l border-[--color-border] pl-6">
            <span className="text-[--color-muted]">Budapest:</span>{' '}
            <span className="font-semibold">{budapestCount}</span>
          </div>
          <div className="border-l border-[--color-border] pl-6">
            <span className="text-[--color-muted]">+20km:</span>{' '}
            <span className="font-semibold">{outsideCount}</span>
          </div>
          <div className="ml-auto">
            <Button onClick={markAllDelivered}>
              <Check className="w-4 h-4 mr-2" />
              Mind kézbesítve
            </Button>
          </div>
        </div>

        {/* Morning Section */}
        {morningDeliveries.length > 0 && (
          <div className="mb-6">
            <h2 className="mb-4">
              Reggel (6:00-9:00) — {morningDeliveries.length} tétel
            </h2>
            <div className="bg-white rounded-lg overflow-hidden shadow-sm">
              <table className="w-full">
                <thead className="bg-[--color-background] border-b border-[--color-border]">
                  <tr>
                    <th className="text-left p-4 font-semibold w-24">Idő</th>
                    <th className="text-left p-4 font-semibold">Vásárló</th>
                    <th className="text-left p-4 font-semibold">Cím</th>
                    <th className="text-left p-4 font-semibold">Termék + Variáns</th>
                    <th className="text-left p-4 font-semibold w-48">Státusz</th>
                  </tr>
                </thead>
                <tbody>
                  {morningDeliveries.map((delivery) => (
                    <tr key={delivery.id} className="border-b border-[--color-border] hover:bg-[--color-background]">
                      <td className="p-4 font-medium">{delivery.time}</td>
                      <td cla
... (5574 chars truncated)
```

### src/app/pages/admin/AdminGiftCards.tsx
```
import { useState } from 'react';

interface GiftCard {
  id: string;
  code: string;
  originalAmount: number;
  balance: number;
  buyer: string;
  expiry: string;
  status: 'active' | 'expired' | 'depleted';
}

export default function AdminGiftCards() {
  const [activeFilter, setActiveFilter] = useState<'all' | 'balance' | 'depleted' | 'expired'>('all');

  const giftCards: GiftCard[] = [
    {
      id: '1',
      code: 'GC-A4F2-9B8E',
      originalAmount: 10000,
      balance: 7500,
      buyer: 'Kovács András',
      expiry: '2027-03-15',
      status: 'active',
    },
    {
      id: '2',
      code: 'GC-C7D1-3A5F',
      originalAmount: 5000,
      balance: 0,
      buyer: 'Nagy Petra',
      expiry: '2027-01-20',
      status: 'depleted',
    },
    {
      id: '3',
      code: 'GC-B9E6-2F4C',
      originalAmount: 20000,
      balance: 0,
      buyer: 'Szabó Eszter',
      expiry: '2025-12-31',
      status: 'expired',
    },
  ];

  const statusConfig = {
    active: { label: 'Aktív', color: '#16A34A' },
    depleted: { label: 'Felhasználva', color: '#78716C' },
    expired: { label: 'Lejárt', color: '#DC2626' },
  };

  const filteredCards = giftCards.filter((card) => {
    if (activeFilter === 'balance') return card.balance > 0;
    if (activeFilter === 'depleted') return card.balance === 0 && card.status === 'depleted';
    if (activeFilter === 'expired') return card.status === 'expired';
    return true;
  });

  return (
    <div className="min-h-screen bg-[--color-background] p-6">
      <div className="max-w-[1280px] mx-auto">
        <h1 className="mb-8">Ajándékkártyák</h1>

        {/* Tab Filters */}
        <div className="bg-white rounded-lg p-4 mb-6 flex gap-4">
          <button
            onClick={() => setActiveFilter('all')}
            className={`px-4 py-2 rounded-md font-medium transition-colors ${
              activeFilter === 'all'
                ? 'bg-[--color-primary] text-white'
                : 'text-[--color-muted] hover:bg-[--color-background]'
            }`}
          >
            Összes
          </button>
          <button
            onClick={() => setActiveFilter('balance')}
            className={`px-4 py-2 rounded-md font-medium transition-colors ${
              activeFilter === 'balance'
                ? 'bg-[--color-primary] text-white'
                : 'text-[--color-muted] hover:bg-[--color-background]'
            }`}
          >
            Aktív egyenleggel
          </button>
          <button
            onClick={() => setActiveFilter('depleted')}
            className={`px-4 py-2 rounded-md font-medium transition-colors ${
              activeFilter === 'depleted'
                ? 'bg-[--color-primary] text-white'
                : 'text-[--color-muted] hover:bg-[--color-background]'
            }`}
          >
            Felhasználva
          </button>
          <button
            onClick={() => setActiveFilter('expired')}
            className={`px-4 py-2 rounded-md font-medium transition-colors ${
              activeFilter === 'expired'
                ? 'bg-[--color-primary] text-white'
                : 'text-[--color-muted] hover:bg-[--color-background]'
            }`}
          >
            Lejárt
          </button>
        </div>

        {/* DataTable */}
        <div className="bg-white rounded-lg overflow-hidden shadow-sm">
          <table className="w-full">
            <thead className="bg-[--color-background] border-b border-[--color-border]">
              <tr>
                <th className="text-left p-4 font-semibold">Kód</th>
                <th className="text-left p-4 font-semibold">Eredeti összeg</th>
                <th className="text-left p-4 font-semibold">Egyenleg</th>
                <th className="text-left p-4 font-semibold">Vásárló</th>
                <th className="text-left p-4 font-semibold">Lejárat</th>
                <th className="text-left p-4 font-semibold">Státusz</th>
              </tr>
            </thead>
            <tbody>
              {filteredCards.map((card) => (
                <tr key={card.id} className="border-b border-[--color-border] hover:bg-[--color-background]">
                  <td className="p-4" style={{ fontFamily: 'var(--font-mono)' }}>
                    {card.code}
                  </td>
                  <td className="p-4">{card.originalAmount.toLocaleString('hu-HU')} Ft</td>
                  <td className="p-4 font-semibold">
                    {card.balance > 0 ? (
                      <span className="text-[--color-success]">{card.balance.toLocaleString('hu-HU')} Ft</span>
                    ) : (
                      <span className="text-[--color-muted]">0 Ft</span>
                    )}
                  </td>
                  <td className="p-4">{card.buyer}</td>
                  <td className="p-4 text-[--color-muted]">{card.expiry}</td>
                  <td className="p-4">
                    <span
                      className="inline-block 
... (389 chars truncated)
```

### src/app/pages/admin/AdminOrders.tsx
```
import { useState } from 'react';
import { Search, X, Check } from 'lucide-react';
import { Button } from '../../components/Button';

interface Order {
  id: string;
  number: string;
  customer: string;
  date: string;
  total: number;
  status: 'new' | 'processing' | 'packed' | 'shipping' | 'delivered' | 'cancelled';
}

const statusConfig = {
  new: { label: 'Új', color: '#3B82F6' },
  processing: { label: 'Feldolgozás', color: '#EAB308' },
  packed: { label: 'Csomagolva', color: '#F97316' },
  shipping: { label: 'Szállítás', color: '#A855F7' },
  delivered: { label: 'Kézbesítve', color: '#16A34A' },
  cancelled: { label: 'Lemondva', color: '#DC2626' },
};

export default function AdminOrders() {
  const [selectedOrder, setSelectedOrder] = useState<Order | null>(null);

  const orders: Order[] = [
    {
      id: '1',
      number: '#1042',
      customer: 'Nagy Petra',
      date: '2026-03-15 10:24',
      total: 7480,
      status: 'processing',
    },
    {
      id: '2',
      number: '#1041',
      customer: 'Kovács András',
      date: '2026-03-15 09:15',
      total: 12490,
      status: 'packed',
    },
    {
      id: '3',
      number: '#1040',
      customer: 'Szabó Eszter',
      date: '2026-03-14 16:42',
      total: 3490,
      status: 'delivered',
    },
  ];

  return (
    <div className="min-h-screen bg-[--color-background] p-6">
      <div className="max-w-[1280px] mx-auto">
        <h1 className="mb-8">Rendelések</h1>

        {/* Filters */}
        <div className="bg-white rounded-lg p-4 mb-6 flex gap-4">
          <select className="px-4 py-2 border border-[--color-border] rounded-md">
            <option>Minden státusz</option>
            <option>Új</option>
            <option>Feldolgozás</option>
            <option>Kézbesítve</option>
          </select>
          <input
            type="date"
            className="px-4 py-2 border border-[--color-border] rounded-md"
            placeholder="Dátum-tól"
          />
          <input
            type="date"
            className="px-4 py-2 border border-[--color-border] rounded-md"
            placeholder="Dátum-ig"
          />
          <div className="flex-1 relative">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-5 h-5 text-[--color-muted]" />
            <input
              type="text"
              placeholder="Rendelésszám vagy vásárló neve..."
              className="w-full pl-10 pr-4 py-2 border border-[--color-border] rounded-md"
            />
          </div>
        </div>

        {/* DataTable */}
        <div className="bg-white rounded-lg overflow-hidden shadow-sm">
          <table className="w-full">
            <thead className="bg-[--color-background] border-b border-[--color-border]">
              <tr>
                <th className="text-left p-4 font-semibold">Szám</th>
                <th className="text-left p-4 font-semibold">Vásárló</th>
                <th className="text-left p-4 font-semibold">Dátum</th>
                <th className="text-left p-4 font-semibold">Összeg</th>
                <th className="text-left p-4 font-semibold">Állapot</th>
                <th className="text-left p-4 font-semibold">Részletek</th>
              </tr>
            </thead>
            <tbody>
              {orders.map((order) => (
                <tr key={order.id} className="border-b border-[--color-border] hover:bg-[--color-background]">
                  <td className="p-4" style={{ fontFamily: 'var(--font-mono)' }}>
                    {order.number}
                  </td>
                  <td className="p-4 font-medium">{order.customer}</td>
                  <td className="p-4 text-[--color-muted]">{order.date}</td>
                  <td className="p-4 font-semibold">{order.total.toLocaleString('hu-HU')} Ft</td>
                  <td className="p-4">
                    <span
                      className="inline-block px-3 py-1 rounded text-xs font-medium text-white"
                      style={{ backgroundColor: statusConfig[order.status].color }}
                    >
                      {statusConfig[order.status].label}
                    </span>
                  </td>
                  <td className="p-4">
                    <button
                      onClick={() => setSelectedOrder(order)}
                      className="text-[--color-secondary] hover:underline font-medium"
                    >
                      Megtekintés
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      {/* Order Detail Slide-in Panel */}
      {selectedOrder && (
        <div className="fixed inset-0 bg-black/50 z-50 flex justify-end">
          <div className="bg-white w-full max-w-2xl h-full overflow-auto">
            <div className="sticky top-0 bg-white border-b border-[--color-border] p-6 flex items-center justify-between">
              <div>
            
... (6262 chars truncated)
```

### src/app/pages/admin/AdminProducts.tsx
```
import { useState } from 'react';
import { Search, Plus, Edit2, Trash2, X } from 'lucide-react';
import { Button } from '../../components/Button';

interface Product {
  id: string;
  thumbnail: string;
  name: string;
  category: string;
  basePrice: number;
  stock: number;
  status: 'active' | 'inactive';
}

export default function AdminProducts() {
  const [isEditing, setIsEditing] = useState(false);
  const [activeTab, setActiveTab] = useState<'basic' | 'coffee' | 'variants' | 'seo' | 'crosssell'>('basic');
  const [editingProduct, setEditingProduct] = useState<Product | null>(null);

  // Mock data
  const products: Product[] = [
    {
      id: '1',
      thumbnail: 'https://images.unsplash.com/photo-1772391264887-50a9e650e0fd?w=80&h=80&fit=crop',
      name: 'Ethiopia Yirgacheffe',
      category: 'Kávé',
      basePrice: 2490,
      stock: 45,
      status: 'active',
    },
    {
      id: '2',
      thumbnail: 'https://images.unsplash.com/photo-1772141614991-eea2a95e770c?w=80&h=80&fit=crop',
      name: 'Colombia Huila',
      category: 'Kávé',
      basePrice: 2790,
      stock: 32,
      status: 'active',
    },
    {
      id: '3',
      thumbnail: 'https://images.unsplash.com/photo-1517668808822-9ebb02f2a0e6?w=80&h=80&fit=crop',
      name: 'Hario V60 Glass',
      category: 'Eszköz',
      basePrice: 4990,
      stock: 12,
      status: 'active',
    },
  ];

  const handleEdit = (product: Product) => {
    setEditingProduct(product);
    setIsEditing(true);
  };

  return (
    <div className="min-h-screen bg-[--color-background] p-6">
      <div className="max-w-[1280px] mx-auto">
        <div className="flex items-center justify-between mb-8">
          <h1>Termékek</h1>
          <Button onClick={() => setIsEditing(true)}>
            <Plus className="w-5 h-5 mr-2" />
            Új termék
          </Button>
        </div>

        {/* Filters */}
        <div className="bg-white rounded-lg p-4 mb-6 flex gap-4">
          <select className="px-4 py-2 border border-[--color-border] rounded-md">
            <option>Minden kategória</option>
            <option>Kávé</option>
            <option>Eszköz</option>
            <option>Merch</option>
          </select>
          <select className="px-4 py-2 border border-[--color-border] rounded-md">
            <option>Minden státusz</option>
            <option>Aktív</option>
            <option>Inaktív</option>
          </select>
          <div className="flex-1 relative">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-5 h-5 text-[--color-muted]" />
            <input
              type="text"
              placeholder="Termék keresése..."
              className="w-full pl-10 pr-4 py-2 border border-[--color-border] rounded-md"
            />
          </div>
        </div>

        {/* DataTable */}
        <div className="bg-white rounded-lg overflow-hidden shadow-sm">
          <table className="w-full">
            <thead className="bg-[--color-background] border-b border-[--color-border]">
              <tr>
                <th className="text-left p-4 font-semibold">Kép</th>
                <th className="text-left p-4 font-semibold">Név</th>
                <th className="text-left p-4 font-semibold">Kategória</th>
                <th className="text-left p-4 font-semibold">Alapár</th>
                <th className="text-left p-4 font-semibold">Készlet</th>
                <th className="text-left p-4 font-semibold">Státusz</th>
                <th className="text-left p-4 font-semibold">Műveletek</th>
              </tr>
            </thead>
            <tbody>
              {products.map((product) => (
                <tr key={product.id} className="border-b border-[--color-border] hover:bg-[--color-background]">
                  <td className="p-4">
                    <img src={product.thumbnail} alt="" className="w-10 h-10 rounded object-cover" />
                  </td>
                  <td className="p-4 font-medium">{product.name}</td>
                  <td className="p-4 text-[--color-muted]">{product.category}</td>
                  <td className="p-4">{product.basePrice.toLocaleString('hu-HU')} Ft</td>
                  <td className="p-4">{product.stock} db</td>
                  <td className="p-4">
                    <span
                      className={`inline-block px-3 py-1 rounded text-xs font-medium ${
                        product.status === 'active'
                          ? 'bg-[--color-success] text-white'
                          : 'bg-[--color-muted] text-white'
                      }`}
                    >
                      {product.status === 'active' ? 'Aktív' : 'Inaktív'}
                    </span>
                  </td>
                  <td className="p-4">
                    <div className="flex gap-2">
                      <button
                        onClick={() => handleEdit(product)}
                        className="p-2 hover:bg-[--color-backgroun
... (11475 chars truncated)
```

### src/app/pages/admin/AdminPromoDays.tsx
```
import { useState } from 'react';
import { Plus, X } from 'lucide-react';
import { Button } from '../../components/Button';

interface PromoDay {
  id: string;
  name: string;
  date: string;
  discount: number;
  emailSent: boolean;
  active: boolean;
}

export default function AdminPromoDays() {
  const [isEditing, setIsEditing] = useState(false);

  const promoDays: PromoDay[] = [
    {
      id: '1',
      name: 'Bolt születésnap',
      date: '2026-03-15',
      discount: 20,
      emailSent: true,
      active: true,
    },
    {
      id: '2',
      name: 'Kávé Világnapja',
      date: '2026-10-01',
      discount: 15,
      emailSent: false,
      active: true,
    },
  ];

  return (
    <div className="min-h-screen bg-[--color-background] p-6">
      <div className="max-w-[1280px] mx-auto">
        <div className="flex items-center justify-between mb-8">
          <h1>Promóciós napok</h1>
          <Button onClick={() => setIsEditing(true)}>
            <Plus className="w-5 h-5 mr-2" />
            Új promóciós nap
          </Button>
        </div>

        <div className="bg-white rounded-lg overflow-hidden shadow-sm">
          <table className="w-full">
            <thead className="bg-[--color-background] border-b border-[--color-border]">
              <tr>
                <th className="text-left p-4 font-semibold">Név</th>
                <th className="text-left p-4 font-semibold">Dátum</th>
                <th className="text-left p-4 font-semibold">Kedvezmény</th>
                <th className="text-left p-4 font-semibold">Email elküldve</th>
                <th className="text-left p-4 font-semibold">Aktív</th>
              </tr>
            </thead>
            <tbody>
              {promoDays.map((promo) => (
                <tr key={promo.id} className="border-b border-[--color-border] hover:bg-[--color-background]">
                  <td className="p-4 font-medium">{promo.name}</td>
                  <td className="p-4">{promo.date}</td>
                  <td className="p-4 font-semibold text-[--color-secondary]">{promo.discount}%</td>
                  <td className="p-4">
                    {promo.emailSent ? (
                      <span className="text-[--color-success]">✓ Igen</span>
                    ) : (
                      <span className="text-[--color-muted]">Nem</span>
                    )}
                  </td>
                  <td className="p-4">
                    <label className="relative inline-flex items-center cursor-pointer">
                      <input type="checkbox" defaultChecked={promo.active} className="sr-only peer" />
                      <div className="w-11 h-6 bg-gray-200 peer-focus:outline-none peer-focus:ring-2 peer-focus:ring-[--color-secondary] rounded-full peer peer-checked:after:translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-white after:border-gray-300 after:border after:rounded-full after:h-5 after:w-5 after:transition-all peer-checked:bg-[--color-primary]"></div>
                    </label>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      {isEditing && (
        <div className="fixed inset-0 bg-black/50 z-50 flex items-center justify-center p-4">
          <div className="bg-white rounded-lg w-full max-w-2xl">
            <div className="border-b border-[--color-border] p-6 flex items-center justify-between">
              <h2>Új promóciós nap</h2>
              <button onClick={() => setIsEditing(false)}>
                <X className="w-6 h-6" />
              </button>
            </div>

            <div className="p-6 space-y-6">
              <div className="grid grid-cols-2 gap-4">
                <div>
                  <label className="block mb-2 font-medium">Név (HU)</label>
                  <input type="text" className="w-full px-4 py-2 border border-[--color-border] rounded-md" />
                </div>
                <div>
                  <label className="block mb-2 font-medium">Név (EN)</label>
                  <input type="text" className="w-full px-4 py-2 border border-[--color-border] rounded-md" />
                </div>
              </div>

              <div className="grid grid-cols-2 gap-4">
                <div>
                  <label className="block mb-2 font-medium">Dátum</label>
                  <input type="date" className="w-full px-4 py-2 border border-[--color-border] rounded-md" />
                </div>
                <div>
                  <label className="block mb-2 font-medium">Kedvezmény (%)</label>
                  <input type="number" className="w-full px-4 py-2 border border-[--color-border] rounded-md" />
                </div>
              </div>

              <div>
                <label className="block mb-2 font-medium">Banner szöveg (HU)</label>
                <textarea rows={3} className="w-full px-4
... (1130 chars truncated)
```

### src/app/pages/admin/AdminReviews.tsx
```
import { useState } from 'react';
import { ChevronDown, ChevronUp } from 'lucide-react';
import { Button } from '../../components/Button';

interface Review {
  id: string;
  stars: number;
  product: string;
  user: string;
  title: string;
  text: string;
  status: 'new' | 'approved' | 'rejected';
  date: string;
}

export default function AdminReviews() {
  const [expandedId, setExpandedId] = useState<string | null>(null);

  const reviews: Review[] = [
    {
      id: '1',
      stars: 5,
      product: 'Ethiopia Yirgacheffe',
      user: 'Nagy Petra',
      title: 'Fantasztikus minőség!',
      text: 'Az Ethiopia Yirgacheffe a kedvencem, olyan virágos és citrusos ízvilága van. Minden reggel ezzel kezdem a napot.',
      status: 'new',
      date: '2026-03-14',
    },
    {
      id: '2',
      stars: 5,
      product: 'Colombia Huila',
      user: 'Kovács András',
      title: 'Kiváló csomagolás',
      text: 'A szállítás mindig pontos, a csomagolás gyönyörű. Ajándékba is gyakran veszem.',
      status: 'approved',
      date: '2026-03-12',
    },
  ];

  const statusConfig = {
    new: { label: 'Új', color: '#3B82F6' },
    approved: { label: 'Elfogadva', color: '#16A34A' },
    rejected: { label: 'Elutasítva', color: '#DC2626' },
  };

  return (
    <div className="min-h-screen bg-[--color-background] p-6">
      <div className="max-w-[1280px] mx-auto">
        <h1 className="mb-8">Értékelések</h1>

        {/* Filters */}
        <div className="bg-white rounded-lg p-4 mb-6 flex gap-4">
          <select className="px-4 py-2 border border-[--color-border] rounded-md">
            <option>Minden státusz</option>
            <option>Új</option>
            <option>Elfogadva</option>
            <option>Elutasítva</option>
          </select>
          <select className="px-4 py-2 border border-[--color-border] rounded-md">
            <option>Min. csillag</option>
            <option>5 csillag</option>
            <option>4+ csillag</option>
            <option>3+ csillag</option>
          </select>
          <select className="px-4 py-2 border border-[--color-border] rounded-md flex-1">
            <option>Minden termék</option>
            <option>Ethiopia Yirgacheffe</option>
            <option>Colombia Huila</option>
          </select>
        </div>

        {/* DataTable */}
        <div className="bg-white rounded-lg overflow-hidden shadow-sm">
          <table className="w-full">
            <thead className="bg-[--color-background] border-b border-[--color-border]">
              <tr>
                <th className="text-left p-4 font-semibold w-24">★</th>
                <th className="text-left p-4 font-semibold">Termék</th>
                <th className="text-left p-4 font-semibold">Felhasználó</th>
                <th className="text-left p-4 font-semibold">Cím</th>
                <th className="text-left p-4 font-semibold">Státusz</th>
                <th className="text-left p-4 font-semibold">Dátum</th>
                <th className="text-left p-4 font-semibold w-20"></th>
              </tr>
            </thead>
            <tbody>
              {reviews.map((review) => (
                <>
                  <tr
                    key={review.id}
                    className="border-b border-[--color-border] hover:bg-[--color-background] cursor-pointer"
                    onClick={() => setExpandedId(expandedId === review.id ? null : review.id)}
                  >
                    <td className="p-4">
                      <div className="flex gap-1">
                        {[...Array(review.stars)].map((_, i) => (
                          <span key={i} className="text-[--color-secondary]">
                            ★
                          </span>
                        ))}
                      </div>
                    </td>
                    <td className="p-4 font-medium">{review.product}</td>
                    <td className="p-4">{review.user}</td>
                    <td className="p-4 text-[--color-muted] truncate max-w-xs">{review.title}</td>
                    <td className="p-4">
                      <span
                        className="inline-block px-3 py-1 rounded text-xs font-medium text-white"
                        style={{ backgroundColor: statusConfig[review.status].color }}
                      >
                        {statusConfig[review.status].label}
                      </span>
                    </td>
                    <td className="p-4 text-[--color-muted]">{review.date}</td>
                    <td className="p-4">
                      {expandedId === review.id ? (
                        <ChevronUp className="w-5 h-5 text-[--color-muted]" />
                      ) : (
                        <ChevronDown className="w-5 h-5 text-[--color-muted]" />
                      )}
                    </td>
                  </tr>
                  {expandedId === review.id && (
                    <tr>
                      <
... (3482 chars truncated)
```

### src/app/pages/admin/AdminStories.tsx
```
import { useState } from 'react';
import { Plus, X, Edit2 } from 'lucide-react';
import { Button } from '../../components/Button';

interface Story {
  id: string;
  title: string;
  category: string;
  status: 'draft' | 'published';
  date: string;
}

export default function AdminStories() {
  const [isEditing, setIsEditing] = useState(false);
  const [contentLang, setContentLang] = useState<'hu' | 'en'>('hu');

  const stories: Story[] = [
    {
      id: '1',
      title: 'Yirgacheffe: A kávé szülőföldje',
      category: 'Eredet',
      status: 'published',
      date: '2026-03-10',
    },
    {
      id: '2',
      title: 'Tökéletes főzési útmutató',
      category: 'Főzés',
      status: 'draft',
      date: '2026-03-08',
    },
  ];

  return (
    <div className="min-h-screen bg-[--color-background] p-6">
      <div className="max-w-[1280px] mx-auto">
        <div className="flex items-center justify-between mb-8">
          <h1>Sztorik</h1>
          <Button onClick={() => setIsEditing(true)}>
            <Plus className="w-5 h-5 mr-2" />
            Új sztori
          </Button>
        </div>

        {/* DataTable */}
        <div className="bg-white rounded-lg overflow-hidden shadow-sm">
          <table className="w-full">
            <thead className="bg-[--color-background] border-b border-[--color-border]">
              <tr>
                <th className="text-left p-4 font-semibold">Cím</th>
                <th className="text-left p-4 font-semibold">Kategória</th>
                <th className="text-left p-4 font-semibold">Státusz</th>
                <th className="text-left p-4 font-semibold">Dátum</th>
                <th className="text-left p-4 font-semibold">Szerkesztés</th>
              </tr>
            </thead>
            <tbody>
              {stories.map((story) => (
                <tr key={story.id} className="border-b border-[--color-border] hover:bg-[--color-background]">
                  <td className="p-4 font-medium">{story.title}</td>
                  <td className="p-4">{story.category}</td>
                  <td className="p-4">
                    <span
                      className={`inline-block px-3 py-1 rounded text-xs font-medium text-white ${
                        story.status === 'published' ? 'bg-[--color-success]' : 'bg-[--color-muted]'
                      }`}
                    >
                      {story.status === 'published' ? 'Publikált' : 'Vázlat'}
                    </span>
                  </td>
                  <td className="p-4 text-[--color-muted]">{story.date}</td>
                  <td className="p-4">
                    <button onClick={() => setIsEditing(true)} className="p-2 hover:bg-[--color-background] rounded">
                      <Edit2 className="w-4 h-4 text-[--color-secondary]" />
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      {/* Story Editor Modal */}
      {isEditing && (
        <div className="fixed inset-0 bg-black/50 z-50 flex items-center justify-center p-4">
          <div className="bg-white rounded-lg w-full max-w-4xl max-h-[90vh] overflow-auto">
            <div className="sticky top-0 bg-white border-b border-[--color-border] p-6 flex items-center justify-between">
              <h2>Új sztori</h2>
              <button onClick={() => setIsEditing(false)}>
                <X className="w-6 h-6" />
              </button>
            </div>

            <div className="p-6 space-y-6">
              {/* Language Tabs */}
              <div className="flex gap-4 border-b border-[--color-border]">
                <button
                  onClick={() => setContentLang('hu')}
                  className={`pb-2 px-4 border-b-2 transition-colors ${
                    contentLang === 'hu'
                      ? 'border-[--color-secondary] text-[--color-secondary] font-medium'
                      : 'border-transparent text-[--color-muted]'
                  }`}
                >
                  Magyar
                </button>
                <button
                  onClick={() => setContentLang('en')}
                  className={`pb-2 px-4 border-b-2 transition-colors ${
                    contentLang === 'en'
                      ? 'border-[--color-secondary] text-[--color-secondary] font-medium'
                      : 'border-transparent text-[--color-muted]'
                  }`}
                >
                  English
                </button>
              </div>

              <div className="grid grid-cols-2 gap-4">
                <div>
                  <label className="block mb-2 font-medium">Cím (HU)</label>
                  <input type="text" className="w-full px-4 py-2 border border-[--color-border] rounded-md" />
                </div>
                <div>
                  <label className="block mb-2 font-medium">Cím (EN)</label>
                  <input t
... (3865 chars truncated)
```

### src/app/pages/admin/AdminSubscriptions.tsx
```
import { Button } from '../../components/Button';

interface Subscription {
  id: string;
  customer: string;
  coffee: string;
  frequency: string;
  nextDelivery: string;
  status: 'active' | 'paused' | 'cancelled';
}

export default function AdminSubscriptions() {
  const subscriptions: Subscription[] = [
    {
      id: '1',
      customer: 'Nagy Petra',
      coffee: 'Ethiopia Yirgacheffe — Szemes, 500g',
      frequency: 'Naponta',
      nextDelivery: '2026-03-16 (holnap)',
      status: 'active',
    },
    {
      id: '2',
      customer: 'Kovács András',
      coffee: 'Colombia Huila — Őrölt, 250g',
      frequency: 'Hetente',
      nextDelivery: '2026-03-20',
      status: 'paused',
    },
    {
      id: '3',
      customer: 'Szabó Eszter',
      coffee: 'Kenya AA — Szemes, 500g',
      frequency: 'Kéthetente',
      nextDelivery: '—',
      status: 'cancelled',
    },
  ];

  const statusConfig = {
    active: { label: 'Aktív', color: '#16A34A' },
    paused: { label: 'Szüneteltetve', color: '#EAB308' },
    cancelled: { label: 'Lemondva', color: '#DC2626' },
  };

  return (
    <div className="min-h-screen bg-[--color-background] p-6">
      <div className="max-w-[1280px] mx-auto">
        <h1 className="mb-8">Előfizetések</h1>

        <div className="bg-white rounded-lg overflow-hidden shadow-sm">
          <table className="w-full">
            <thead className="bg-[--color-background] border-b border-[--color-border]">
              <tr>
                <th className="text-left p-4 font-semibold">Vásárló</th>
                <th className="text-left p-4 font-semibold">Kávé</th>
                <th className="text-left p-4 font-semibold">Gyakoriság</th>
                <th className="text-left p-4 font-semibold">Következő szállítás</th>
                <th className="text-left p-4 font-semibold">Státusz</th>
                <th className="text-left p-4 font-semibold">Műveletek</th>
              </tr>
            </thead>
            <tbody>
              {subscriptions.map((sub) => (
                <tr key={sub.id} className="border-b border-[--color-border] hover:bg-[--color-background]">
                  <td className="p-4 font-medium">{sub.customer}</td>
                  <td className="p-4">{sub.coffee}</td>
                  <td className="p-4">{sub.frequency}</td>
                  <td className="p-4 text-[--color-muted]">{sub.nextDelivery}</td>
                  <td className="p-4">
                    <span
                      className="inline-block px-3 py-1 rounded text-xs font-medium text-white"
                      style={{ backgroundColor: statusConfig[sub.status].color }}
                    >
                      {statusConfig[sub.status].label}
                    </span>
                  </td>
                  <td className="p-4">
                    <div className="flex gap-2">
                      {sub.status === 'active' && (
                        <Button variant="outlined" className="text-sm py-1">
                          Szüneteltetés
                        </Button>
                      )}
                      {sub.status === 'paused' && (
                        <Button variant="outlined" className="text-sm py-1">
                          Aktiválás
                        </Button>
                      )}
                      <Button variant="outlined" className="text-sm py-1">
                        Módosítás
                      </Button>
                      {sub.status !== 'cancelled' && (
                        <button className="px-3 py-1 text-sm bg-[--color-error] text-white rounded-md hover:opacity-90">
                          Lemondás
                        </button>
                      )}
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}

```

### src/app/pages/user/UserAddresses.tsx
```
import { useState } from 'react';
import { Link, useLocation } from 'react-router';
import { User, MapPin, ShoppingBag, Calendar, Heart, Plus, Edit2, Trash2, Star, X } from 'lucide-react';
import { Button } from '../../components/Button';

interface Address {
  id: string;
  label: string;
  name: string;
  postalCode: string;
  city: string;
  street: string;
  phone: string;
  zone: string;
  isDefault: boolean;
}

export default function UserAddresses() {
  const location = useLocation();
  const [addresses, setAddresses] = useState<Address[]>([
    {
      id: '1',
      label: 'Otthon',
      name: 'Nagy Petra',
      postalCode: '1075',
      city: 'Budapest',
      street: 'Kazinczy u. 28.',
      phone: '+36 30 123 4567',
      zone: 'Budapest',
      isDefault: true,
    },
    {
      id: '2',
      label: 'Iroda',
      name: 'Nagy Petra',
      postalCode: '1061',
      city: 'Budapest',
      street: 'Andrássy út 45.',
      phone: '+36 30 123 4567',
      zone: 'Budapest',
      isDefault: false,
    },
  ]);

  const [isEditing, setIsEditing] = useState(false);

  const menuItems = [
    { id: 'adataim', label: 'Adataim', icon: User, path: '/fiokom' },
    { id: 'cimeim', label: 'Címeim', icon: MapPin, path: '/fiokom/cimeim' },
    { id: 'rendeleseim', label: 'Rendeléseim', icon: ShoppingBag, path: '/fiokom/rendeleseim' },
    { id: 'elofizeteseim', label: 'Előfizetéseim', icon: Calendar, path: '/fiokom/elofizeteseim' },
    { id: 'kedvenceim', label: 'Kedvenceim', icon: Heart, path: '/fiokom/kedvenceim' },
  ];

  return (
    <div className="min-h-screen bg-[--color-background] py-12">
      <div className="max-w-[1280px] mx-auto px-4 sm:px-6">
        <div className="flex flex-col md:flex-row gap-8">
          {/* Sidebar */}
          <aside className="hidden md:block w-64 shrink-0">
            <div className="bg-white rounded-lg p-6 shadow-sm">
              <div className="flex flex-col items-center mb-6">
                <div className="w-20 h-20 bg-[--color-background] rounded-full flex items-center justify-center mb-3">
                  <User className="w-10 h-10 text-[--color-muted]" />
                </div>
                <h3 className="font-semibold">Nagy Petra</h3>
                <p className="text-sm text-[--color-muted]">nagy.petra@email.com</p>
              </div>
              <nav className="space-y-1">
                {menuItems.map((item) => {
                  const Icon = item.icon;
                  const isActive = location.pathname === item.path;
                  return (
                    <Link
                      key={item.id}
                      to={item.path}
                      className={`flex items-center gap-3 px-4 py-3 rounded-md transition-colors ${
                        isActive
                          ? 'bg-[--color-primary] text-white'
                          : 'text-[--color-text] hover:bg-[--color-background]'
                      }`}
                    >
                      <Icon className="w-5 h-5" />
                      <span>{item.label}</span>
                    </Link>
                  );
                })}
              </nav>
            </div>
          </aside>

          {/* Main Content */}
          <main className="flex-1">
            <div className="bg-white rounded-lg p-6 md:p-8 shadow-sm">
              <div className="flex items-center justify-between mb-6">
                <h1>Címeim</h1>
                <Button onClick={() => setIsEditing(true)}>
                  <Plus className="w-5 h-5 mr-2" />
                  Új cím
                </Button>
              </div>

              {/* Address Cards */}
              <div className="grid gap-4 md:grid-cols-2">
                {addresses.map((address) => (
                  <div
                    key={address.id}
                    className="border border-[--color-border] rounded-lg p-6 relative hover:border-[--color-secondary] transition-colors"
                  >
                    {address.isDefault && (
                      <div className="absolute top-4 right-4">
                        <Star className="w-5 h-5 text-[--color-secondary] fill-current" />
                      </div>
                    )}
                    <div className="mb-4">
                      <span className="inline-block px-3 py-1 bg-[--color-secondary] text-white text-xs rounded-full mb-2">
                        {address.label}
                      </span>
                      {address.zone && (
                        <span className="inline-block ml-2 px-3 py-1 bg-[--color-background] text-[--color-primary] text-xs rounded-full">
                          {address.zone}
                        </span>
                      )}
                    </div>
                    <p className="font-medium mb-1">{address.name}</p>
                    <p className="text-[--color-muted] text-sm mb-1">
                      {address.postalCode} {address.city}
           
... (3717 chars truncated)
```

### src/app/pages/user/UserProfile.tsx
```
import { useState } from 'react';
import { Link, useLocation } from 'react-router';
import { User, MapPin, ShoppingBag, Calendar, Heart, Lock } from 'lucide-react';
import { Button } from '../../components/Button';

export default function UserProfile() {
  const location = useLocation();
  const [language, setLanguage] = useState('hu');

  const menuItems = [
    { id: 'adataim', label: 'Adataim', icon: User, path: '/fiokom' },
    { id: 'cimeim', label: 'Címeim', icon: MapPin, path: '/fiokom/cimeim' },
    { id: 'rendeleseim', label: 'Rendeléseim', icon: ShoppingBag, path: '/fiokom/rendeleseim' },
    { id: 'elofizeteseim', label: 'Előfizetéseim', icon: Calendar, path: '/fiokom/elofizeteseim' },
    { id: 'kedvenceim', label: 'Kedvenceim', icon: Heart, path: '/fiokom/kedvenceim' },
  ];

  return (
    <div className="min-h-screen bg-[--color-background] py-12">
      <div className="max-w-[1280px] mx-auto px-4 sm:px-6">
        <div className="flex flex-col md:flex-row gap-8">
          {/* Sidebar - Desktop */}
          <aside className="hidden md:block w-64 shrink-0">
            <div className="bg-white rounded-lg p-6 shadow-sm">
              <div className="flex flex-col items-center mb-6">
                <div className="w-20 h-20 bg-[--color-background] rounded-full flex items-center justify-center mb-3">
                  <User className="w-10 h-10 text-[--color-muted]" />
                </div>
                <h3 className="font-semibold">Nagy Petra</h3>
                <p className="text-sm text-[--color-muted]">nagy.petra@email.com</p>
              </div>
              <nav className="space-y-1">
                {menuItems.map((item) => {
                  const Icon = item.icon;
                  const isActive = location.pathname === item.path;
                  return (
                    <Link
                      key={item.id}
                      to={item.path}
                      className={`flex items-center gap-3 px-4 py-3 rounded-md transition-colors ${
                        isActive
                          ? 'bg-[--color-primary] text-white'
                          : 'text-[--color-text] hover:bg-[--color-background]'
                      }`}
                    >
                      <Icon className="w-5 h-5" />
                      <span>{item.label}</span>
                    </Link>
                  );
                })}
              </nav>
            </div>
          </aside>

          {/* Mobile Menu Tabs */}
          <div className="md:hidden overflow-x-auto">
            <div className="flex gap-2 pb-2">
              {menuItems.map((item) => {
                const Icon = item.icon;
                const isActive = location.pathname === item.path;
                return (
                  <Link
                    key={item.id}
                    to={item.path}
                    className={`flex items-center gap-2 px-4 py-2 rounded-md whitespace-nowrap transition-colors ${
                      isActive
                        ? 'bg-[--color-primary] text-white'
                        : 'bg-white text-[--color-text] border border-[--color-border]'
                    }`}
                  >
                    <Icon className="w-4 h-4" />
                    <span className="text-sm">{item.label}</span>
                  </Link>
                );
              })}
            </div>
          </div>

          {/* Main Content */}
          <main className="flex-1">
            <div className="bg-white rounded-lg p-6 md:p-8 shadow-sm">
              <h1 className="mb-6">Adataim</h1>

              <form className="space-y-6">
                <div>
                  <label className="block mb-2 font-medium">Név</label>
                  <input
                    type="text"
                    defaultValue="Nagy Petra"
                    className="w-full px-4 py-2 border border-[--color-border] rounded-md"
                  />
                </div>

                <div>
                  <label className="block mb-2 font-medium">Email cím</label>
                  <div className="relative">
                    <input
                      type="email"
                      defaultValue="nagy.petra@email.com"
                      readOnly
                      className="w-full px-4 py-2 pr-10 border border-[--color-border] rounded-md bg-[--color-background]"
                    />
                    <Lock className="absolute right-3 top-1/2 -translate-y-1/2 w-5 h-5 text-[--color-muted]" />
                  </div>
                  <p className="text-sm text-[--color-muted] mt-1">
                    Az email címed megváltoztatásához lépj kapcsolatba az ügyfélszolgálattal.
                  </p>
                </div>

                <div>
                  <label className="block mb-2 font-medium">Nyelv</label>
                  <div className="flex gap-4">
                    <label className="flex items-center gap-2 cursor-pointer">
  
... (2199 chars truncated)
```

### src/app/routes.tsx
```
import { createBrowserRouter } from "react-router";
import Home from "./pages/Home";
import ProductCatalog from "./pages/ProductCatalog";
import ProductDetail from "./pages/ProductDetail";
import Cart from "./pages/Cart";
import Checkout from "./pages/Checkout";
import SubscriptionWizard from "./pages/SubscriptionWizard";
import UserDashboard from "./pages/UserDashboard";
import AdminDashboard from "./pages/AdminDashboard";
import Login from "./pages/Login";
import Register from "./pages/Register";
import Stories from "./pages/Stories";
import StoryDetail from "./pages/StoryDetail";
import NotFound from "./pages/NotFound";
import Layout from "./components/Layout";

// Admin Pages
import AdminProducts from "./pages/admin/AdminProducts";
import AdminOrders from "./pages/admin/AdminOrders";
import AdminDeliveries from "./pages/admin/AdminDeliveries";
import AdminCoupons from "./pages/admin/AdminCoupons";
import AdminPromoDays from "./pages/admin/AdminPromoDays";
import AdminGiftCards from "./pages/admin/AdminGiftCards";
import AdminReviews from "./pages/admin/AdminReviews";
import AdminStories from "./pages/admin/AdminStories";
import AdminSubscriptions from "./pages/admin/AdminSubscriptions";

// User Pages
import UserProfile from "./pages/user/UserProfile";
import UserAddresses from "./pages/user/UserAddresses";

export const router = createBrowserRouter([
  {
    path: "/",
    Component: Layout,
    children: [
      { index: true, Component: Home },
      { path: "kavek", Component: ProductCatalog },
      { path: "kavek/:id", Component: ProductDetail },
      { path: "kosar", Component: Cart },
      { path: "penztar", Component: Checkout },
      { path: "elofizetés", Component: SubscriptionWizard },
      { path: "fiokom", Component: UserProfile },
      { path: "fiokom/cimeim", Component: UserAddresses },
      { path: "admin", Component: AdminDashboard },
      { path: "admin/termekek", Component: AdminProducts },
      { path: "admin/rendelesek", Component: AdminOrders },
      { path: "admin/szallitas", Component: AdminDeliveries },
      { path: "admin/kuponok", Component: AdminCoupons },
      { path: "admin/promo-napok", Component: AdminPromoDays },
      { path: "admin/ajandekkartyak", Component: AdminGiftCards },
      { path: "admin/ertekelesek", Component: AdminReviews },
      { path: "admin/sztorik", Component: AdminStories },
      { path: "admin/elofizetesek", Component: AdminSubscriptions },
      { path: "sztorik", Component: Stories },
      { path: "sztorik/:slug", Component: StoryDetail },
      { path: "belepes", Component: Login },
      { path: "regisztracio", Component: Register },
      { path: "*", Component: NotFound },
    ],
  },
]);
```

### src/imports/pasted_text/admin-pages.md
```
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
  - Address cards: Label "Otthom", Name, Full addr
... (3531 chars truncated)
```

### src/imports/pasted_text/craftbrew-design-tokens.md
```

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

TESTIMONIALS: 1-column, 3 review cards stack
... (21937 chars truncated)
```

### src/lib/utils.ts
```
import { type ClassValue, clsx } from "clsx";
import { twMerge } from "tailwind-merge";

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}

export function formatPrice(price: number): string {
  return `${price.toLocaleString('hu-HU')} Ft`;
}

```

### src/styles/fonts.css
```
@import url('https://fonts.googleapis.com/css2?family=Playfair+Display:wght@400;600;700&family=Inter:wght@400;500;600&family=JetBrains+Mono:wght@400;500&display=swap');

```

### src/styles/index.css
```
@import './fonts.css';
@import './tailwind.css';
@import './theme.css';

```

### src/styles/tailwind.css
```
@import 'tailwindcss' source(none);
@source '../**/*.{js,ts,jsx,tsx}';

@import 'tw-animate-css';

```

### src/styles/theme.css
```
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

### vite.config.ts
```
import { defineConfig } from 'vite'
import path from 'path'
import tailwindcss from '@tailwindcss/vite'
import react from '@vitejs/plugin-react'

export default defineConfig({
  plugins: [
    // The React and Tailwind plugins are both required for Make, even if
    // Tailwind is not being actively used – do not remove them
    react(),
    tailwindcss(),
  ],
  resolve: {
    alias: {
      // Alias @ to the src directory
      '@': path.resolve(__dirname, './src'),
    },
  },

  // File types to support raw imports. Never add .css, .tsx, or .ts files to this.
  assetsInclude: ['**/*.svg', '**/*.csv'],
})

```

### UI Library Components
*48 shadcn/ui primitives available in `sources/` (not inlined):*

- `src/app/components/ui/accordion.tsx`
- `src/app/components/ui/alert-dialog.tsx`
- `src/app/components/ui/alert.tsx`
- `src/app/components/ui/aspect-ratio.tsx`
- `src/app/components/ui/avatar.tsx`
- `src/app/components/ui/badge.tsx`
- `src/app/components/ui/breadcrumb.tsx`
- `src/app/components/ui/button.tsx`
- `src/app/components/ui/calendar.tsx`
- `src/app/components/ui/card.tsx`
- `src/app/components/ui/carousel.tsx`
- `src/app/components/ui/chart.tsx`
- `src/app/components/ui/checkbox.tsx`
- `src/app/components/ui/collapsible.tsx`
- `src/app/components/ui/command.tsx`
- `src/app/components/ui/context-menu.tsx`
- `src/app/components/ui/dialog.tsx`
- `src/app/components/ui/drawer.tsx`
- `src/app/components/ui/dropdown-menu.tsx`
- `src/app/components/ui/form.tsx`
- `src/app/components/ui/hover-card.tsx`
- `src/app/components/ui/input-otp.tsx`
- `src/app/components/ui/input.tsx`
- `src/app/components/ui/label.tsx`
- `src/app/components/ui/menubar.tsx`
- `src/app/components/ui/navigation-menu.tsx`
- `src/app/components/ui/pagination.tsx`
- `src/app/components/ui/popover.tsx`
- `src/app/components/ui/progress.tsx`
- `src/app/components/ui/radio-group.tsx`
- `src/app/components/ui/resizable.tsx`
- `src/app/components/ui/scroll-area.tsx`
- `src/app/components/ui/select.tsx`
- `src/app/components/ui/separator.tsx`
- `src/app/components/ui/sheet.tsx`
- `src/app/components/ui/sidebar.tsx`
- `src/app/components/ui/skeleton.tsx`
- `src/app/components/ui/slider.tsx`
- `src/app/components/ui/sonner.tsx`
- `src/app/components/ui/switch.tsx`
- `src/app/components/ui/table.tsx`
- `src/app/components/ui/tabs.tsx`
- `src/app/components/ui/textarea.tsx`
- `src/app/components/ui/toggle-group.tsx`
- `src/app/components/ui/toggle.tsx`
- `src/app/components/ui/tooltip.tsx`
- `src/app/components/ui/use-mobile.ts`
- `src/app/components/ui/utils.ts`