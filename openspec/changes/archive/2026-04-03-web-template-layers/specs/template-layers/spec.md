# Spec: Web Template Layers

## Layer 1: Web Module Template Files

### REQ-L1-GLOBALS: globals.css template
- File: `modules/web/.../templates/nextjs/src/app/globals.css`
- Content: `@import "tailwindcss";`
- Deployed to: `src/app/globals.css` in target project
- Added to `manifest.yaml` core section

### REQ-L1-UTILS: lib/utils.ts template
- File: `modules/web/.../templates/nextjs/src/lib/utils.ts`
- Content: shadcn `cn()` helper (clsx + tailwind-merge)
- Deployed to: `src/lib/utils.ts` in target project
- Added to `manifest.yaml` core section

### REQ-L1-PRISMA: lib/prisma.ts template
- File: `modules/web/.../templates/nextjs/src/lib/prisma.ts`
- Content: globalThis PrismaClient singleton pattern
- Export name: `prisma` (matches `functional-conventions.md` rule)
- Deployed to: `src/lib/prisma.ts` in target project
- Added to `manifest.yaml` core section

### REQ-L1-ENV: .env.example template
- File: `modules/web/.../templates/nextjs/.env.example`
- Content: DATABASE_URL, NEXTAUTH_SECRET with dev defaults
- Deployed to: `.env.example` in target project
- Added to `manifest.yaml` core section

### REQ-L1-E2E-SETUP: e2e global-setup.ts template
- File: `modules/web/.../templates/nextjs/tests/e2e/global-setup.ts`
- Content: prisma generate → db push --force-reset → db seed
- Deployed to: `tests/e2e/global-setup.ts` in target project
- Added to `manifest.yaml` core section

### REQ-L1-MANIFEST: manifest.yaml update
- All 5 new files listed in manifest.yaml core section
- Existing files unchanged

### REQ-L1-DEPLOY: profile_deploy.py handles src/ paths
- `_target_path()` correctly maps `src/app/globals.css` → `<target>/src/app/globals.css`
- `_target_path()` correctly maps `tests/e2e/global-setup.ts` → `<target>/tests/e2e/global-setup.ts`
- Files in `src/` and `tests/` deploy to project root (not into `.claude/`)

## Layer 2: Scaffold Templates

### REQ-L2-MINISHOP: minishop scaffold conventions
- File: `tests/e2e/scaffolds/minishop/templates/rules/minishop-conventions.md`
- Content: placeholder images (placehold.co), EUR currency, 6 seed products, 3 attribute types, Prisma schema hints, bcrypt admin auth
- Frontmatter: paths trigger on `src/**`, `prisma/**`

### REQ-L2-MICROWEB: micro-web scaffold conventions
- File: `tests/e2e/scaffolds/micro-web/templates/rules/micro-web-conventions.md`
- Content: no database, no auth, no API routes, static pages only, minimal deps (next + react + tailwindcss), hardcoded blog posts array, client-side form validation only
- Frontmatter: paths trigger on `src/**`

### REQ-L2-CRAFTBREW: craftbrew scaffold conventions
- File: `tests/e2e/scaffolds/craftbrew/templates/rules/craftbrew-conventions.md`
- Content: coffee product types, roast levels, subscription model (weekly/bi-weekly/monthly), HUF currency, Figma design system reference, Hungarian locale
- Frontmatter: paths trigger on `src/**`, `prisma/**`

### REQ-L2-RUNNER: runner scripts deploy scaffold templates
- All 4 runner scripts (micro-web, minishop, craftbrew, micro-blog) gain a step after `set-project init`:
  ```bash
  if [[ -d "$SCAFFOLD_DIR/templates/rules" ]]; then
      cp "$SCAFFOLD_DIR/templates/rules/"*.md "$TEST_DIR/.claude/rules/"
  fi
  ```
- scaffold.yaml gains optional `templates.deploy_to` key (documentation only, runner handles deployment)

## Layer 3: Project-Level Template Override

### REQ-L3-DETECT: detect project-templates directory
- `profile_deploy.py` checks for `.claude/project-templates/` in the target project BEFORE deploying templates
- If directory exists, files are noted for post-deploy merge

### REQ-L3-MERGE: merge project templates after module deploy
- After standard template deployment completes, iterate `.claude/project-templates/` recursively
- Each file is mapped through `_target_path()` (same rules as module templates)
- Files overwrite module template files (project wins over module)
- Rules files go to `.claude/rules/` (no `set-` prefix — project rules are project-owned)
- Log deployed project template files with `[project-template]` prefix

### REQ-L3-DOCS: documentation for project templates
- Add "Project Templates" section to `docs/plugins.md` explaining:
  - How to create `.claude/project-templates/` directory
  - File mapping rules (same as module templates)
  - Override priority: project > module > core
  - Example: custom `src/lib/prisma.ts` with audit logging
- Console output during `set-project init` shows project template files deployed
