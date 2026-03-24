---
paths:
  - "src/components/**"
  - "src/features/**"
  - "src/pages/**"
---
# Component Conventions

## File Size
- Components should stay under 400 lines
- Extract custom hooks into separate files when logic exceeds ~50 lines
- Split large components into sub-components

## Naming
- Components: PascalCase (`UserProfile.tsx`)
- Hooks: camelCase with `use` prefix (`useUserProfile.ts`)
- Utilities: camelCase (`formatDate.ts`)
- Constants: UPPER_SNAKE_CASE (`MAX_RETRY_COUNT`)

## Structure
- One component per file (default export)
- Co-locate styles, tests, and types with the component
- Use barrel exports (`index.ts`) only for public API of feature modules

## State Management
- Local state: `useState` / `useReducer`
- Shared state: choose ONE solution for your project and document it here
  - Options: Zustand, Jotai, Redux Toolkit, React Context
- Server state: React Query / TanStack Query or SWR
- Never mix multiple state management solutions for the same concern

## Props
- Use TypeScript interfaces for props
- Destructure props in function signature
- Provide sensible defaults for optional props

## Layout Consistency
- All pages within a route group MUST use the shared layout — never create page-level wrappers that replace the route group layout sidebar/nav
- Admin pages must always render within the admin layout (`app/admin/layout.tsx`) — if the sidebar disappears on a sub-page, the layout nesting is broken
- E2e tests for admin features must verify sidebar/nav is visible on every admin page
