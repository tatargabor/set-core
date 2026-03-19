## 1. Help Command File

- [x] 1.1 Create `.claude/commands/wt/help.md` with quick reference content covering: CLI Commands section (all user-facing wt-* tools with one-line descriptions), Skills section (/opsx:* and /wt:* with one-line descriptions), MCP Tools section (set-memory and set-core MCP tools), Common Workflows section (typical task sequences)
- [x] 1.2 Verify help.md lists all required CLI tools: wt-new, wt-list, wt-work, wt-close, wt-merge, wt-status, set-memory, wt-loop, wt-control, set-project, wt-usage, wt-config
- [x] 1.3 Verify help.md lists all required skills and MCP tools per spec

## 2. CLAUDE.md Help Router

- [x] 2.1 Add "Help & Documentation" section to CLAUDE.md with routing rules (max 10 lines): CLI questions → wt-* --help or /wt:help, skill questions → SKILL.md or /wt:help, memory questions → docs/developer-memory.md, general overview → /wt:help
- [x] 2.2 Verify the help router section is 10 lines or fewer

## 3. Verification

- [x] 3.1 Verify help.md auto-deploys by checking it's in `.claude/commands/wt/` (no changes to bin/set-project needed)
- [x] 3.2 Verify help.md content is accurate against current bin/wt-* scripts and available skills
