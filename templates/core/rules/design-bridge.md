# Design Bridge Rule

## What you have

Your worktree contains a **design source export** — typically `v0-export/` (v0.app Next.js export) but the exact directory name depends on the design tool (`claude-design-export/`, `figma-make-export/`, etc.). Read any file there as **visual truth**. This is the full design source; your `input.md` may highlight focus files, but you are never limited to those.

If no design-source export is present in your worktree, skip this rule.

## Locale convention: design source = canonical HU, consumer = i18n-aware

**v0-design (and similar design tools) emit HU-only canonical previews by convention.** UI strings are HU literals (`<Button>Kosárba</Button>`) and route paths are HU slugs (`'/belepes'`, `'/kavek'`). This is **not** a bug — the design source is a single-locale preview, not the deployed app.

**The CONSUMER (your orchestrated app) is what makes it locale-aware**, via next-intl:
- **UI strings:** transform `<Button>Kosárba</Button>` → `<Button>{t('product.addToCart')}</Button>` at implementation. Add the entry to `messages/hu.json` (canonical) AND `messages/en.json` (translation).
- **Route paths:** import next-intl `<Link>` or `useRouter()`; the design source's HU literal (`/belepes`) is the canonical key, transformed to `/en/login` at render time via the `pathnames` map in `i18n/routing.ts`.
- **Middleware:** `/` → `/hu` redirect; `[locale]` segment for non-default locales.

