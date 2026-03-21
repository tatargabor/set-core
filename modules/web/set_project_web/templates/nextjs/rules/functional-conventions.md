---
paths:
  - "src/app/**"
  - "src/lib/**"
  - "src/actions/**"
---
# Functional Conventions

## Server Actions
- Return `{ success, error? }` — never throw from actions
- Call `revalidatePath()` after mutations
- Protected actions: check auth at the top before any logic
- Place in `src/actions/` or co-locate in feature directories

## Database Patterns (Prisma)
- Use singleton PrismaClient — import from `src/lib/prisma.ts`
- globalThis pattern for dev hot reload (prevent connection exhaustion)
- Use transactions (`prisma.$transaction`) for multi-table mutations
- Never use `deleteMany` without a WHERE clause

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
