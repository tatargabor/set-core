# v0.app Prompt Package — Micro Web Design

Copy-paste-ready prompts for designing the micro-web reference UI in v0.app.
The end goal is a Next.js 14 + shadcn/ui project that you push to GitHub
(e.g. `github.com/<your-user>/v0-micro-web-design`) and reference from
`scaffold.yaml::design_source.repo`.

## How to use

1. Open [v0.app](https://v0.app) and create a new project named `v0-micro-web-design`
2. Paste **Prompt 1** as the initial prompt — v0 generates the base layout +
   theme + shadcn primitives
3. Iterate on each subsequent prompt to flesh out individual pages
4. Final pass: confirm v0's preview matches your expectations on desktop +
   mobile breakpoints
5. Export → push to GitHub
6. Update `tests/e2e/scaffolds/micro-web/scaffold.yaml::design_source.repo`
   with the real URL

The prompts are intentionally distinctive on UX patterns (CommandDialog,
Sheet, HoverCard, Combobox, etc.) so the design-fidelity gate has clear
signals to track.

---

## Prompt 1 — Initial scaffold + theme + global header

```
Create a Next.js 14 App Router site called "Micro Web" using shadcn/ui with
the slate theme. Tailwind CSS v4. TypeScript. The site has 5 pages:
Home (/), About (/about), Contact (/contact), Blog (/blog), Blog Detail
(/blog/[slug]).

Build a shared site-header component (components/site-header.tsx) and a
shared site-footer component (components/site-footer.tsx) that mount on
every page via app/layout.tsx.

The site-header has these elements (left to right):
- Site title "Micro Web" as a Link to / — font-bold text-xl
- Desktop nav links: Home, About, Blog, Contact — text-sm, with active page
  highlighted text-primary font-medium
- A "Search…" button on the right that opens a Cmd+K command palette. The
  button shows a kbd badge with ⌘K. Clicking it OR pressing ⌘K / Ctrl+K
  globally opens a CommandDialog.
- On viewports below md, the desktop nav links collapse into a hamburger
  Menu icon button. Tapping it opens a Sheet drawer FROM THE LEFT (use
  side="left") with vertical nav links inside SheetContent. Include the
  ⌘K trigger inside the Sheet drawer too.

The CommandDialog content (components/command-palette.tsx, exported and
used by site-header):
- CommandInput at top with placeholder "Search pages, posts…"
- CommandList with three CommandGroups separated by CommandSeparator:
  - "Pages": Home, About, Blog, Contact (each as a CommandItem with a
    lucide icon — House, Info, Newspaper, Mail). On select: navigate via
    next/router.
  - "Recent posts": three placeholder posts (each with a BookOpen icon)
  - "Theme": one CommandItem "Toggle theme" with a Sun/Moon icon
    (placeholder action — no real implementation needed)
- CommandEmpty for no-match state

The site-footer is a single line, border-t, py-6, text-center text-sm
text-muted-foreground: "Built with Next.js and shadcn/ui".

Use slate as the base color. The layout must be responsive: max-width 1024px
container with px-6, sticky header with z-50 and border-b.
```

---

## Prompt 2 — Home page

```
Build app/page.tsx (the Home page). It uses the existing site-header and
site-footer. Sections top to bottom:

1. Hero: py-24, text-center, with H1 "Welcome to Micro Web" (text-4xl
   font-bold tracking-tight), a max-w-2xl mx-auto subtitle "A tiny site
   showcasing distinctive shadcn UX patterns.", and a primary Button
   size="lg" linked to /about with text "Learn more".

2. Features grid: py-16, md:grid-cols-3 gap-6, single column on mobile.
   Three Card components (Card, CardHeader, CardContent, CardDescription).
   Each has a lucide icon in CardHeader, a CardTitle, and a CardDescription:
   - Zap icon, "Fast", "Static-first build with edge caching"
   - ShieldCheck icon, "Reliable", "Type-checked and tested end-to-end"
   - Sparkles icon, "Simple", "No database, no auth — just five pages"

3. Newsletter signup: py-12, centered, with H2 "Stay in the loop" and a
   single primary Button "Subscribe to updates". Clicking the button opens
   a Sheet from the RIGHT (side="right") containing:
   - SheetHeader with SheetTitle "Subscribe" and SheetDescription
     "Occasional emails about new posts. No spam."
   - An Input for email + a primary Button "Subscribe"
   - On submit: console.log + show a toast (sonner) "Thanks for
     subscribing!" and close the Sheet
   The Sheet trigger button MUST be a SheetTrigger asChild wrapper around
   the visible Subscribe button. Do NOT use Dialog — must be Sheet.

The whole page lives inside the max-w-1024 container.
```

---

## Prompt 3 — About page

```
Build app/about/page.tsx. Sections:

1. Page title: H1 "About Us" — text-3xl font-bold, py-12

2. Description: max-w-prose, text-muted-foreground leading-relaxed,
   2-3 paragraphs of placeholder text about a fictional small dev team.

3. Team section: py-12, with H2 "Our Team" — text-2xl font-semibold mb-8.
   Grid: md:grid-cols-3 gap-6. Three team members. Each member is rendered
   as an Avatar with placeholder initials (use Avatar + AvatarFallback) inside
   a HoverCard:

   - HoverCard wraps the Avatar (HoverCardTrigger asChild)
   - HoverCardContent shows:
     * Larger avatar at top
     * Name (font-bold), role (text-sm text-muted-foreground)
     * 1-2 sentences of bio (text-sm)
     * Two social links as small icon buttons (lucide Github, Twitter)
       — placeholder hrefs are fine

   Members:
   - Alice Chen — Engineering — initials "AC" — bio "Loves TypeScript and
     pour-over coffee."
   - Bob Smith — Design — initials "BS" — bio "Pixel-perfect, but pragmatic."
   - Carol Davis — Product — initials "CD" — bio "Talks to users; ships
     things."

   Use HoverCard, NOT Tooltip. The content shown on hover must be richer
   than a single line of text.
```

---

## Prompt 4 — Contact page (multi-step Dialog wizard)

```
Build app/contact/page.tsx. The page itself is mostly empty:

1. Page title: H1 "Contact" — text-3xl font-bold, py-12
2. Subtitle: text-muted-foreground "We'd love to hear from you."
3. Primary CTA Button "Get in touch" — opens a Dialog (components/
   contact-wizard.tsx).

Build components/contact-wizard.tsx as a Dialog with a 3-step wizard inside.

Use Dialog, DialogTrigger, DialogContent, DialogHeader, DialogTitle,
DialogDescription, DialogFooter. The DialogContent should be max-w-md.

At the top of DialogContent, render a custom stepper indicator (3 steps
horizontally, with the active step filled, completed steps with a check
icon, future steps muted). Use simple flex divs with Badge or custom div
styling. Step labels: "Your details", "What's it about?", "Review".

Step 1 — "Your details":
- Label + Input "Name" (required, min 2 chars)
- Label + Input "Email" (required, must be valid email format)
- Inline error text (text-sm text-destructive) below each invalid field
- Footer: a primary "Next" Button. Disabled until step is valid.

Step 2 — "What's it about?":
- Label + Combobox "Subject" — uses Command-based Combobox pattern. Options
  (CommandItem inside CommandList): "General Inquiry", "Technical Support",
  "Feedback", "Bug Report", "Other". Type-ahead filtering. Required.
- Label + Textarea "Message" (required, min 10 chars)
- Footer: a "Back" Button (variant="outline") and a primary "Next" Button.

Step 3 — "Review":
- Read-only summary of all fields entered (name, email, subject, message)
  in a Card or definition-list layout
- Footer: "Back" Button + primary "Send message" Button

On Send:
- console.log the entire payload
- close the Dialog
- show a sonner toast with title "Message sent" and description
  "We'll get back to you within 2 business days."
- reset the wizard state to step 1

Validation must prevent advancing if the current step's required fields are
invalid. Use react-hook-form + zod for clean validation.

Crucially: this MUST be a single Dialog with internal step state — not three
separate routed pages. The whole flow happens in a modal overlay.
```

---

## Prompt 5 — Blog list page

```
Build app/blog/page.tsx. Sections:

1. Page title: H1 "Blog" — text-3xl font-bold, py-12

2. Filter bar: a single Combobox (NOT two separate Selects) that combines
   search and category filtering:
   - Trigger Button shows current selection or "All posts"
   - PopoverContent contains a Command with CommandInput "Search posts…"
   - CommandList shows two CommandGroups:
     * "Categories": items "All", "Frontend", "Backend", "Tooling" (each
       sets the category filter when selected)
     * "Posts": filtered by typed query (typing narrows the post list)
   - As the user types, the post list below the filter bar reactively
     updates (client-side filtering — no real backend)

3. Post list: space-y-6. Each post renders as a Card:
   - CardHeader: CardTitle is a link to /blog/[slug] — hover:underline. Below
     it, a row with a Badge (category) and a date (text-sm text-muted-foreground).
   - CardContent: excerpt (2-3 lines)
   - Author row at bottom: small Avatar + name. The Avatar is wrapped in a
     HoverCard (same pattern as About page) showing the author's full name,
     role, and 1-line bio.

Hardcoded posts (in lib/posts.ts as an exported array):
- slug "getting-started-with-nextjs", title "Getting Started with Next.js",
  date "2024-01-15", category "Frontend", author "Alice Chen", excerpt
  "An overview of the App Router and Server Components."
- slug "understanding-typescript", title "Understanding TypeScript", date
  "2024-01-10", category "Tooling", author "Bob Smith", excerpt "Why types
  are leverage, not friction."
- slug "tailwind-css-tips", title "Tailwind CSS Tips", date "2024-01-05",
  category "Frontend", author "Carol Davis", excerpt "Five patterns I reach
  for in every project."

Each post has a body (full content as plaintext, ~3-4 paragraphs). Bodies
go in lib/posts.ts too.
```

---

## Prompt 6 — Blog detail page

```
Build app/blog/[slug]/page.tsx using the lib/posts.ts data. Layout:

1. A sticky `Progress` bar at the very top of the viewport (BELOW the site
   header — top: 64px, sticky). Use the shadcn Progress component. As the
   user scrolls through the article, the progress fills 0% → 100%.
   Implement this with a useEffect + scroll listener; clamp to [0, 100].

2. Below the progress bar, a `Breadcrumb` (use shadcn Breadcrumb,
   BreadcrumbList, BreadcrumbItem, BreadcrumbLink, BreadcrumbSeparator):
   "Home / Blog / {category} / {post title}"

3. Article: max-w-prose mx-auto. H1 with the title, then a row with date
   and author byline (Avatar wrapped in HoverCard, same as Blog list). Then
   the body — render plaintext paragraphs with leading-relaxed and space-y-4.

4. Reactions row at end of article (border-t, py-6): three buttons in a
   horizontal flex with gap-2:
   - 👍 button with count (placeholder "12")
   - ❤️ button with count (placeholder "34")
   - Share button — wrapped in a Popover. PopoverTrigger is the share button
     (lucide Share2 icon). PopoverContent shows three options as plain
     buttons stacked vertically: "Share on Twitter", "Share via Email",
     "Copy link". Each option toasts a confirmation on click.

5. "Back to blog" link below the reactions: Link to /blog with text
   "← Back to blog", text-sm text-muted-foreground hover:text-foreground.

Invalid slug: call notFound(). Build a custom app/blog/[slug]/not-found.tsx
that uses an Alert component (variant="destructive") with title "Post not
found" and a Link back to /blog.
```

---

## Prompt 7 — Final pass: a11y, mobile QA, and polish

```
Audit the entire site for:

1. Every interactive button has aria-label or visible text
2. The Cmd+K palette is reachable via keyboard (Tab, Enter, Esc)
3. The Sheet drawer is dismissible via Esc and backdrop click
4. The mobile hamburger sits in the same header position consistently
5. The Combobox on Blog is reachable via keyboard (open, type, arrow nav,
   Enter to select, Esc to close)
6. The HoverCard pattern works on touch (tap to open) — fall back to
   showing on click for touch devices
7. The reading progress bar updates smoothly without layout thrash

Test on viewport widths 375px, 768px, 1024px, 1440px. The container is
always max-w-1024 with px-6, but the hero, features grid, and team grid
adapt: 1 column < md, 2-3 columns >= md.

Run a final dev preview and confirm all pages render without console errors.
```

---

## After v0 export

Once the design is finalized in v0:

1. Click "Push to GitHub" in v0 (or download and push manually)
2. Verify the repo has these directories:
   - `app/` (with all page.tsx files)
   - `components/` with `site-header.tsx`, `site-footer.tsx`,
     `command-palette.tsx`, `contact-wizard.tsx` (top-level shells)
   - `components/ui/` with all the shadcn primitives used:
     **`button`, `card`, `command`, `dialog`, `sheet`, `hover-card`,
     `popover`, `breadcrumb`, `progress`, `badge`, `avatar`, `input`,
     `textarea`, `label`, `alert`, `sonner`** (these are the primitives
     the design-fidelity gate's shadcn-primitive-parity check looks for)
   - `app/globals.css` with shadcn slate theme tokens
3. Update `tests/e2e/scaffolds/micro-web/scaffold.yaml`:
   ```yaml
   design_source:
     type: v0-git
     repo: https://github.com/<your-user>/v0-micro-web-design.git
     ref: main   # or pin to a specific tag/commit
   ```
4. Run the smoke test:
   ```bash
   ./tests/e2e/runners/run-micro-web.sh
   ```
   The runner should clone the design, generate `design-manifest.yaml`, and
   complete the "v0 design source ready" step without warnings.
5. Confirm `v0-export/components/` ships these files (the fidelity gate's
   `shell-not-mounted` check enforces these mount in `src/components/`):
   - `site-header.tsx`
   - `site-footer.tsx`
   - `command-palette.tsx`
   - `contact-wizard.tsx`

If any of those components are missing, return to v0 and refine the prompts.

## What success looks like

An orchestration run on this scaffold should:
- Mount all four shell components (`site-header`, `site-footer`,
  `command-palette`, `contact-wizard`) at their canonical filenames in
  `src/components/`
- Use ALL distinctive primitives — `CommandDialog`, `Sheet`, `HoverCard`,
  `Dialog`, `Combobox`, `Progress`, `Breadcrumb`, `Popover` — somewhere
  under `src/`
- NOT alias-shadow any shell (`export const SiteHeader = Navbar`)

If any of those fail, the design-fidelity gate fires with the codes
documented in `.claude/rules/design-bridge.md` and the change cannot merge.
That's the test working.
