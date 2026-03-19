## Context

set-core deploys hooks, skills, and commands to projects via `set-project init`. But a "well-configured" project needs more than hooks — it needs design docs, path-scoped rules, code-reviewer agents, permission allowlists, OpenSpec config context, and verification hooks. Today these are created ad-hoc per project, often via dedicated OpenSpec changes (e.g. "claude-code-best-practices", "add-code-hygiene-rules"). There's no way to assess what's missing or stale.

The existing `set-project init` handles deploy (hooks, commands, skills) but not audit. `wt-deploy-hooks` handles the `.claude/settings.json` hook entries but doesn't check permissions, agents, or rules.

## Goals / Non-Goals

**Goals:**
- L1 bash scanner that checks 6 project health dimensions in <5 seconds
- Structured output (human-readable + `--json`) with evidence, delta, and guidance
- Modular check functions (one per dimension) for easy extension
- Reference doc describing target state so the LLM knows what "good" looks like
- `/wt:audit` skill for interactive LLM-driven gap remediation
- Post-init audit call in `set-project init`

**Non-Goals:**
- Generating design doc or rule FILE CONTENT (the LLM does that, not wt-audit)
- L2 content-quality analysis (requires LLM, not bash — the skill covers this)
- Runtime watch hooks (PostToolUse:Edit file-size checks etc.) — future change
- Score/percentage system — use ✅/⚠️/❌ status indicators instead
- Enforcing fixes — audit reports and guides, doesn't auto-modify

## Decisions

### 1. Modular check functions in `lib/audit/`

**Decision:** Each health dimension is a standalone bash function in its own file under `lib/audit/`. The main `bin/wt-audit` sources them all and runs them in sequence.

```
lib/audit/
  check-claude-config.sh    # permissions, hooks, agents, rules
  check-design-docs.sh      # docs/design/*.md existence + freshness
  check-openspec-config.sh  # config.yaml context population
  check-code-signals.sh     # file sizes, package.json scripts
  check-claude-md.sh        # CLAUDE.md structure, @import usage
  check-gitignore.sh        # sensitive file coverage
  reference.md              # target state description for LLM
```

**Why:** Each check is testable independently. New checks can be added without touching the main script. Projects can disable specific checks if needed.

**Alternative rejected:** Single monolithic script — harder to maintain, can't disable individual checks.

### 2. Output format: evidence + delta + guidance

**Decision:** Output has three sections per dimension:
- **Evidence**: what was found (file paths, line counts, config values)
- **Delta**: comparison against reference (✅ present, ⚠️ stale/incomplete, ❌ missing)
- **Guidance**: what the LLM should READ to create what's MISSING (source files, not templates)

**Why:** This is the core insight — wt-audit doesn't generate content, it provides the LLM with a "context package" pointing to sources. The same output works for init (many ❌) and update (some ⚠️).

**Alternative rejected:** Template generation (skeleton files with TODOs) — generic output that doesn't reflect the actual project. The LLM reading actual code produces better project-specific docs.

### 3. Guidance uses source pointers, not templates

**Decision:** Guidance entries look like:

```
GUIDANCE: Create docs/design/ui-conventions.md
  READ: src/components/**/*.tsx — find UI patterns, spacing, component structure
  READ: src/app/globals.css or tailwind.config.* — theme/color system
  READ: package.json — UI framework deps (shadcn, tailwind version)
  REFERENCE: lib/audit/reference.md#design-documentation — what to document
```

**Why:** The LLM reads actual project code and writes project-specific content. This works for any stack — the check function detects which files exist and points to them. The reference.md describes WHAT categories to document, not HOW to write the content.

**Alternative rejected:** Per-framework templates (Next.js template, Astro template) — combinatorial explosion, always incomplete.

### 4. Check detection uses filesystem signals only

**Decision:** L1 checks use only: file existence, line count (`wc -l`), modification time (`stat`), JSON parsing (`jq` or bash), grep for key patterns. No AST parsing, no npm install, no LLM calls.

**Why:** Must run in <5 seconds. Projects may not have deps installed. wt-audit should work on any project, any stack.

**Alternative rejected:** Running `tsc --noEmit` or `knip` — requires installed deps, slow, stack-specific.

### 5. Stack detection from package.json / config files

**Decision:** `wt-audit` detects the project's stack by checking for framework config files and package.json dependencies. This determines which guidance to provide (e.g., "READ astro.config.mjs" vs "READ next.config.ts").

Detection signals:
- `next.config.*` → Next.js
- `astro.config.*` → Astro
- `vite.config.*` → Vite
- `tsconfig.json` → TypeScript
- `package.json` deps: prisma, tailwind, shadcn, etc.

**Why:** Guidance must point to the right config files. A Next.js project's deployment docs differ from an Astro project's.

### 6. `/wt:audit` skill as thin wrapper

**Decision:** The skill runs `wt-audit scan --json`, formats the output as context, then prompts the LLM to address findings. It does NOT auto-create files — it presents the evidence and asks what the user wants to fix.

**Why:** Interactive mode lets the user prioritize. Some gaps are intentional (no deploy docs for a library). The LLM applies judgment that bash can't.

### 7. `--json` output for machine consumption

**Decision:** `wt-audit scan --json` outputs structured JSON with all evidence, making it consumable by skills, hooks, and other tools.

```json
{
  "project": "eg-sales",
  "timestamp": "2026-02-26T14:00:00Z",
  "dimensions": {
    "claude_config": {
      "checks": [
        { "id": "permissions", "status": "pass", "detail": "11 allow, 1 deny" },
        { "id": "verify_hook", "status": "fail", "detail": "No PostToolUse:Edit/Write verification hook" }
      ],
      "sources": [".claude/settings.json"]
    }
  },
  "summary": { "pass": 12, "warn": 3, "fail": 2 }
}
```

**Why:** Skills and hooks need structured data. Human output is derived from the same data with formatting.

## Risks / Trade-offs

- **[Risk] Reference.md becomes stale** → Mitigated by keeping it concise (categories only, not framework-specific details). The guidance section in check functions handles framework specifics.
- **[Risk] Stack detection is imperfect** → Accept false negatives. Unknown stack = generic guidance. Projects can always run the skill for LLM-assisted detection.
- **[Risk] Too many warnings feel noisy** → Group by dimension, show summary counts first. User can drill into dimensions.
- **[Risk] Guidance pointers may point to non-existent files** → Check functions verify file existence before suggesting `READ`. Use glob patterns as fallback (e.g., "READ src/components/**/*.tsx" even if we can't enumerate them all).
