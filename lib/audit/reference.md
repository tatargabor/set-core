# Project Health Reference

What a well-configured Claude Code project looks like. This is the target state
that `set-audit` checks against. When creating missing files, read the actual
project code and describe what you find — don't copy this document.

## Claude Code Config

### Permissions
- Safe build/test/lint commands allowed (stack-specific: pnpm/npm/bun + framework CLI)
- Git read commands allowed (status, diff, log)
- Git write commands allowed (add, commit) for auto-commit workflow
- Dangerous commands denied (rm -rf, force push)
- OpenSpec CLI allowed if project uses OpenSpec

### Hooks
- Memory hooks on all events (deployed by set-deploy-hooks)
- TypeScript verification hook on PostToolUse:Edit and PostToolUse:Write (runs tsc --noEmit)

### Agents
- **code-reviewer** (sonnet model): Project-specific review checklist covering:
  - Redundancy detection (duplicate logic, existing utils)
  - File size limits (400 lines guideline)
  - Unused code (imports, exports, cascading cleanup)
  - Design doc consistency (code matches docs/design/*.md)
  - Project-specific patterns (auth guards, DB access, error handling)
  - Security (injection, secrets, XSS, auth)

### Rules
- Path-scoped rules for distinct code areas (e.g., UI components, API routes, database)
- Each rule has `paths:` frontmatter with glob patterns
- Rules provide targeted context so the LLM gets relevant conventions per file

## Design Documentation

Located in `docs/design/`. Each file documents ACTUAL patterns found in the codebase.

### Categories

- **ui-conventions.md** — UI framework, component library, spacing system, color/theme tokens, layout patterns, common component patterns (tables, forms, dialogs, cards), icon usage, responsive behavior
- **functional-conventions.md** — Server/API patterns (actions, handlers, middleware), auth flow, database access pattern, error handling, background jobs, external integrations, file/folder organization
- **data-model.md** — Database schema overview, entity relationships, state machines, JSON field structures, migration conventions
- **deployment.md** — Deploy target (Docker, Vercel, Railway, etc.), environment variables, build commands, local dev setup
- **code-hygiene.md** — File size limits, search-before-create policy, no copy-paste rule, cascading cleanup on deletion, dead code detection tooling, code review checklist

## OpenSpec Config

`openspec/config.yaml` should have:
- `context:` field with: tech stack, runtime, language conventions, domain description, key patterns, design doc references, testing setup, deploy target
- `rules:` section with artifact-specific guidelines (proposal length, design decisions format, spec scenario format, task granularity)

## CLAUDE.md Structure

- Convention summaries pointing to design docs (not duplicating content)
- Source of truth table (where to find what)
- Managed sections from set-core (Persistent Memory, Auto-Commit)
- Optional: @import for automatic doc loading

## Gitignore Coverage

Must include:
- `.env*` — environment secrets
- `CLAUDE.local.md` — personal Claude instructions
- `.claude/settings.local.json` — personal Claude settings
