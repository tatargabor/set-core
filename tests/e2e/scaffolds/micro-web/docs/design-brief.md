# Design Brief

Per-page visual specifications for implementing agents.
Uses shadcn/ui components with the default slate theme.
Each page section describes layout, components, and responsive behavior.

## Page: Home

Container: 1024px max-width, centered, px-6
Background: bg-background

Sections (top to bottom):

1. Header Component (shared across all pages)
   - Sticky, z-50, border-b border-border
   - Height: h-16
   - Layout: flex justify-between items-center
   - Left: Site title "Micro Web" as link to /, font-bold text-xl
   - Right: Navigation links (Home, About, Blog, Contact)
   - Mobile (< md): hamburger icon → Sheet component with vertical nav links
   - Active page: text-primary font-medium

2. Hero Section
   - Padding: py-24
   - Layout: text-center
   - H1: "Welcome to Micro Web" — text-4xl font-bold tracking-tight
   - Subtitle: text-muted-foreground text-lg, max-w-2xl mx-auto
   - CTA: Button variant="default" size="lg" → links to /about

3. Features Grid
   - Padding: py-16
   - Grid: 3 columns (md:grid-cols-3), gap-6, single column on mobile
   - Each item: Card component
     * CardHeader: icon (lucide-react) + CardTitle
     * CardContent: CardDescription text
   - Items: "Fast", "Reliable", "Simple" (placeholder features)

4. Footer
   - Border-t border-border, py-8
   - text-center text-sm text-muted-foreground
   - "Built with Next.js and shadcn/ui"

## Page: About

Container: 1024px max-width, centered, px-6

Sections:

1. Header (shared component)

2. Page Title
   - Padding: py-12
   - H1: "About Us" — text-3xl font-bold

3. Description
   - max-w-prose
   - text-muted-foreground leading-relaxed
   - 2-3 paragraphs about the company

4. Team Section
   - Padding: py-12
   - H2: "Our Team" — text-2xl font-semibold mb-8
   - Grid: 3 columns (md:grid-cols-3), gap-6, single column on mobile
   - Each team member: Card component
     * Avatar placeholder: div w-16 h-16 rounded-full bg-muted mx-auto
     * CardHeader: CardTitle = name (centered)
     * CardContent: CardDescription = role (centered)
   - Members: "Alice Chen — Engineering", "Bob Smith — Design", "Carol Davis — Product"

5. Footer (shared component)

## Page: Contact

Container: 1024px max-width, centered, px-6

Sections:

1. Header (shared component)

2. Page Title
   - Padding: py-12
   - H1: "Contact Us" — text-3xl font-bold
   - Subtitle: text-muted-foreground

3. Contact Form
   - max-w-lg mx-auto
   - Card component wrapping the form
   - CardContent with space-y-4:
     * Label + Input: "Name" — required
     * Label + Input: "Email" — required, type="email"
     * Label + Textarea: "Message" — required, min 10 chars
   - Validation errors: text-sm text-destructive below each field
   - CardFooter: Button variant="default" w-full — "Send Message"
   - On valid submit: console.log data, show success toast or alert

4. Footer (shared component)

## Page: Blog

Container: 1024px max-width, centered, px-6

Sections:

1. Header (shared component)

2. Page Title
   - Padding: py-12
   - H1: "Blog" — text-3xl font-bold

3. Blog Post List
   - space-y-6
   - 3 hardcoded posts, each as Card component:
     * CardHeader:
       - CardTitle: post title as link to /blog/[slug] — hover:underline
       - CardDescription: date in text-sm text-muted-foreground
     * CardContent: excerpt text (2-3 lines)
   - Posts:
     * "Getting Started with Next.js" — 2024-01-15
     * "Understanding TypeScript" — 2024-01-10
     * "Tailwind CSS Tips" — 2024-01-05

4. Footer (shared component)

## Page: BlogDetail

Route: /blog/[slug]
Container: 1024px max-width, centered, px-6

Sections:

1. Header (shared component)

2. Back Link
   - py-4
   - Link to /blog with "← Back to Blog" — text-sm text-muted-foreground hover:text-foreground

3. Article Content
   - max-w-prose mx-auto
   - H1: post title — text-3xl font-bold mb-2
   - Date: text-sm text-muted-foreground mb-8
   - Body: prose styling (leading-relaxed, space-y-4 paragraphs)
   - Hardcoded content for each of the 3 slugs
   - Invalid slug: notFound() → Next.js 404 page

4. Footer (shared component)

## Shared Components

### Header
- Used on every page
- Responsive: full nav on md+, Sheet hamburger on mobile
- Components: NavigationMenu or custom nav, Sheet, Button (ghost, icon-only for hamburger)
- Icons: Menu (hamburger), X (close)

### Footer
- Used on every page
- Minimal: single line centered text
