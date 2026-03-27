# Proposal: Web Template Layers

## Problem

Agent-ek minden orchestration runban újragenerálják a boilerplate fájlokat (`globals.css`, `lib/utils.ts`, `lib/prisma.ts`, `.env.example`, `e2e/global-setup.ts`). Ezek 100% azonosak minden runban — felesleges token használat és divergencia forrás (naming eltérések: `prisma.ts` vs `db.ts`, `validation.ts` vs `validate-contact.ts`).

Nincs mód projekt-specifikus szabályokat adni scaffold vagy valódi projekt szinten — minden a web module-ban van, ami túl általános egyedi projektekhez.

## Solution

Három rétegű template rendszer:

**Layer 1 — Web module template bővítés:** src/ boilerplate fájlok hozzáadása a web module template-hez. Ezeket `set-project init` deploy-olja, az agent nem kell generálja.

**Layer 2 — Scaffold templates:** E2E scaffold-okba (`tests/e2e/scaffolds/<name>/`) kerülnek a projekt-specifikus rules amik nem általánosak (pl. "EUR currency", "6 seed products", "placeholder images from placehold.co"). A runner script deploy-olja ezeket az init után.

**Layer 3 — Projekt-szintű template override:** Valódi projektek tartalmazhatnak `.claude/project-templates/` könyvtárat. A `set-project init` merge-eli ezeket a web module template fölé. Így egy fintech projekt PCI compliance rule-okat adhat hozzá anélkül, hogy a web module-t módosítaná.

## Scope

### Layer 1 (web module)
- `src/app/globals.css` — `@import "tailwindcss"`
- `src/lib/utils.ts` — shadcn `cn()` helper
- `src/lib/prisma.ts` — globalThis singleton PrismaClient
- `.env.example` — DATABASE_URL, NEXTAUTH_SECRET template
- `tests/e2e/global-setup.ts` — prisma generate + db push + seed
- `manifest.yaml` frissítés

### Layer 2 (scaffold templates)
- `scaffolds/minishop/templates/rules/minishop-conventions.md` — placeholder images, seed data conventions, EUR currency
- `scaffolds/micro-web/templates/rules/micro-web-conventions.md` — static pages, no DB, no auth
- `scaffolds/craftbrew/templates/rules/craftbrew-conventions.md` — coffee product types, subscription model, HUF currency
- Runner script-ek frissítése: scaffold templates deploy-olása init után

### Layer 3 (project-level override)
- `profile_deploy.py` módosítás: `.claude/project-templates/` felismerés és merge
- Dokumentáció: hogyan használható valódi projektekben

## Out of scope
- `package.json` template (npm init generálja)
- Route page-ek template-je (100% projekt-specifikus)
- layout.tsx template (metadata a spec-ből jön)
