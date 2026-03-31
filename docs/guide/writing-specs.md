[< Back to Guides](README.md)

# Writing Specs for Web Projects

Your specification is the single most important input to the orchestration pipeline. A well-written spec produces an app that matches your vision — the right colors, the right layout, the right behavior. A vague spec produces a working but generic app that needs extensive manual fixing afterward.

This guide covers how to write specs that get you what you want on the first run.

---

## The Core Principle

**Agents implement exactly what the spec tells them.** If the spec says "add a product catalog page," you get a generic page with default styling. If the spec says "product catalog with filter sidebar (280px, 6 filter groups, collapsible sections), 3-column product grid with hover shadow and gold border, sorting dropdown top-right," you get that.

```
VAGUE SPEC                          DETAILED SPEC
─────────────                       ─────────────
"Add a cart page"                   "Cart page with:
                                     - Item table: 60px thumbnail, product name + variant,
                                       unit price, [-] qty [+] controls (44px touch target),
                                       line total, trash icon to remove
                                     - Coupon input below items with 'Beváltás' button
                                     - Gift card input with separate balance check
                                     - Order summary sidebar: subtotal, discount, shipping
                                       (free above 10,000 Ft), total in bold
                                     - 'Tovább a fizetéshez' CTA button, full-width on mobile"

Result: generic table              Result: matches the Figma design
```

---

## Spec Structure

A good spec has these sections. You don't need all of them — but the more detail you provide, the better the result.

### 1. Project Overview

What is this app? Who is it for? What's the tech stack?

```markdown
# CraftBrew — Specialty Coffee E-commerce

Premium specialty coffee webshop for Budapest-based roasters.
Next.js 14 App Router, Prisma + SQLite, next-intl (HU/EN),
shadcn/ui components, Tailwind CSS.

Target: Desktop + mobile responsive. Primary locale: Hungarian.
```

**Why this matters:** The agent uses this to make hundreds of micro-decisions — naming conventions, locale defaults, price formatting, SEO structure.

### 2. Data Model

Name your entities, their fields, and relationships. This becomes the Prisma schema.

```markdown
## Data Model

### Product
- id, name, slug (unique), description, shortDescription
- category: enum (COFFEE, EQUIPMENT, MERCH, BUNDLE)
- basePrice (Int, in HUF), compareAtPrice (optional)
- imageUrl, thumbnailUrl
- origin, roastLevel, processingMethod (for coffee)
- inStock (boolean), stockCount
- Relations: variants[], reviews[], bundleItems[]

### ProductVariant
- id, productId, name (e.g., "Szemes 250g"), sku
- price (Int), weight (grams), grindType (optional)
- stockCount, isDefault

### Order
- id, userId, status: enum (PENDING, CONFIRMED, SHIPPED, DELIVERED, CANCELLED)
- subtotal, discount, shippingCost, total (all Int, HUF)
- shippingAddress (JSON), billingAddress (JSON)
- stripePaymentId, createdAt
- Relations: items[], user
```

**Why this matters:** Without this, agents invent their own schema — and every agent invents a different one. Conflicts on merge.

### 3. Page Layouts

Describe each page's structure — sections, column layouts, component placement.

```markdown
## Pages

### Homepage
1. **Hero Banner** — full-width atmospheric photo background (~500px tall),
   overlay text left-aligned: h1 title + subtitle + CTA button
2. **Featured Products** — section title centered, 4-column product card grid
3. **Subscription CTA** — two-column: image left (50%), text + button right (50%).
   NOT centered banner. Side-by-side layout.
4. **Stories** — 3 story cards with cover image (16:9), title, date, excerpt
5. **Footer** — 3 columns: brand info | navigation links | contact + social icons

### Product Catalog
- Filter sidebar (left, 280px desktop): origin checkboxes, roast level,
  processing method, price range slider (dual handle, 1990-9380 Ft)
- Product grid (right, 3 columns desktop, 1 column mobile)
- Sorting dropdown top-right: Népszerű, Ár↑, Ár↓, Legújabb
- Mobile: filters collapse into bottom sheet, triggered by "Szűrők" button
```

**Why this matters:** This is the biggest gap between "what you imagine" and "what agents build." Without layout descriptions, agents use whatever shadcn defaults look reasonable.

### 4. Component Behavior

Describe interactive elements — what happens on click, hover, state changes.

