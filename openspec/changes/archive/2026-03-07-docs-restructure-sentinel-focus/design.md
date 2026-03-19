## Context

The current documentation is a single monolithic README.md (867 lines) that serves as landing page, tutorial, reference, and architecture doc simultaneously. A `docs/readme-guide.md` enforces a rigid 16-section structure that makes the README impossible to keep short. Several feature-specific docs already exist (`docs/sentinel.md`, `docs/orchestration.md`, `docs/developer-memory.md`, `docs/agent-messaging.md`) but they're not linked from a coherent navigation structure.

The project narrative has shifted from "GUI for managing terminal tabs" to "sentinel-driven autonomous orchestration." The docs need to reflect this.

Existing doc files:
- `README.md` — monolithic, GUI-centric narrative
- `docs/readme-guide.md` — generation guide enforcing 16-section structure
- `docs/sentinel.md` — sentinel supervisor docs (good, keep)
- `docs/orchestration.md` — orchestration guide (good, keep)
- `docs/developer-memory.md` — memory system docs (good, keep)
- `docs/agent-messaging.md` — messaging docs (merge into team-sync)
- `docs/config.md` — minimal config notes (expand)
- `docs/project-management.md` — consumer project setup (good, keep)
- `docs/planning-guide.md`, `docs/plan-checklist.md` — OpenSpec planning (keep as-is)
- `docs/project-knowledge.md` — project knowledge system (keep as-is)
- `docs/memory-seeding-guide.md` — memory bootstrap guide (keep as-is)
- `docs/benchmark-results.md` — benchmark data (keep as-is)

## Goals / Non-Goals

**Goals:**
- README under 200 lines — a landing page, not a manual
- Sentinel/orchestration as the lead narrative ("spec in, features out")
- Each major feature has its own dedicated doc page
- Clear "what goes where" — every piece of content has exactly one home
- `docs/readme-guide.md` updated to match new structure so README is regenerable
- Plugin section as extensibility point (placeholder for future plugin repos)
- Navigation: every doc page links back to README and to related pages

**Non-Goals:**
- Building a docs site (mkdocs, docusaurus, etc.) — plain markdown files are fine
- Rewriting existing good docs (sentinel.md, orchestration.md, developer-memory.md) — only add navigation headers and cross-links
- Changing any code or CLI behavior
- Creating actual plugins — only the docs/plugins.md placeholder

## Decisions

### D1: README structure — 10 sections max

The new README has these sections:
1. Header + tagline (sentinel-focused)
2. What & Why (5-7 sentences, sentinel-first)
3. Quick Start (5 commands)
4. Features (1-2 sentences each, link to doc page)
5. Plugins (3-5 sentences, link to docs/plugins.md)
6. Installation (brief, link to getting-started.md for details)
7. Platform Support (table)
8. Related Projects (collapsed `<details>`)
9. Contributing (1 line + link)
10. License

**Rationale**: The current 16-section structure is the root cause of bloat. Use Cases, CLI Reference, Architecture, Configuration, and Claude Code Integration all move to dedicated doc pages. The README becomes a routing table to the right doc.

**Alternative considered**: Keep README as comprehensive doc, add a separate "landing page" → rejected because README IS the landing page on GitHub.

### D2: Doc page inventory

| Page | Source | Status |
|------|--------|--------|
| `docs/getting-started.md` | New | Detailed install + first project + first run |
| `docs/sentinel.md` | Existing | Add nav header, minor updates |
| `docs/orchestration.md` | Existing | Add nav header |
| `docs/worktrees.md` | New | Worktree CLI reference + use cases from README |
| `docs/ralph.md` | New | Ralph loop guide (extracted from README) |
| `docs/developer-memory.md` | Existing | Add nav header |
| `docs/gui.md` | New | Control Center details (extracted from README) |
| `docs/team-sync.md` | New | Team Sync + absorb agent-messaging.md content |
| `docs/mcp-server.md` | New | MCP server setup and tools |
| `docs/plugins.md` | New | Plugin concept, install pattern, registry placeholder |
| `docs/cli-reference.md` | New | Full CLI command tables (moved from README) |
| `docs/configuration.md` | New | All config files, settings, orchestration.yaml |
| `docs/architecture.md` | New | Technical diagrams, layer model, tech stack |

**Rationale**: Each page is a self-contained topic. A user looking for "how do I configure the orchestrator" goes to configuration.md, not README line 396.

### D3: Navigation pattern — header + footer links

Each doc page gets:
- **Top**: `[< Back to README](../README.md)` + breadcrumb
- **Bottom**: "See also:" with links to related pages

No sidebar, no TOC generator — keep it simple markdown.

**Rationale**: Works on GitHub, no tooling needed, easy to maintain.

### D4: readme-guide.md — rewrite, not delete

The guide stays as the authoritative source for README generation, but rewrites to match the new 10-section structure. The guide ensures the README stays consistent when regenerated.

**Rationale**: The guide concept is good (regenerable README), the old content was the problem.

### D5: Content migration strategy

Content from the current README moves to specific doc pages:
- "How It Works" architecture → `docs/architecture.md`
- CLI Reference tables → `docs/cli-reference.md`
- Configuration section → `docs/configuration.md`
- Use Cases → distributed into respective feature doc pages
- Claude Code Integration → `docs/cli-reference.md` (skills section) + `docs/mcp-server.md`
- Related Projects + Feature Comparison → stays in README (collapsed)
- Future Development → `docs/architecture.md` (vision section)

### D6: agent-messaging.md handling

Content from `agent-messaging.md` merges into the new `docs/team-sync.md`. The old file gets a redirect note: "This content has moved to [team-sync.md](team-sync.md)."

**Rationale**: Messaging is part of team sync. Having a separate file fragments the topic.

### D7: Plugin docs structure

`docs/plugins.md` contains:
- What plugins are (extend set-core without modifying core)
- How to install a plugin (future: `wt-plugin install <repo>`)
- Plugin registry (table of known plugins with repo links — starts empty)
- How to create a plugin (brief, links to contributing)

This is a placeholder — no plugin system exists yet, but the doc page establishes the concept and gives plugin repos a place to be listed.

## Risks / Trade-offs

- **[Risk] External links break** → Acceptable. The README URL sections were not stable anyway. GitHub search still works.
- **[Risk] Information gets lost in migration** → Mitigation: diff old README against new docs to verify all content landed somewhere. Task includes a verification step.
- **[Risk] Too many doc pages for a small project** → Mitigation: Pages are only created if there's enough content to justify them. Empty pages are worse than missing ones.
- **[Risk] Navigation maintenance burden** → Mitigation: Simple header/footer links, no generated nav. Easy to update when adding pages.
- **[Trade-off] Collapsed Related Projects in README** → Saves space but reduces visibility. Acceptable — this section is reference, not discovery.
