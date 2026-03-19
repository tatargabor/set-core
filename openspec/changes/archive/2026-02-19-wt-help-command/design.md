## Context

Documentation for set-core is scattered across multiple locations: SKILL.md files (loaded on skill invocation), CLI `--help` flags, `docs/*.md` guides, and README.md. When an LLM is asked "how does X work?", it has no routing instruction telling it where to find the answer. The existing deployment mechanism (`set-project init`) already copies `.claude/commands/wt/*.md` to target projects, so adding a new command file requires zero deployment changes.

## Goals / Non-Goals

**Goals:**
- LLM can answer "how does X work?" questions about any set-core feature
- Works in both set-core repo and deployed projects (via existing deploy mechanism)
- Minimal context overhead (on-demand, not always-loaded)

**Non-Goals:**
- Interactive help system (search, filtering)
- Auto-generating help from source code or --help output
- Replacing existing detailed docs (docs/developer-memory.md, etc.)
- Modifying the deployment mechanism in `bin/set-project`

## Decisions

### D1: `/wt:help` command file over dedicated skill or CLAUDE.md inline

**Choice:** `.claude/commands/wt/help.md`

**Alternatives considered:**
- CLAUDE.md inline (~50-80 lines): Always loaded → context waste on every session
- Dedicated skill (`.claude/skills/wt-help/SKILL.md`): Requires deployment changes, separate skill maintenance
- MCP resource: Overkill, not user-invocable

**Rationale:** Command files in `.claude/commands/wt/` are already deployed by `deploy_set_tools()`. Zero deployment changes needed. Content loads on-demand when user types `/wt:help`, not on every session.

### D2: CLAUDE.md help router section (~5-10 lines)

**Choice:** Small section in CLAUDE.md that tells the LLM where to look when asked help questions.

**Rationale:** CLAUDE.md loads every session. A 5-10 line router adds negligible context cost but enables the LLM to proactively find answers even without the user typing `/wt:help`.

### D3: Help content structure — categorized quick reference

**Choice:** Organize help.md by category: CLI Commands, Skills, MCP Tools, Workflows.

**Rationale:** Users ask about specific tools, not about architecture. Category-based organization maps directly to how questions are asked: "what CLI commands are there?" / "what does /opsx:apply do?".

### D4: Help content scope — deployed tools only

**Choice:** Only document tools/skills/commands that are available in deployed projects (what users actually encounter), plus set-core-internal ones marked as such.

**Rationale:** The help command deploys to target projects. Users there shouldn't see docs about internal set-core development commands they don't have.

## Risks / Trade-offs

- **[Staleness]** help.md content can drift from actual tools → Mitigation: Keep descriptions brief (1-line per tool), link to detailed docs. Less content = less drift.
- **[Size]** help.md could grow large → Mitigation: Quick reference format (1-2 lines per item), not full documentation. Deep details stay in docs/ and SKILL.md files.
