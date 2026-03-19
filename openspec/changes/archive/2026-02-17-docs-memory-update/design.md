## Context

Three completed changes need documentation:

1. **`memory-dedup-audit`**: Added `set-memory audit` (diagnostic report: duplicate clusters, redundancy stats) and `set-memory dedup` (remove duplicates with dry-run, interactive, threshold support).
2. **`save-hook-staging`**: Added staging+debounce pattern to transcript extraction, reducing Haiku calls from ~25/session to ~6-10/session.
3. **`set-project-init-deploy`**: Enhanced `set-project init` to deploy hooks, commands, and skills per-project (copy, not symlink). Re-running = idempotent update. `install.sh` no longer creates global `/wt:*` symlinks.

The GUI now shows colored badges in the "Extra" column of project header rows: `[M]` (memory available, blue), `[O]` (OpenSpec initialized, teal), `[R]` (Ralph running, red). A user-provided screenshot captures this.

The Setup section in `docs/developer-memory.md` has individual commands but no step-by-step happy-flow guides. And there's no explanation of how set-memory relates to Claude Code's built-in memory (CLAUDE.md + auto memory at `~/.claude/projects/<project>/memory/`), which causes confusion.

## Goals / Non-Goals

**Goals:**
- Document `audit` and `dedup` in all three doc files (developer-memory.md, README.md, readme-guide.md)
- Add happy-flow command sequences for 3 scenarios: fresh init, add memory, post-update hook reinstall
- Add screenshot showing M/O/R badges to developer-memory.md GUI section
- Document staging pattern in the automatic hooks section
- Add "How set-memory differs from Claude Code memory" comparison section
- Update README to reflect `set-project init` now deploying hooks+commands+skills

**Non-Goals:**
- Changing any code or behavior
- Rewriting existing documentation sections beyond what's needed
- Adding the screenshot to the README (keep README lightweight — screenshot goes in the detailed guide only)
- Full rewrite of README Quick Start or Installation — just update `set-project init` description

## Decisions

### D1: Screenshot placement — developer-memory.md GUI section only

**Choice**: Add the screenshot to `docs/developer-memory.md` under the `## GUI` heading, not in the README.

The README already has multiple screenshots and the Developer Memory subsection is kept compact per readme-guide.md instructions. The detailed guide is the right place for a badge-focused screenshot.

### D2: Happy-flow section structure — three numbered flows under Setup

**Choice**: Add a `### Quick Setup Flows` subsection after the existing "3. Install OpenSpec hooks" step in the Setup section. Three flows: (A) Fresh project, (B) Add memory to existing, (C) After OpenSpec update. Each flow is a numbered command sequence with one-line explanations.

### D3: Staging pattern docs — add to existing "Automatic memory hooks" subsection

**Choice**: Extend the `wt-hook-memory-save` description in the existing automatic hooks section to mention the staging+debounce behavior. Keep it brief — one paragraph explaining the staging file mechanism and why it exists (prevents duplicate extractions).

### D4: CLI reference entries — match existing table format

**Choice**: Add `audit` and `dedup` to the existing table structure in each file:
- `developer-memory.md`: Add to CLI Reference under a new "Diagnostics:" row in the set-memory table
- `README.md`: Add two rows to the Developer Memory CLI table
- `readme-guide.md`: Add `set-memory audit` and `set-memory dedup` to the mandatory CLI list

### D5: Comparison section placement — after Quick Start, before "When Is It Useful?"

**Choice**: Add a new `## How set-memory Differs from Claude Code Memory` section in `developer-memory.md` right after the Quick Start. This is the first question a new user has — "why do I need this when Claude already has memory?"

Content structure: one-paragraph framing ("complementary, not competing"), then a comparison table (storage, recall, structure, scale, worktrees, team, lifecycle), then a short paragraph about when to use which.

Key messages:
- CLAUDE.md/auto memory = **instructions** (always loaded, deterministic, 200-line cap)
- set-memory = **experience** (searched on demand, semantic, scales to 1000s)
- Worktree sharing is a major differentiator: Claude auto memory isolates worktrees, set-memory shares across same-repo worktrees
- They work together — CLAUDE.md tells agents how to behave, set-memory tells them what happened before

### D6: `set-project init` docs — minimal README touch

**Choice**: Update the `set-project init` description in README Quick Start and CLI Reference to mention it now deploys hooks+commands+skills (not just registers). The happy-flow guides in developer-memory.md will use `set-project init` instead of separate `wt-deploy-hooks`.

### D7: Happy flows use `set-project init` as the deploy step

**Choice**: Since `set-project init` now handles `wt-deploy-hooks` internally, the happy-flow commands simplify:
- Flow A: `pip install shodh-memory` → `set-project init` → `wt-openspec init` → `set-memory-hooks install` → verify
- Flow B: `pip install shodh-memory` → `set-project init` (re-run to update) → `set-memory-hooks install` → verify
- Flow C: `wt-openspec update` → `set-memory-hooks install` → verify

## Risks / Trade-offs

- **[Screenshot filename]** → Using `control-center-memory.png` following existing naming convention. User must save the screenshot to `docs/images/` before apply.
- **[README CLI table completeness]** → Past memory notes that "README audit found 5+ missing CLI commands." This change only adds audit/dedup — a broader CLI audit is out of scope.
- **[Comparison section may go stale]** → Claude Code's memory system evolves. The comparison should state the reference date and link to Claude Code docs.
