---
paths:
  - "src/app/**"
  - "src/lib/**"
---
# Functional Conventions

## Server Actions
- Return `{ success, error? }` — never throw from actions
- Call `revalidatePath()` after mutations
- Protected actions: check auth at the top before any logic
- Co-locate actions with their route segment as `actions.ts` (e.g., `src/app/admin/(dashboard)/products/actions.ts`)
- NEVER create a top-level `src/actions/` directory — actions belong next to the routes that use them
- Shared actions used by 3+ route segments go in `src/lib/actions/`
- Naming: verb-noun functions (`createProduct`, `deleteOrder`)

## Database Patterns (Prisma)
- Use singleton PrismaClient — export from `src/lib/prisma.ts`
- NEVER name it `db.ts`, `database.ts`, or `client.ts`
- Import as: `import { prisma } from "@/lib/prisma"`
- globalThis pattern for dev hot reload (prevent connection exhaustion)
- Use transactions (`prisma.$transaction`) for multi-table mutations
- Never use `deleteMany` without a WHERE clause

## Utility Files
- `src/lib/format.ts` — formatting helpers (price, date, number). Not `format-price.ts`, not `formatters.ts`
- `src/lib/queries/<entity>.ts` — reusable data access queries (when a query is used by 3+ components)
- `src/lib/validations.ts` — shared Zod schemas (single file until it exceeds 400 lines, not a `validations/` directory)

## Form Patterns
- **Pattern A (Dialog)**: Form in dialog → server action → close dialog → revalidate
- **Pattern B (Inline)**: Inline form/toggle → server action → revalidate
- Use `react-hook-form` + `zod` for validation
- Share validation schemas between client and server

## API Route Handlers
- Use `NextResponse.json()` for all responses — set explicit status codes
- Standard response shape: `{ data }` on success, `{ error: string }` on failure
- Common status codes: 200 (OK), 201 (Created), 400 (Bad Request), 401 (Unauthorized), 403 (Forbidden), 404 (Not Found), 500 (Internal Server Error)
- Validate request body with `zod` — return 400 with validation errors
- Auth-protected routes: check session at the top, return 401/403 before logic
- Group related routes: `src/app/api/[resource]/route.ts` (GET, POST) and `src/app/api/[resource]/[id]/route.ts` (GET, PUT, DELETE)
- Never expose internal error details in production responses

## Multi-Step Forms (Wizard)
- Store step state in a `useReducer` or zustand store — not scattered `useState`
- Each step is a sub-component receiving shared state + dispatch
- Validate current step before allowing next — show inline errors
- Support back navigation without losing data
- Show step indicator (stepper) with current/completed/remaining states
- Final submission sends all collected data in a single server action
- On server validation failure: return which step has the error, navigate back to it

## Error Handling
- Server actions return `{ success: false, error: string }` — never throw
- API routes return proper HTTP status codes with JSON error bodies
- Use `try/catch` at the action boundary, not inside utility functions

## Slug Generation
- Slugs MUST be ASCII-safe — strip or transliterate accented characters before storing
- Accented characters in URLs cause 404 errors because URL encoding doesn't match DB lookup
- Pattern:
  ```typescript
  function slugify(str: string): string {
    return str
      .normalize('NFD')
      .replace(/[\u0300-\u036f]/g, '')  // strip diacritics
      .toLowerCase()
      .replace(/[^a-z0-9]+/g, '-')
      .replace(/^-|-$/g, '');
  }
  ```
- Apply during seed data generation AND any user-generated slug creation
- Test slug generation with non-ASCII input (é, á, ö, ü, ñ, ß, etc.)

## URL Filter Encoding
- When filter values may contain commas (e.g., "Ethiopia, Yirgacheffe"), the delimiter between filter values MUST be pipe (`|`) not comma (`,`)
- Alternative: URL-encode individual values before joining with comma
- This applies to query parameters like `?origin=Ethiopia|Kenya` or `?tags=dark-roast|single-origin`

## Rendering Consistency
- Saved/cached data views MUST reuse the same components as live views — never render raw JSON or use different formatting for the same data shape
- Example: if a live adaptation result uses `DeviceCard`, `StepTimeline`, `CollapsibleSection`, the saved adaptation detail page MUST use those same components — not a raw JSON dump or a simplified flat list
- When adding a "saved" or "history" view, import and reuse the existing result components
