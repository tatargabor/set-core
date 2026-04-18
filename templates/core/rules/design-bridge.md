# Design Bridge Rule (v0-only pipeline)

## What you get

When your change has a `design-source/` directory (`openspec/changes/<change>/design-source/`), **those TSX files are the design truth**. They come from the project's v0.app export and are sliced to just the routes/components your change covers, plus shared components (`components/ui/**`, layout, header, globals.css).

If no `design-source/` exists for your change, skip this rule.

## Agent contract: integrator, not re-implementer

You **copy** v0's TSX into the project, then adapt the integration layer around it. You do NOT rebuild the UI from a markdown spec.

### Allowed refactors (encouraged)

- Extract repeated JSX into reusable component files
- Rename / move files to project convention (kebab-case, directory structure)
- Add TypeScript types where v0 used `any` or omitted
- Convert client→server components when data is server-side — preserve interactivity
- Replace mock data with Prisma queries / real API calls
- Add `metadata` exports, Suspense boundaries, `error.tsx`
- Replace English placeholder copy with HU content from the i18n catalog
- Replace placeholder images with seed/CMS URLs
- Add `aria-*` attributes for accessibility

### Forbidden changes (caught by the design-fidelity gate)

- Tailwind className value changes (even "more semantic" alternatives)
- DOM structure changes (added/removed wrappers, sibling reorder)
- shadcn primitive substitution (`Button` → custom `<button>`)
- shadcn variant prop changes (`size`, `variant`, etc.)
- Spacing token changes (`gap`, `padding`, `margin`)
- Responsive breakpoint changes
- Animation sequence/duration/easing changes
- Icon library substitution
- `globals.css` modification — this file is synced from v0-export and the agent MUST NOT touch it

## The contract is visual, not file-for-file

The fidelity gate (Playwright screenshot + pixel diff across desktop/tablet/mobile) is what enforces the design contract. You're free to refactor the file layout — what must stay constant is the rendered output.

### Skeleton check runs first (fast fail)

Before any build/screenshot, the gate verifies:
- Every route in `docs/design-manifest.yaml` has a `page.tsx` in your worktree
- Every `shared:` file from the manifest exists (either at its manifest path or via `shared_aliases` rename)
- Shared components remain discrete file exports — don't inline a shared component into the page that uses it

If the skeleton check fails, the gate reports `skeleton-mismatch` with the specific missing/extra items. Fix those before the screenshot diff can even run.

## When uncertain

If you're unsure whether a change is "refactor-safe" or "design-breaking":
1. Preserve v0's className/JSX exactly
2. Commit
3. Let the fidelity gate tell you

Don't pre-emptively change things because you think v0's choice is "wrong" — make the change, let the gate pass, then if you still believe a change is warranted, raise it as a scaffold-author concern (the fix goes in the v0 repo, not the agent worktree).

## v0 source bug policy

If you find an actual bug in v0's output (broken link, type error, missing import):

- Fix it in your worktree while preserving the visual output (classNames, JSX structure)
- Commit-message prefix: `v0-fix: <short description>`
- Common v0 bugs: incorrect `Link` href, missing `"use client"` on interactive components, unused imports, `any` where a concrete type would fix a tsc error

If v0 shows the same concept inconsistently across pages (e.g. some pages use `<Button variant="default">`, others use `<button className="...">` with identical styling): **standardize on the shadcn primitive** across your worktree, document in the commit message. If that causes a fidelity gate failure, escalate to the scaffold author — the fix belongs in the v0 source, not in the agent worktree.

## Token source priority

When the framework injects design tokens into your input:

1. `v0-export/app/globals.css` (or `shadcn/globals.css`) — authoritative CSS variables
2. Optional `docs/design-brief.md` — **non-authoritative** vibe notes (brand personality, AVOID list). Never use this as spec.
3. If neither exists: use project shadcn/ui defaults; don't invent new variants.
