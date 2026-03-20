# nextjs-patterns

New rule file: `.claude/rules/web/nextjs-patterns.md`.

## ADDED Requirements

## IN SCOPE
- The force-dynamic export anti-pattern and correct alternatives (ISR, unstable_cache)
- Server actions invoked from client-side effects and correct patterns

## OUT OF SCOPE
- General React patterns (covered by other rules)
- Next.js deployment configuration
- Next.js middleware patterns (covered by auth-middleware.md)

### Requirement: force-dynamic anti-pattern prevention

Pages that contain a mix of static and dynamic content SHALL NOT use `export const dynamic = 'force-dynamic'` as a blanket solution. force-dynamic disables all static optimization for the entire page, including parts that could be cached. The system SHALL use granular caching strategies instead: ISR (`revalidate`), `unstable_cache` / `cache()` for specific data fetches, or Suspense boundaries to stream dynamic sections.

#### Scenario: Page with mostly static content and one dynamic section

- **WHEN** a product listing page has static category navigation and dynamically priced items
- **THEN** the page uses ISR with revalidation or wraps the dynamic section in Suspense, not `export const dynamic = 'force-dynamic'`

#### Scenario: Entire page is genuinely dynamic

- **WHEN** every part of the page depends on the current user session (e.g., a dashboard)
- **THEN** using `force-dynamic` is acceptable because no part can be statically optimized

### Requirement: Server actions in client effects

Server actions SHALL NOT be called directly inside `useEffect` or event handlers without proper error handling and loading state management. When client components need server data, prefer server component data fetching passed as props. When client-side invocation is necessary, the call MUST be wrapped in try/catch with user-visible error feedback.

#### Scenario: Server action called in useEffect without error handling

- **WHEN** a client component calls a server action inside `useEffect` without try/catch
- **THEN** a server-side error causes an unhandled rejection with no user feedback

#### Scenario: Correct approach with error handling

- **WHEN** a client component must invoke a server action
- **THEN** the call is wrapped in try/catch, a loading state is shown during the request, and errors are displayed to the user
