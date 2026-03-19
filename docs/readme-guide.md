# README Generation Guide

This document defines the structure, content rules, and style for `README.md`. It serves as the authoritative source for both manual edits and AI-assisted README generation.

---

## Mandatory Sections (in order)

The README MUST contain these sections in this exact order:

### 1. Header
- Project name: `# set-core`
- One-line tagline: what it does (autonomous multi-agent orchestration)
- MIT + Platform badges
- NO "Latest update" date — rely on git history

### 2. Why set-core?
- Problem → Solution narrative (3-4 sentences)
- Simple ASCII pipeline diagram (max 6 lines)
- Screenshot of orchestrator TUI
- "What makes it different" comparison table vs alternatives
- Keep it scannable — details live in doc pages

### 3. Quick Start
- Two paths: full orchestration (3 commands) and simple worktree usage (3 commands)
- Each step: one command + one-line comment
- Must be copy-pasteable
- Link to `docs/getting-started.md`

### 4. Core Features
- Each feature: heading + 2-3 sentence description + link to doc page
- Feature order (reflects importance):
  1. Sentinel & Orchestration
  2. Developer Memory
  3. OpenSpec Workflow
  4. Worktree Management
  5. Ralph Loop
  6. Control Center GUI
  7. Team Sync & MCP Server
- Include "When to use what" table

### 5. Fork & Adapt
- Credibility paragraph: production experience, battle-tested, actively maintained
- Why it's worth forking/copying from
- Who built/uses it

### 6. Installation
- Prerequisites list
- Clone + install.sh
- Platform & Editor Support table
- Link to getting-started.md

### 7. Plugins
- 2-3 sentences + link to docs/plugins.md

### 8. Documentation
- Table linking to all doc pages

### 9. Alternatives & Comparison
- Inside `<details>` collapsed section
- Two tables: Claude Code-specific tools, General orchestration
- Feature comparison matrix
- One-sentence positioning statement

### 10. Contributing
- One line + link to CONTRIBUTING.md

### 11. Acknowledgements
- 1-2 lines

### 12. License
- One line + link to LICENSE

---

## Line Budget

The README should be between **150 and 200 lines**. If content exceeds this budget, move it to the appropriate doc page and add a link.

Content that does NOT belong in the README:
- CLI command reference → `docs/cli-reference.md`
- Configuration details → `docs/configuration.md`
- Full architecture diagrams → `docs/architecture.md`
- Detailed use cases → respective feature doc pages

---

## Key Principles

1. **WHY → WHAT → HOW** — lead with the problem, show the solution, then explain how
2. **Differentiators first** — what makes set-core unique should be visible above the fold
3. **Copy-paste examples** — every code block must work if pasted
4. **Fork-friendly** — emphasize production experience and modularity
5. **Honest positioning** — don't overclaim; show the feature matrix and let it speak
6. **No dates** — they get stale; rely on git history and commit activity

---

## Doc Pages

| Page | Content |
|------|---------|
| `docs/getting-started.md` | Detailed install, prerequisites, first-run tutorial |
| `docs/sentinel.md` | Sentinel supervisor |
| `docs/orchestration.md` | Orchestration engine |
| `docs/openspec.md` | OpenSpec spec-driven development workflow |
| `docs/worktrees.md` | Worktree CLI and skills |
| `docs/ralph.md` | Ralph loop guide |
| `docs/developer-memory.md` | Memory system |
| `docs/gui.md` | Control Center GUI |
| `docs/team-sync.md` | Team sync and messaging |
| `docs/mcp-server.md` | MCP server tools |
| `docs/plugins.md` | Plugin system |
| `docs/cli-reference.md` | Complete CLI reference |
| `docs/configuration.md` | All config files and options |
| `docs/architecture.md` | Technical architecture |
| `docs/project-setup.md` | Project registration and templates |

---

## Tone & Style

1. **Language**: English only
2. **Voice**: Technical but accessible — assume the reader knows git and CLI
3. **Sentences**: Concise, active voice
4. **Formatting**: Tables for reference data, bullets for features, code blocks for commands
5. **Length**: Scannable. Use `<details>` for rarely-needed info
6. **Emoji**: Avoid

---

## Update Checklist

When modifying the README:

- [ ] All sections present and in order
- [ ] Line count is between 150-200
- [ ] Every feature links to its doc page
- [ ] Platform table is current
- [ ] Quick Start commands are copy-pasteable
- [ ] No broken internal links
- [ ] Comparison data is reasonably current
- [ ] "Fork & Adapt" section reflects actual state
