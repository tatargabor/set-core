# Design System

Source: shadcn/ui default theme (slate)
Format: oklch color space, CSS custom properties

## Design Tokens

### Colors

Light mode:
- background: oklch(1 0 0) — white
- foreground: oklch(0.145 0 0) — near-black
- primary: oklch(0.205 0 0) — dark slate (buttons, links)
- primary-foreground: oklch(0.985 0 0) — white text on primary
- secondary: oklch(0.97 0 0) — light gray
- secondary-foreground: oklch(0.205 0 0) — dark text on secondary
- muted: oklch(0.97 0 0) — subtle backgrounds
- muted-foreground: oklch(0.556 0 0) — subdued text
- accent: oklch(0.97 0 0) — hover/active states
- accent-foreground: oklch(0.205 0 0)
- destructive: oklch(0.577 0.245 27.325) — red for errors/delete
- border: oklch(0.922 0 0) — light border
- input: oklch(0.922 0 0) — form input borders
- ring: oklch(0.708 0 0) — focus rings

Dark mode:
- background: oklch(0.145 0 0) — near-black
- foreground: oklch(0.985 0 0) — white
- primary: oklch(0.922 0 0) — light for dark bg
- primary-foreground: oklch(0.205 0 0) — dark text
- destructive: oklch(0.704 0.191 22.216) — brighter red on dark

### Typography

- Font body: system font stack (Inter when available)
- Font mono: system monospace
- text-sm: 0.875rem / 1.25rem
- text-base: 1rem / 1.5rem
- text-lg: 1.125rem / 1.75rem
- text-xl: 1.25rem / 1.75rem
- text-2xl: 1.5rem / 2rem
- text-3xl: 1.875rem / 2.25rem
- text-4xl: 2.25rem / 2.5rem

### Spacing

- Tailwind default scale (4px base)
- Page padding: px-6 (1.5rem)
- Section padding: py-12 to py-24
- Card padding: p-6
- Grid gap: gap-6 (1.5rem)
- Container: max-w-screen-lg (1024px)

### Border Radius

- radius: 0.625rem (10px)
- radius-sm: 0.375rem (6px)
- radius-md: 0.5rem (8px)
- radius-lg: 0.625rem (10px)
- radius-xl: 1.025rem (16px)

### Shadows

- Tailwind defaults (shadow-sm, shadow, shadow-md)
- Cards: no shadow by default, border-border instead

## Component Hierarchy

- Button (default, ghost, outline, destructive)
- Card (CardHeader, CardTitle, CardDescription, CardContent, CardFooter)
- Input
- Textarea
- Label
- Sheet (SheetTrigger, SheetContent) — mobile navigation
- NavigationMenu — desktop navigation
