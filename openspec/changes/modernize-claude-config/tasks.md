## 1. Create path-scoped rules files

- [x] 1.1 Create `.claude/rules/gui/testing.md` with YAML frontmatter `paths: ["gui/**", "tests/gui/**"]` containing GUI test command, trigger words, test patterns, and "do not run automatically" directive — extracted from CLAUDE.md lines 38-45
- [x] 1.2 Create `.claude/rules/gui/dialogs.md` with YAML frontmatter `paths: ["gui/**"]` containing the macOS Always-On-Top Dialog Rule with all three patterns (system dialogs, custom QDialogs, custom subclasses) — extracted from CLAUDE.md lines 64-83
- [x] 1.3 Create `.claude/rules/gui/debug-startup.md` with YAML frontmatter `paths: ["gui/**"]` containing GUI debug log info (location, rotation, logging setup) and startup commands (wt-control, PYTHONPATH, troubleshooting) — extracted from CLAUDE.md lines 96-143
- [x] 1.4 Create `.claude/rules/openspec-artifacts.md` with YAML frontmatter `paths: ["openspec/**"]` containing the "no project-specific content" rule — extracted from CLAUDE.md lines 47-49
- [x] 1.5 Create `.claude/rules/readme-updates.md` with YAML frontmatter `paths: ["README.md", "docs/readme-guide.md"]` containing the README update procedure — extracted from CLAUDE.md lines 85-94

## 2. Create custom subagent definitions

- [x] 2.1 Create `.claude/agents/code-reviewer.md` with frontmatter: name, description, tools (Read, Grep, Glob), model (sonnet) — body with review focus areas (code quality, PySide6/Qt patterns, security, bash conventions)
- [x] 2.2 Create `.claude/agents/gui-tester.md` with frontmatter: name, description, tools (Bash, Read, Grep, Glob), model (haiku), maxTurns (5) — body with pytest command and reporting instructions
- [x] 2.3 Create `.claude/agents/openspec-verifier.md` with frontmatter: name, description, tools (Read, Grep, Glob, Bash), model (sonnet) — body with artifact-implementation coherence verification instructions

## 3. Slim down CLAUDE.md

- [x] 3.1 Remove GUI Testing section (lines 38-45) from CLAUDE.md — content now in rules/gui/testing.md
- [x] 3.2 Remove macOS Always-On-Top Dialog Rule section (lines 64-83) from CLAUDE.md — content now in rules/gui/dialogs.md
- [x] 3.3 Remove GUI Debug Log section (lines 96-113) from CLAUDE.md — content now in rules/gui/debug-startup.md
- [x] 3.4 Remove GUI Startup section (lines 115-143) from CLAUDE.md — content now in rules/gui/debug-startup.md
- [x] 3.5 Remove OpenSpec Artifacts section (lines 47-49) from CLAUDE.md — content now in rules/openspec-artifacts.md
- [x] 3.6 Remove README Updates section (lines 85-94) from CLAUDE.md — content now in rules/readme-updates.md
- [x] 3.7 Add "Compact Instructions" section to CLAUDE.md after Auto-Commit section — instruct Claude to preserve current change name, modified files, active worktree path, test results during compaction

## 4. Add new hooks to settings.json

- [x] 4.1 Add SessionStart hook entry with `"matcher": "compact"` calling `wt-hook-memory SessionStart` with timeout 10 — append to existing SessionStart array in `.claude/settings.json`
- [x] 4.2 Add SubagentStart hook entry with `"matcher": ""` calling `wt-hook-memory SubagentStart` with timeout 10 — new event key in `.claude/settings.json`
- [x] 4.3 Add SubagentStart event handling to `wt-hook-memory` script — read subagent task description from stdin, perform proactive context recall, output relevant memories as additionalContext

## 5. Optimize skill frontmatter

- [x] 5.1 Add `context: fork` and `agent: Explore` to `.claude/skills/openspec-explore/SKILL.md` frontmatter (after the existing fields)
- [x] 5.2 Add `disable-model-invocation: true` to `.claude/skills/openspec-onboard/SKILL.md` frontmatter
- [x] 5.3 Add `disable-model-invocation: true` to `.claude/skills/openspec-bulk-archive-change/SKILL.md` frontmatter
- [x] 5.4 Add `disable-model-invocation: true` to `.claude/skills/openspec-sync-specs/SKILL.md` frontmatter

## 6. Update wt-project init deployment

- [x] 6.1 Add rules deployment to `deploy_wt_tools()` in `bin/wt-project` — copy `.claude/rules/` from wt-tools repo to target project, with `wt-` prefix for non-self targets, preserving subdirectory structure
- [x] 6.2 Add agents deployment to `deploy_wt_tools()` in `bin/wt-project` — copy `.claude/agents/` from wt-tools repo to target project
- [x] 6.3 Update `wt-deploy-hooks` to include SubagentStart and SessionStart[compact] hook entries in the deployed settings.json

## 7. Verification

- [x] 7.1 Verify all 5 rules files exist with correct YAML frontmatter and content matches original CLAUDE.md sections
- [x] 7.2 Verify all 3 agent files exist with correct YAML frontmatter and meaningful instructions
- [x] 7.3 Verify CLAUDE.md is ~60-80 lines with only universal sections remaining
- [x] 7.4 Verify `.claude/settings.json` has both new hook entries and all existing hooks are unchanged
- [x] 7.5 Verify skill frontmatter changes are syntactically valid YAML
