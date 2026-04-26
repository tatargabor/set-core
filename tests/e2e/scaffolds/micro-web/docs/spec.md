# Micro Web — Minimal Next.js App

A tiny Next.js 14 application with 5 pages, distinctive shadcn UX patterns, and Playwright E2E tests.
Purpose: validate orchestration pipeline + design-fidelity tracking with a small functional surface.

## Tech Stack
- Next.js 14 (App Router)
- TypeScript
- Tailwind CSS v4
- shadcn/ui (slate theme — tokens come from v0-export's `app/globals.css`)
- Playwright for E2E tests
- Vitest for unit tests

## Design Source

The visual contract is defined in `v0-export/` (cloned at run time from
`scaffold.yaml::design_source`). See `docs/design-brief.md` for the
**v0 Pattern Map** — which distinctive shadcn primitives appear where.

If `v0-export/` is present, the orchestrator's design-fidelity gate enforces
shell mounting + primitive parity (`.claude/rules/design-bridge.md`).

## Pages

### 1. Home Page (`/`)
- Header (shared) — see Header section below
- Hero: title "Micro Web" + short description + CTA button → /about
- Features grid: 3 `Card` components (Fast / Reliable / Simple) with lucide icons
- Newsletter signup CTA: button "Subscribe to updates" — clicking it opens a
  `Sheet` drawer from the right with email input + Submit button. On submit:
  toast "Thanks for subscribing!" (no backend, just `console.log`).
- Footer

### 2. About Page (`/about`)
- Header
- Page title "About Us" + 2-3 paragraphs of placeholder text
- Team section: 3 team members. Each renders as an avatar (placeholder
  initials in a circle) wrapped in `HoverCard` — hovering reveals the
  full member card with name, role, 1-2 sentence bio, and 2 social links.
  - Members (hardcoded): "Alice Chen — Engineering", "Bob Smith — Design",
    "Carol Davis — Product"
- Footer

### 3. Contact Page (`/contact`)
- Header
- Page title "Contact" + subtitle "We'd love to hear from you"
- Primary CTA button: "Get in touch" — opens a `Dialog` (multi-step wizard)

#### Contact wizard (inside `Dialog`)
- Stepper indicator at the top of the dialog showing 3 steps
- Step 1 — **Your details**: `Input` for Name (required) + `Input` for Email
  (required, email format)
- Step 2 — **What's it about?**:
  - Subject: `Combobox` — type-ahead filterable list of pre-defined
    categories (`General Inquiry`, `Technical Support`, `Feedback`, `Bug Report`,
    `Other`). Required.
  - Message: `Textarea` (required, min 10 chars)
- Step 3 — **Review & send**: read-only summary of fields + Submit button
- Validation per step: cannot advance until current step is valid
- On submit: close dialog, show `toast` (success variant) with title "Message sent"
  and description "We'll get back to you within 2 business days." `console.log`
  the payload.
- Footer

### 4. Blog Page (`/blog`)
- Header
- Page title "Blog"
- Filter bar: `Combobox` — single combined widget with type-ahead search
  AND category selection. Categories: `All`, `Frontend`, `Backend`, `Tooling`.
  Typing filters by title/excerpt; selecting a category filters by tag.
- Blog post list: 3 hardcoded posts as `Card` components
  - Each card: title (links to detail), date, excerpt, `Badge` for category,
    and an author byline. Hovering the author name shows a `HoverCard` with
    name, avatar, and 1-line bio.
  - Posts (hardcoded):
    - "Getting Started with Next.js" — 2024-01-15 — Frontend — author: Alice
    - "Understanding TypeScript" — 2024-01-10 — Tooling — author: Bob
    - "Tailwind CSS Tips" — 2024-01-05 — Frontend — author: Carol
- Footer

### 5. Blog Detail Page (`/blog/[slug]`)
- Header
- Sticky `Progress` bar at the very top of the viewport (below header) — fills
  as the user scrolls through the article (0% at top, 100% at bottom)
- `Breadcrumb`: "Home / Blog / {category} / {post title}"
- Article: title (h1), date, author byline (with `HoverCard`), full body
  prose (hardcoded, ~3-5 paragraphs per slug)
- Reactions row at end of article: 👍 / ❤️ / 🔖 buttons. Each has a
  `Popover` that opens on click showing extra options (e.g. share via
  Twitter/Email/Copy link for the share button)
- "Back to blog" link
- Invalid slug: `notFound()` → custom 404 page using `Alert` component
- Footer

## Shared Header (all pages)

- Sticky, full-width, `border-b`
- Layout (desktop): site title left, nav links (Home/About/Blog/Contact), Cmd+K palette trigger button, theme toggle (placeholder)
- **Cmd+K palette** (the global navigation primitive):
  - Trigger button labeled "Search…" with a `kbd` showing `⌘K` (or `Ctrl K`).
    Clicking it opens a `CommandDialog`.
  - Pressing `⌘K` / `Ctrl+K` anywhere on the page also opens it.
  - `CommandDialog` content: a `CommandInput` at top, then `CommandGroup`s:
    - "Pages" — entries: Home, About, Blog, Contact (each as `CommandItem`,
      navigates on Enter)
    - "Recent posts" — first 3 blog post titles (each navigates to the post)
    - "Theme" — `CommandItem` "Toggle theme" (placeholder action: toast)
  - `CommandSeparator` between groups; `CommandEmpty` when typed query
    matches nothing.
- **Mobile (< md):** the desktop nav links are replaced by a `Sheet` drawer.
  Hamburger icon button → `SheetTrigger`. `SheetContent` from the LEFT, with
  vertical nav links and a Cmd+K trigger inside.
- Active page highlighted (`text-primary font-medium`)

## Shared Footer (all pages)

- `border-t`, single line centered: "Built with Next.js and shadcn/ui"

## Requirements

### Navigation
- REQ-NAV-01: Header on every page with site title and 4 nav links
- REQ-NAV-02: Active page highlighted in nav
- REQ-NAV-03: Mobile uses `Sheet` drawer (NOT a `Dialog` modal) for nav
- REQ-NAV-04: Cmd+K opens `CommandDialog` palette globally; palette has
  Pages + Recent posts + Theme groups; navigation works via Enter key

### Content
- REQ-CONTENT-01: Home hero + 3 features `Card` grid + newsletter `Sheet`
- REQ-CONTENT-02: About page with 3 team members each in a `HoverCard`
- REQ-CONTENT-03: Blog list shows 3 posts with `Combobox` filter
- REQ-CONTENT-04: Blog detail shows full content for valid slug;
  invalid slug → `notFound()` (custom 404 with `Alert` component)
- REQ-CONTENT-05: Blog detail has sticky `Progress` reading indicator,
  `Breadcrumb`, and `Popover` reactions row

### Form
- REQ-FORM-01: Contact form is a multi-step wizard inside a `Dialog`
  (3 steps with stepper indicator)
- REQ-FORM-02: Step 2 uses `Combobox` for Subject (5 hardcoded categories)
- REQ-FORM-03: Validation per step (cannot advance with invalid current step)
- REQ-FORM-04: On submit: close Dialog, `console.log` payload, show success toast

### Testing
- REQ-TEST-01: Vitest unit tests for form validation logic
- REQ-TEST-02: Playwright E2E: visit each page, verify title/content
- REQ-TEST-03: Playwright E2E: open Cmd+K palette via `⌘K` keystroke,
  navigate to a page from it
- REQ-TEST-04: Playwright E2E: open contact wizard, fill all 3 steps,
  submit, verify toast appears
- REQ-TEST-05: Playwright E2E: blog list filter via Combobox narrows results
- REQ-TEST-06: Mobile viewport — hamburger opens Sheet drawer (not Dialog)

### Test selectors

Use stable `data-testid` for E2E:
- `cmdk-trigger` — Cmd+K palette trigger button
- `cmdk-dialog` — the open palette
- `mobile-nav-trigger` — hamburger button (mobile)
- `mobile-nav-drawer` — the open Sheet
- `newsletter-trigger` — home newsletter Sheet trigger
- `contact-dialog-trigger` — "Get in touch" button
- `contact-step-1` / `contact-step-2` / `contact-step-3` — wizard step containers
- `contact-submit` — submit button (step 3)
- `blog-filter-combobox` — blog filter combobox
- `reading-progress` — blog detail progress bar

## Orchestrator Directives

```yaml
max_parallel: 2
review_before_merge: true
e2e_mode: per_change
time_limit: 2h
```
