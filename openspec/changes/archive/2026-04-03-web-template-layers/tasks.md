# Tasks: Web Template Layers

## Layer 1: Web Module Template Files

- [x] Create `modules/web/.../templates/nextjs/src/app/globals.css` — `@import "tailwindcss";`
- [x] Create `modules/web/.../templates/nextjs/src/lib/utils.ts` — cn() helper with clsx+tailwind-merge
- [x] Create `modules/web/.../templates/nextjs/src/lib/prisma.ts` — globalThis PrismaClient singleton
- [x] Create `modules/web/.../templates/nextjs/.env.example` — DATABASE_URL + NEXTAUTH_SECRET dev defaults
- [x] Create `modules/web/.../templates/nextjs/tests/e2e/global-setup.ts` — prisma generate + db push + seed
- [x] Update `modules/web/.../templates/nextjs/manifest.yaml` — add 5 new files to core section
- [x] Update `profile_deploy.py` `_target_path()` — already handles src/ and tests/ correctly (default path)
- [x] Test: run `set-project init` on a temp dir — all 5 files deployed to correct locations

## Layer 2: Scaffold Templates

- [x] Create `tests/e2e/scaffolds/minishop/templates/rules/minishop-conventions.md` — placeholder images, EUR, 6 products, 3 attribute types, Prisma schema hints, bcrypt admin auth
- [x] Create `tests/e2e/scaffolds/micro-web/templates/rules/micro-web-conventions.md` — no DB, no auth, static pages, minimal deps, hardcoded blog posts, client-side validation
- [x] Create `tests/e2e/scaffolds/craftbrew/templates/rules/craftbrew-conventions.md` — coffee types, roast levels, subscription model, HUF, Figma design system
- [x] Update `tests/e2e/runners/run-micro-web.sh` — add scaffold template deploy step after set-project init
- [x] Update `tests/e2e/runners/run-minishop.sh` — add scaffold template deploy step after set-project init
- [x] Update `tests/e2e/runners/run-craftbrew.sh` — add scaffold template deploy step after set-project init
- [x] Update `tests/e2e/runners/run-micro-blog.sh` — add scaffold template deploy step (if templates dir exists)

## Layer 3: Project-Level Template Override

- [x] Update `profile_deploy.py` — after template deployment, check for `.claude/project-templates/` and merge files on top
- [x] Log project template files with `[project-template]` prefix in deploy output
- [x] Add "Project Templates" section to `docs/plugins.md` — creation, file mapping, override priority, examples
- [x] Test: custom-rule.md deployed to `.claude/rules/custom-rule.md` ✅
- [x] Test: custom `src/lib/prisma.ts` overwrites module template version (grep confirms "audit") ✅
