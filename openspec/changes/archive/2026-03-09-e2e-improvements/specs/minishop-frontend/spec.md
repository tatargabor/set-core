## ADDED Requirements

### R1: Next.js App Router Scaffold
- E2E scaffold uses Next.js 14+ App Router with TypeScript
- Prisma ORM with SQLite database (`file:./dev.db`)
- shadcn/ui component library (pre-initialized with button, card, input, label, table, sheet, dialog, dropdown-menu, toast, badge, skeleton, separator)
- Tailwind CSS for styling
- pnpm as package manager
- Scaffold includes pre-built base: root layout, health API route, Prisma client singleton, shadcn `cn()` utility, and seed data

### R2: Prisma Schema
- Models: `Product` (id, name, description, price, stock, imageUrl, createdAt, updatedAt), `User` (id, email, passwordHash, name, role, createdAt), `Order` (id, userId, total, status, createdAt), `OrderItem` (id, orderId, productId, quantity, price), `CartItem` (id, sessionId, productId, quantity)
- Relations: Order → User (many-to-one), OrderItem → Order/Product, CartItem → Product
- SQLite provider, no `@@map` needed (simple names)
- Seed script populates 6+ products with Hungarian names, realistic prices (HUF), stock levels, and placeholder image URLs

### R3: Feature Roadmap Spec (v1-minishop.md)
- 6 changes in dependency order:
  1. `products-page` — Server Component product catalog, shadcn Card grid, product detail page
  2. `cart-feature` (depends: products-page) — Server-side cart persisted in Prisma `CartItem` table, anonymous sessions via UUID cookie, cart page with quantity controls
  3. `orders-checkout` (depends: cart-feature, products-page) — Server Action checkout, transactional order creation, orders history page
  4. `admin-auth` (depends: products-page) — NextAuth.js v5 (Auth.js) Credentials provider, `auth()` for session, login/register pages, middleware protection (admin routes only — storefront routes remain public), admin layout
  5. `admin-products` (depends: admin-auth, products-page) — DataTable CRUD, Server Actions, zod validation, react-hook-form
  6. `playwright-e2e` (depends: all) — Full journey E2E tests, screenshot capture, responsive viewport tests
- Orchestrator directives: max_parallel: 2, smoke_command: pnpm test, smoke_blocking: true, auto_replan: true, merge_policy: checkpoint, checkpoint_auto_approve: true

### R4: Scaffold CLAUDE.md
- Documents all conventions from set-project-web: Server Actions pattern, shadcn usage, Prisma conventions
- Commands: `pnpm dev`, `pnpm test`, `pnpm build`, `pnpm prisma migrate dev`
- File conventions: `src/app/**/page.tsx`, `src/components/ui/`, `src/lib/`, `src/actions/`
- Explicit rules: use shadcn not raw Radix, "use client" only where needed, Server Components by default, TypeScript strict mode

### R5: E2E Runner Update
- `tests/e2e/run.sh` updated for pnpm: `pnpm install`, `pnpm test`, `pnpm prisma migrate dev`, `pnpm prisma db seed`
- set-project init with `--project-type web`
- Playwright browsers installed during scaffold init: `pnpm exec playwright install chromium`
- After sentinel completes, invoke `wt-e2e-report` for report + screenshots

### R6: Design Quality
- Consistent color scheme using Tailwind/shadcn theme (CSS variables)
- Responsive: mobile (375px), tablet (768px), desktop (1200px+)
- Navigation bar with logo, links (Products, Cart, Orders, Admin)
- Active page highlighted
- Loading states (shadcn Skeleton components)
- Toast notifications for actions (add to cart, order placed, product CRUD)
- Product cards with image placeholder, hover effects
- Admin sidebar layout distinct from storefront layout

### R7: Playwright E2E Tests
- Playwright config with headless Chromium, webServer pointing to `pnpm dev`
- Test cases:
  - Storefront: products render with images, prices, stock
  - Cart: add from storefront, quantity update, remove, total calculation
  - Checkout: place order, verify stock decremented, order in history
  - Admin: login, add product (appears in catalog), edit, delete
  - Responsive: mobile viewport (375px) layout adapts
- Each test uses fresh database (via test fixtures)
- Screenshot capture for report: `page.screenshot({ path: 'e2e-screenshots/<name>.png' })`
