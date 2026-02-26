## 1. Foundation — lib/audit/ and bin/wt-audit scaffolding

- [x] 1.1 Create `lib/audit/` directory with shared helpers: output formatting functions (status icons ✅/⚠️/❌, json builder, section headers), color support detection, and the common `add_check()` / `add_guidance()` pattern that all check functions use
- [x] 1.2 Create `bin/wt-audit` entry point — source `bin/wt-common.sh`, parse subcommands (`scan`, `help`), `--json` flag, detect project root (require wt-project registration), source all `lib/audit/check-*.sh` files, run them in sequence, output summary
- [x] 1.3 Create `lib/audit/reference.md` — target state description for all 6 dimensions: what a well-configured project looks like (categories to document, recommended agents/rules, config structure). Generic, no framework-specific content. This is what the LLM reads when creating missing files.

## 2. Check functions — one per dimension

- [x] 2.1 Create `lib/audit/check-claude-config.sh` — check `.claude/settings.json` for: permissions (allow/deny counts), memory hooks (wt-hook-memory presence), agents (list `.claude/agents/*.md` with name/model), rules (list `.claude/rules/*.md` distinguishing wt-managed vs project-specific). Guidance pointers for each missing item.
- [x] 2.2 Create `lib/audit/check-design-docs.sh` — check `docs/design/` for standard categories (ui-conventions, functional-conventions, data-model, deployment, code-hygiene). Report present files with line count + mtime, missing categories with READ source pointers based on detected stack.
- [x] 2.3 Create `lib/audit/check-openspec-config.sh` — check `openspec/config.yaml` exists, has non-empty `context` field, has `rules` section. Guidance to populate with detected stack info.
- [x] 2.4 Create `lib/audit/check-code-signals.sh` — find source files >400 lines (`.ts/.tsx/.js/.jsx/.py/.astro/.vue/.svelte`), check `package.json` for unused-code detection scripts (knip, depcheck). Report large files sorted by line count.
- [x] 2.5 Create `lib/audit/check-claude-md.sh` — check `CLAUDE.md` exists, contains convention references (links to design docs or convention sections), check for `@import` usage. Report structure quality.
- [x] 2.6 Create `lib/audit/check-gitignore.sh` — check `.gitignore` for sensitive patterns: `.env*`, `CLAUDE.local.md`, `.claude/settings.local.json`. Report missing patterns.

## 3. Stack detection

- [x] 3.1 Create `lib/audit/detect-stack.sh` — detect project stack from filesystem signals: framework config files (`next.config.*`, `astro.config.*`, `vite.config.*`), `package.json` dependencies (prisma, tailwind, shadcn, etc.), package manager (`pnpm-lock.yaml`, `yarn.lock`, `bun.lockb`), TypeScript (`tsconfig.json`). Export stack info as variables for check functions to use in guidance pointers.

## 4. JSON output

- [x] 4.1 Add `--json` output mode to `bin/wt-audit` — structured JSON with `project`, `timestamp`, `dimensions` (each with `checks` array and `sources`), and `summary` object with pass/warn/fail counts. All check functions populate a shared data structure that gets serialized at the end.

## 5. Skill — `/wt:audit`

- [x] 5.1 Create `.claude/commands/wt/audit.md` — command file that runs `wt-audit scan --json`, parses results, presents findings grouped by dimension, offers interactive remediation
- [x] 5.2 Update `.claude/skills/wt/SKILL.md` — add audit section describing the `/wt:audit` command and its capabilities

## 6. Integration — wt-project init

- [x] 6.1 Add post-deploy audit call to `bin/wt-project` init function — after existing deploy steps, check if `wt-audit` is in PATH, run `wt-audit scan` with condensed output (summary line only), suggest `/wt:audit` for details if gaps found

## 7. Install and test

- [x] 7.1 Add `wt-audit` to `install.sh` symlink creation (alongside other `bin/wt-*` tools)
- [x] 7.2 Manual verification: run `wt-audit scan` on at least 2 registered projects, verify correct stack detection, check count accuracy, and JSON output validity
