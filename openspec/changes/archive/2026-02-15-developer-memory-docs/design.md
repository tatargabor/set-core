## Context

The shodh-memory integration is feature-complete across four layers: CLI (`set-memory`), GUI (browse/remember dialogs, [M] button), OpenSpec hooks (automatic recall/remember in 6 skill phases), and ambient CLAUDE.md instructions. Current documentation is a 9-line blurb in the README Features section plus a CLI command table. Users cannot discover how, when, or why to use developer memory without reading source code.

The README is generated/maintained using `docs/readme-guide.md` as the authoritative blueprint. If the guide doesn't contain detailed instructions for memory documentation, any README regeneration will revert to minimal content.

## Goals / Non-Goals

**Goals:**
- Create a standalone `docs/developer-memory.md` that a user can read end-to-end to understand and start using developer memory
- Structure the doc around concrete, realistic examples — not abstract descriptions
- Show exactly what happens automatically (OpenSpec hooks) vs what the user does manually
- Update `docs/readme-guide.md` so future README regeneration includes rich memory content
- Expand the README Developer Memory sections (Features, Use Cases, CLI Reference)

**Non-Goals:**
- Documenting shodh-memory internals (that's the upstream library's job)
- Documenting set-memory-hooks implementation details for contributors (except a brief architecture appendix)
- Changing any code or behavior
- Creating tutorial/video content

## Decisions

### 1. Two-tier documentation structure
Create `docs/developer-memory.md` as the deep-dive, keep README concise with links.

**Rationale**: The README is already long (670+ lines). A dedicated doc allows thorough coverage with examples while keeping the README scannable. This matches the existing pattern (`docs/agent-messaging.md` for Team Sync).

**Alternative considered**: Putting everything in the README — rejected because it would make the README unwieldy and the guide harder to maintain.

### 2. Example-first structure for the user guide
Each section in `docs/developer-memory.md` leads with a concrete scenario showing real commands and outputs, then explains the concept.

**Rationale**: Memory is an abstract concept ("agents remember things"). Concrete examples ("you tried RocksDB without locks, it crashed, you saved that, next month the agent avoids it") make the value immediately clear.

**Alternative considered**: Concept-first with examples at the end — rejected because users need to see the value before investing in understanding the system.

### 3. OpenSpec integration shown as a phase diagram + table
Use an ASCII flow diagram showing all 6 phases, then a detailed table with columns: Phase, Hook Type, What Happens, Example.

**Rationale**: The flow is the most complex part of the system. A diagram gives the big picture, the table gives precision. Users can scan the diagram to understand the flow, then look up specific phases in the table.

### 4. readme-guide.md gets detailed generation instructions
Add specific content rules for Developer Memory in each relevant section (Features, Use Cases, CLI Reference), not just a one-liner.

**Rationale**: The guide's purpose is to be enough context for an LLM to generate a conforming README. A one-liner produces a one-liner in output. Detailed instructions produce detailed content. This was validated by examining the current state — the guide has `Developer Memory — per-project remember/recall, OpenSpec hooks, GUI browse (experimental)` and the README has exactly that level of detail.

### 5. README gets a "Developer Memory" use case in Section 13
Add a new use case alongside existing ones (GUI, Ralph Loop, Team Sync) showing the memory workflow end-to-end.

**Rationale**: The Use Cases section is where users discover features through scenarios. Memory needs the same treatment as other major features.

## Risks / Trade-offs

- **Documentation drift** → Memory is still marked experimental. Documentation may drift from implementation as the feature evolves. Mitigation: the guide instructs README generators to check actual CLI commands against `bin/set-memory --help`.
- **Over-documenting** → Risk of making the docs longer than the feature warrants. Mitigation: keep the README section concise (link to deep-dive), keep the deep-dive focused on user-facing behavior with only a brief architecture appendix.
- **OpenSpec hooks change** → If hooks are modified, the phase diagram becomes stale. Mitigation: note in the doc that hooks are installed by `set-memory-hooks install` and may evolve.
