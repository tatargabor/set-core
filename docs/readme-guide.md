# README Generation Guide

This document defines the structure, content rules, and style for `README.md`. It serves as the authoritative source for both manual edits and AI-assisted README generation.

---

## Mandatory Sections (in order)

The README MUST contain these 10 sections in this exact order:

### 1. Header
- Project name: `# wt-tools`
- Sentinel-focused tagline (e.g., "Autonomous multi-change orchestration for Claude Code")
- "Latest update" date badge

### 2. Overview
- 5-7 sentences explaining what wt-tools is
- **Sentinel-first narrative**: lead with autonomous orchestration ("give it a spec, get merged features"), not the GUI
- Mention modularity: users cherry-pick what they need
- Mention Developer Memory with benchmark result (+34% convention compliance)
- Simple ASCII architecture diagram (sentinel-centric, max 10 lines)
- NO screenshots on the main README — GUI images belong in `docs/gui.md`
- Keep it high-level — details live in doc pages

### 3. Quick Start
- 5 steps maximum
- Sentinel workflow as the primary path (install, init, run sentinel)
- Each step: one command + one-line comment
- Must be copy-pasteable
- Link to `docs/getting-started.md` for detailed instructions

### 4. Features
- 1-2 sentences per feature, each linking to its dedicated doc page
- **Feature order** (reflects priority, not alphabetical):
  1. Sentinel & Orchestration → `docs/sentinel.md`, `docs/orchestration.md`
  2. Project Setup → `docs/project-setup.md`
  3. OpenSpec Workflow → `docs/openspec.md`
  4. Worktrees → `docs/worktrees.md`
  5. Ralph Loop → `docs/ralph.md`
  6. Developer Memory → `docs/developer-memory.md`
  7. Control Center GUI → `docs/gui.md`
  8. Team Sync & Messaging → `docs/team-sync.md`
  9. MCP Server → `docs/mcp-server.md`
- Include a "When to use what" summary table after features
- No CLI reference here — link to `docs/cli-reference.md`
- No configuration details — link to `docs/configuration.md`

### 5. Plugins
- 3-5 sentences explaining the plugin concept
- Link to `docs/plugins.md`

### 6. Installation
- Brief prerequisites list (Git, Python 3.10+, jq, Node.js)
- Clone + install.sh commands
- Link to `docs/getting-started.md` for full guide (GUI deps, platform notes)

### 7. Platform Support
- Table format with status indicators:

| Platform/Tool | Status | Notes |
|---------------|--------|-------|
| Linux | Primary | |
| macOS | Supported | |
| Windows | Not supported | |
| Zed | Primary editor | |
| VS Code | Basic support | |
| Claude Code | Integrated | |

### 8. Related Projects
- Inside a `<details>` collapsed section
- Categorized tables: Worktree+Agent Managers, Multi-Agent Orchestration, Desktop Apps
- Feature comparison matrix (ASCII table)
- Update periodically

### 9. Contributing
- One line + link to `CONTRIBUTING.md`

### 10. License
- One line + link to LICENSE file

---

## Line Budget

The README MUST be between **150 and 200 lines**. If content exceeds this budget, move it to the appropriate doc page and add a link.

Content that does NOT belong in the README:
- CLI command reference → `docs/cli-reference.md`
- Configuration details → `docs/configuration.md`
- Architecture diagrams (full) → `docs/architecture.md`
- Use cases → respective feature doc pages
- Future Development → `docs/architecture.md`

---

## Architecture Diagram

The README contains a **simplified** sentinel-centric diagram (max 10 lines ASCII):

```
spec.md → sentinel → orchestrate → worktrees (parallel) → merged features
```

The full 4-layer architecture diagram lives in `docs/architecture.md`.

---

## Doc Pages

The README links to these doc pages. Each page is self-contained with navigation header and footer.

| Page | Content |
|------|---------|
| `docs/getting-started.md` | Detailed install, prerequisites, first-run tutorial |
| `docs/sentinel.md` | Sentinel supervisor |
| `docs/orchestration.md` | Orchestration engine |
| `docs/project-setup.md` | Project registration, templates, scraping |
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
| `docs/architecture.md` | Technical architecture and vision |
| `docs/project-management.md` | Consumer project maintenance (legacy — see project-setup.md) |

---

## Tone & Style

1. **Language**: English only
2. **Voice**: Technical but accessible — assume the reader knows git and CLI basics
3. **Sentences**: Concise, active voice
4. **Formatting**: Tables for reference data, bullets for features, code blocks for commands
5. **Jargon**: Define project-specific terms on first use
6. **Length**: Scannable. Use `<details>` for rarely-needed info
7. **Emoji**: Avoid in prose. OK in status indicators

---

## Update Checklist

When modifying the README:

- [ ] All 10 sections present and in order
- [ ] "Latest update" date is current
- [ ] Line count is between 150-200
- [ ] Every feature links to its doc page
- [ ] Platform Support table is current
- [ ] Quick Start commands are copy-pasteable
- [ ] No broken internal links
- [ ] Architecture diagram is simple (max 10 lines)
- [ ] Related Projects is inside `<details>`

---

## AI Generation Instructions

When using an LLM to regenerate the README:

1. Provide this guide as context
2. Provide the current doc pages listing for link accuracy
3. The LLM should follow the 10-section order exactly
4. Output should be a complete, standalone README.md
5. Verify line count is within budget (150-200 lines)