**DO NOT propify HU literals back into the design source** (e.g. don't add `labels?: { addToCart: string }` props to `<Button>` — the design source intentionally has the canonical HU string). Translation happens at IMPLEMENTATION time.

The `set-design-hygiene` scanner reports HU literals as INFO severity (not WARN) because of this convention.

## Component-mounting rule (design-binding-completeness)

**If a shell component for your feature exists in the design source's `components/` directory, mount it. DO NOT create a parallel implementation under a different name.**

### Strict mounting rules (the fidelity gate enforces these)

For every top-level shell `v0-export/components/<X>.tsx` (anything NOT under `components/ui/`):

1. **Mount at the canonical filename** — `src/components/<X>.tsx` MUST exist with the same kebab-case name. Different filenames are a `shell-not-mounted` violation (CRITICAL, blocks merge), even if a similarly-purposed file exists under another name.
2. **No aliasing to a sibling local file** — A file like:
   ```tsx
   // src/components/site-header.tsx
   import { Navbar } from "./Navbar";
   export const SiteHeader = Navbar;       // ← shadow-alias, BLOCKS MERGE
   export default Navbar;                    // ← also shadow-alias
   ```
   This pattern games the skeleton check while bypassing the v0 design entirely. The gate flags `shadow-alias` (CRITICAL).
3. **Re-exporting v0 directly is fine** — if you want to keep `components/ui/` simple imports while "mounting" the shell:
   ```tsx
   // src/components/site-header.tsx
   export { default } from "@/v0-export/components/site-header";   // OK
   ```
4. **Forking the v0 file is fine** — copy the v0 contents into `src/components/<X>.tsx` and adapt them (server-component conversion, i18n, real data). The kebab-case filename is what matters.
5. **Different filename requires a waiver** — operators can list mappings in `gate_overrides.design-fidelity.aliases` in orchestration config to suppress per shell.

### Bad

Agent creates `src/components/search-bar.tsx` while v0 already has `components/search-palette.tsx` (modal CommandDialog pattern). The agent ends up with an inline dropdown instead of the design's modal — the fidelity gate flags `decomposition-shadow` violation.

### Good

Agent imports the existing component:

```tsx
import { SearchPalette } from "@/components/search-palette"  // mounted from v0
// ... wire data via useQuery, swap MOCK_PRODUCTS for /api/search results
```

The shell file stays structurally faithful; only data sourcing and i18n strings are adapted.

## No UX pattern reinterpretation

**If the v0 design uses a specific shadcn primitive, the implementation MUST use the same primitive.** Pattern divergence — even when "the alternative is more accessible" or "easier to implement" — is FORBIDDEN unless explicitly waived in `proposal.md`.

This is not a stylistic preference. The v0 design is the visual contract; reinterpreting `<CommandDialog>` as a "dropdown anchored to the input" is a design change, not an implementation detail.

### Caught by the fidelity gate

The `shadcn-primitive-missing` check tracks distinctive primitives — `CommandDialog`, `Sheet`, `HoverCard`, `Combobox`, `Drawer`, `ResizablePanel`, `ScrollArea`, `Stepper`, etc. If the v0 export imports one but **no file under `src/`** does, the gate emits `shadcn-primitive-missing` (WARN). Frequent offenders:

| v0 uses | Agent often substitutes | Why it's wrong |
|---|---|---|
| `CommandDialog` (Cmd+K modal palette) | Plain `Input` with a `Card` dropdown | Different keyboard model, different a11y, different visual hierarchy |
| `Sheet` (slide-in drawer) | `Dialog` (modal centered) | Wrong mobile UX — Sheet is the "edge drawer" pattern, Dialog is the "center modal" pattern |
| `HoverCard` (rich preview on hover) | `Tooltip` (label-only) | HoverCard supports rich content (avatar, links, badges); Tooltip is single-line text only |
| `Combobox` (search + select fused) | Two separate `Select`s, or `Input` + dropdown | Combobox is a single accessible widget with type-ahead filtering |
| `Drawer` (mobile-up modal sheet) | `Sheet` or `Dialog` | Drawer animation/direction differs |
| `ResizablePanel` | Static grid | User can't resize |
| `Stepper` (custom shadcn-blocks step UI) | `<div>Step 1/3</div>` | Stepper has a11y semantics + visual distinctiveness |

### If you genuinely need to diverge

Add a waiver in your `proposal.md`:

```yaml
design:
  primitive_waivers:
    - primitive: CommandDialog
      reason: "Mobile-first design — modal is too large on small viewports; using anchored dropdown instead"
      approved_by: "<operator name or @scaffold-author>"
```

The waiver is reviewed by the operator. Without it, divergence is a DESIGN BUG.

### What NOT to do

> "shadcn-style command palette layout, but rendered as a dropdown anchored to the input — not a modal `CommandDialog`"

This kind of phrasing in `design.md` is a red flag. You're announcing the divergence ahead of implementing it, which proves it's a deliberate design decision (not an accidental simplification). Either:
- (a) Use the v0 primitive as-is, OR
- (b) Get a waiver BEFORE writing this in design.md.

Never (c) "decide for the design" by yourself.

### Entity-reference markers in spec

The spec.md uses inline markers to bind to design entities:
- `@component:search-palette` — references a shell component (matches `manifest.shared`)
- `@route:/kereses` — references a manifest route

These markers are **mandatory references** — you must mount the named component, not invent a new one. The markers also surface in your `input.md` `Focus files for this change` section.

## Agent contract: integrator, not re-implementer

You **copy** the design source's TSX into the project, then adapt the integration layer around it. You do NOT rebuild the UI from a markdown spec.

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

## Reading order

1. **`v0-export/app/<your-route>/page.tsx`** — the canonical implementation for any UI you touch
2. **`v0-export/components/<component>.tsx`** — components the page imports
3. **`v0-export/components/ui/**`** — shadcn primitives (use these as-is)
4. **`v0-export/app/layout.tsx`** + **`globals.css`** — shared shell + tokens

If you need to see how other pages use a shared component for consistency — `Read` any file from `v0-export/`. Nothing is off-limits.

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
- **Never** modify files *inside* `v0-export/` itself — that directory is a read-only reference. Fix the issue in your own copy in `src/`.

If v0 shows the same concept inconsistently across pages (e.g. some pages use `<Button variant="default">`, others use `<button className="...">` with identical styling): **standardize on the shadcn primitive** across your worktree, document in the commit message. If that causes a fidelity gate failure, escalate to the scaffold author — the fix belongs in the v0 source, not in the agent worktree.

## Token source priority

When the framework injects design tokens into your input:

1. `v0-export/app/globals.css` (or `shadcn/globals.css`) — authoritative CSS variables
2. Optional `docs/design-brief.md` — **non-authoritative** vibe notes (brand personality, AVOID list). Never use this as spec.
3. If neither exists: use project shadcn/ui defaults; don't invent new variants.