```markdown
## Component Behavior

### Product Card
- Image: 4:3 aspect ratio, hover → subtle shadow lift + gold border
- Heart icon top-right on image (wishlist toggle)
- Price in bold, gold color (#D97706)
- "Részletek" link below price
- Variant badge ("Szemes", "Őrölt") if multiple variants

### Cart
- Quantity controls: [-] and [+] buttons, minimum 1, 44px touch target
- Remove: trash icon, confirmation dialog before removing
- Coupon: input + "Beváltás" button. Applied → green badge with X to remove
- Summary: recalculates live when quantity changes
- Empty state: icon + "A kosarad üres" message + "Kávék böngészése" link
```

### 5. Auth & Roles

Be explicit about who can do what.

```markdown
## Authentication

- JWT session strategy (NextAuth.js)
- Roles: USER, ADMIN
- User registration: email, password, name. Auto-login after register.
- Admin access: /admin/* routes, no public admin link (security)

### Protected Routes
- /admin/* → ADMIN only, redirect to /admin/login
- /fiok/* → USER, redirect to /login
- /kosar, /fizetes → USER for checkout, cart viewable without auth
```

### 6. Seed Data

Define initial data so the app isn't empty after first run.

```markdown
## Seed Data

### Products
- 8 coffees (Ethiopia Yirgacheffe, Colombia Supremo, etc.) with:
  - 3 variants each (250g/500g/1kg), different prices
  - Realistic Hungarian descriptions
  - placehold.co URLs with brand colors for images
- 7 equipment items (V60 Dripper, Hario Scale, etc.)
- 5 merch items (tote bag, mug, t-shirt)

### Users
- Admin: admin@craftbrew.hu / admin123
- Test user: test@craftbrew.hu / test123 (for E2E tests)

### Content
- 5 story categories, 10 stories with Hungarian text
- 3 coupons: ELSO10 (10%), NYAR2026 (15%), BUNDLE20 (20% on bundles)
```

**Why this matters:** Without seed data spec, agents create 2-3 placeholder products with "Product 1" names. With it, the app launches with realistic content.

---

## Design Integration

This is the step most people skip — and then spend hours fixing colors and fonts afterward.

### Option A: Figma Make (Recommended)

