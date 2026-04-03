## Context

Consumer projects get 15+ rule files, commands, skills, and config after `set-project init`. But there's no meta-documentation explaining the structure to the project's own Claude agent. When projects build themselves incrementally (local `/opsx:*` sessions), the agent needs to understand what's managed vs. custom.

## Goals / Non-Goals

**Goals:**
- Single rule file that gives the consumer project agent full awareness of set-core structure
- Clear ownership boundaries (set-* = managed, rest = project-owned)
- Guidance for common extension patterns (adding rules, knowledge, domain conventions)

**Non-Goals:**
- Changes to deploy logic (existing mechanism works)
- Project-type-specific content in the guide (that's what project-type rules are for)
- Tutorial-style onboarding (the guide is a reference, not a walkthrough)

## Decisions

### D1: Single file, not multiple
One `project-guide.md` covering all topics. Not split into separate files per topic.

**Why:** This is reference material the agent reads once to understand the project structure. Splitting would create more files without adding value — the agent needs the complete picture, not fragments.

### D2: Deployed via existing core rules mechanism
The file goes in `templates/core/rules/project-guide.md` and the existing `deploy.sh` loop copies it as `set-project-guide.md`. No deploy code changes needed.

**Why:** The mechanism already exists and works correctly. Adding a file to `templates/core/rules/` is all that's needed.

### D3: Content structure
The guide covers these sections in order:
1. **What is this project** — set-core initialized, what that means
2. **File ownership** — set-* managed vs project-owned, with table
3. **Adding custom rules** — where and how, naming convention
4. **Project knowledge** — `set/knowledge/` and `project-knowledge.yaml`
5. **OpenSpec usage** — `/opsx:*` commands available, how to write changes
6. **Extending conventions** — domain-specific patterns (create rules, update knowledge)
7. **Config** — `set/orchestration/config.yaml` reference

**Why:** Ordered from "what is this" → "how do I use it" → "how do I extend it". An agent reading top-to-bottom gets progressively more actionable information.

## Risks / Trade-offs

- **[Risk] Guide becomes stale** → Mitigated by keeping it generic (references file patterns, not specific file names). Updates deploy automatically on next `set-project init`.
- **[Risk] Too much content** → Keep under 80 lines. This is a rule file, not documentation.

## Open Questions

None — this is a straightforward template addition.