1. Design in [Figma Make](https://www.figma.com/make) — give it your exact brand colors, fonts, spacing
2. Export: File → Download .make file → save to `docs/design.make`
3. Run:
   ```bash
   set-design-sync --input docs/design.make --spec-dir docs/
   ```
4. This generates `docs/design-system.md` and adds `## Design Reference` sections to your specs

The agents then receive exact hex colors, font names, and page layouts — not framework defaults.

### Option B: Manual Design Tokens

Add a section to your spec with exact values:

```markdown
## Design Tokens

### Colors
- Primary: #78350F (dark coffee brown) — buttons, CTAs, logo
- Secondary: #D97706 (gold accent) — hover states, links, prices
- Background: #FFFBEB (warm cream) — page background, NOT white
- Surface: #FFFFFF — cards, panels, header
- Text: #1C1917 — main text
- Muted: #78716C — secondary text, placeholders

### Typography
- Headings: Playfair Display (serif) — h1: 40px, h2: 32px, h3: 24px
- Body: Inter (sans-serif) — 16px base, 14px small
- Import from Google Fonts in root layout

### Spacing
- 8px base grid, 24px card padding, 6px button radius, 8px card radius
- Container max-width: 1280px

### Components
- Buttons: filled #78350F with white text, 6px radius, 44px min touch target
- Cards: 24px padding, 8px radius, subtle shadow on hover
- Nav items: hover color #D97706, active underline #78350F
```

**Without this section**, agents use shadcn defaults: white background, system fonts, generic blue/gray palette.

### Option C: No Design

If you have no design, say so explicitly:

```markdown
## Design
Use shadcn/ui defaults with a clean, modern aesthetic. No custom branding required.
```

This prevents agents from inventing random brand colors.

---

## i18n (Internationalization)

If your app is multilingual, state it clearly:

```markdown
## Internationalization

- Framework: next-intl
- Locales: hu (default), en
- URL structure: /hu/kavek, /en/coffees (localized paths)
- All user-visible text via translation keys — never hardcoded strings
- Units: display in user's locale (db/piece for HU, piece for EN)
- Seed data: translations for both locales
```

**Without this**, agents hardcode Hungarian strings or build English-only. Adding i18n after the fact requires touching every component.

---

## E2E Test Expectations

Tell agents what to test:

```markdown
## E2E Tests

Each feature change must include Playwright tests covering:
- Cold visit (no login, no session) — page loads without crash
- Happy path (login → action → verify result)
- Error state (invalid input → error message shown)

### Test User
Login as test@craftbrew.hu / test123 for authenticated tests.

### Critical Flows
- Homepage loads with products visible
- Add to cart → cart page shows item → checkout flow completes
- Admin login → product CRUD (create, edit, delete, verify list updates)
- Language switcher toggles between /hu/ and /en/
```

---

## Common Mistakes

| Mistake | Result | Fix |
|---------|--------|-----|
| No color values in spec | White background, gray buttons | Add `## Design Tokens` with hex values |
| "Add product page" without layout | Generic single-column list | Describe columns, filters, cards, sorting |
| No data model | Each agent invents different schema, merge conflicts | Write explicit entity/field list |
| No seed data spec | "Product 1", "Product 2" placeholder content | Specify realistic product names, categories, prices |
| No i18n mention | Hardcoded English (or hardcoded Hungarian) | State locales and framework up front |
| No auth roles | Admin endpoints without auth, or auth everywhere | List protected routes and roles |
| "Use Figma design" without tokens | Agent can't access Figma, uses defaults | Run `set-design-sync` or paste tokens in spec |
| No E2E test guidance | Tests only check "page loads", miss CRUD flows | Specify critical flows per feature |

---

## Complete Example: Coffee E-commerce Spec

See the craftbrew scaffold for a production-quality example:

```
tests/e2e/scaffolds/craftbrew/docs/
├── v1-craftbrew.md          ← Main spec (overview, data model, auth, seed data)
├── design.make              ← Figma Make export (brand design)
├── design-system.md         ← Generated design tokens (from set-design-sync)
├── catalog/                 ← Feature specs per product category
│   ├── coffees.md
│   ├── equipment.md
│   └── bundles.md
└── features/                ← Feature specs per capability
    ├── product-catalog.md
    ├── cart-checkout.md
    ├── admin.md
    ├── i18n.md
    ├── subscription.md
    └── ...
```

Each feature spec has:
- Concrete page/component descriptions
- Data model references
- `## Design Reference` section (auto-generated by `set-design-sync`)

To start a new project using this as a template:

```bash
./tests/e2e/runners/run-craftbrew.sh
```

---

## Checklist Before Starting Sentinel

Use this checklist before every orchestration run:

- [ ] **Data model complete?** — All entities, fields, relationships, enums defined
- [ ] **Page layouts described?** — Each page has section list, column counts, component names
- [ ] **Design tokens present?** — Either via `set-design-sync` or manual `## Design Tokens` section
- [ ] **Auth & roles defined?** — Protected routes listed, admin access specified
- [ ] **Seed data specified?** — Product names, user credentials, sample content
- [ ] **i18n stated?** — Locales, framework, URL structure (or "English only")
- [ ] **E2E expectations set?** — Test user credentials, critical flows listed
- [ ] **Config reviewed?** — `set/orchestration/config.yaml` has correct commands

---

## End-to-End Terminal Walkthrough

Here's the complete flow from an empty directory to a running app — every command you'll type.

### Step 1: Create the project

```bash
mkdir my-coffee-shop && cd my-coffee-shop
git init && git checkout -b main
```

### Step 2: Write your spec

Create `docs/spec.md` with the sections described above. This is the most important step — spend time here.

```bash
mkdir docs
# Write your spec (use your editor, or Claude Code to help draft it)
claude "Help me write a detailed spec for a specialty coffee e-commerce
       webshop. I need: data model, page layouts, auth, seed data,
       i18n (HU/EN), and design tokens. Save to docs/spec.md"
```

**Tip:** Use Claude Code to help draft the spec interactively. It will ask good questions about what you want. Review and edit the output — don't use it blindly.

### Step 3: Create the Figma design (optional but recommended)

Go to [Figma Make](https://www.figma.com/make) and create your design. Give it your spec text as input — the more detail, the better.

```bash
# After designing in Figma Make:
# File → Download .make file
cp ~/Downloads/my-design.make docs/design.make
```

### Step 4: Initialize the project with set-core

```bash
set-project init --name my-coffee-shop --project-type web --template nextjs
```

This deploys:
- `.claude/rules/` — 20+ rules guiding agents (auth, testing, security, i18n, etc.)
- `.claude/commands/` and `.claude/skills/` — orchestration skills
- `playwright.config.ts`, `vitest.config.ts`, `global-setup.ts` — test infrastructure
- `set/orchestration/config.yaml` — pipeline configuration

### Step 5: Sync design tokens into specs

```bash
set-design-sync --input docs/design.make --spec-dir docs/
```

Output:
```
Parsing: docs/design.make (MakeParser)
Generated: docs/design-system.md (394 lines)
  Tokens: 28 properties
  Components: 7
  Pages: 24
  Fonts: Playfair Display, Inter, JetBrains Mono
  Specs updated: 16
```

**Verify:** Open `docs/design-system.md` — are the hex colors correct? Open `docs/spec.md` — is there a `## Design Reference` section at the bottom?

### Step 6: Review the orchestration config

```bash
cat set/orchestration/config.yaml
```

Key settings to verify:
```yaml
default_model: opus        # or sonnet for faster/cheaper runs
test_command: pnpm test    # unit tests
e2e_command: npx playwright test  # E2E tests
merge_policy: checkpoint   # merge after each change, not all at once
review_before_merge: true  # LLM code review gate
max_parallel: 2            # how many agents run simultaneously
env_vars:
  DATABASE_URL: "file:./dev.db"
```

### Step 7: Commit everything

```bash
git add -A
git commit -m "Initial project setup with spec and design"
```

**Important:** The sentinel runs on a git repo — everything must be committed before starting.

### Step 8: Start the sentinel

```bash
# Option A: Via web dashboard (recommended — visual monitoring)
# Open http://localhost:7400, select your project, click Start

# Option B: Via API
curl -X POST http://localhost:7400/api/my-coffee-shop/sentinel/start \
  -H 'Content-Type: application/json' \
  -d '{"spec":"docs/spec.md"}'
```

The sentinel will:
1. **Digest** your spec → extract requirements
2. **Decompose** → break into parallel changes with dependency DAG
3. **Dispatch** → create worktrees, give each agent its scope + design tokens
4. **Build/Test/E2E** → quality gates on each change
5. **Merge** → verified changes merge to main
6. **Repeat** until all requirements are covered

### Step 9: Monitor progress

```bash
# Check status via API
curl -s http://localhost:7400/api/my-coffee-shop/status | python3 -m json.tool

# Or watch the dashboard at http://localhost:7400
```

Typical timeline for a 6-change coffee shop project:
- Digest + decompose: ~5 min
- Foundation (first change): ~10 min
- Parallel changes (3-4 at a time): ~30-45 min
- Total: ~45-60 min

### Step 10: Review the result

```bash
# Install deps and start the dev server
cd /path/to/my-coffee-shop
pnpm install
npx prisma generate && npx prisma db push && npx prisma db seed
pnpm dev
# Open http://localhost:3000
```

Check:
- Do the colors match your Figma design?
- Are the page layouts correct (column counts, component placement)?
- Does the header/footer match the design?
- Does i18n work (language switcher)?
- Does login/admin work?

### If something doesn't match the design

Two options:

**A) Run a design-alignment spec** (like we did with craftbrew-run14):
```bash
# Write a targeted spec for the visual fixes
cat > docs/design-fixes.md << 'EOF'
# Design Alignment

Fix the following visual issues to match the Figma design:

## Header
Current: inline search bar
Target: search icon only, opens overlay

## Subscription Section
Current: centered text on beige band
Target: two-column layout, image left 50%, text right 50%

## Design Tokens (use these exact values)
- Primary: #78350F
- Background: #FFFBEB (NOT white)
- Headings: Playfair Display serif
EOF

# Start sentinel with the fix spec
curl -X POST http://localhost:7400/api/my-coffee-shop/sentinel/start \
  -H 'Content-Type: application/json' \
  -d '{"spec":"docs/design-fixes.md"}'
```

**B) Fix manually in Claude Code:**
```bash
claude "Fix the homepage subscription section to match the Figma design:
       two-column layout, image left 50%, text right 50%.
       Use #78350F for the CTA button. See docs/design-system.md for tokens."
```

---

## Quick Reference: Commands

| Step | Command | Why |
|------|---------|-----|
| Init project | `set-project init --name X --project-type web --template nextjs` | Deploys rules, templates, config |
| Sync design | `set-design-sync --input docs/design.make --spec-dir docs/` | Extracts tokens, updates specs |
| Health check | `/set:audit` (in Claude Code) | Catches config issues |
| Start sentinel | Via dashboard or `curl -X POST .../sentinel/start` | Runs the full pipeline |
| Check status | `curl -s .../api/X/status` or dashboard | Monitor progress |
| Compare runs | `set-compare run-a run-b` | Diff two runs for divergence |
