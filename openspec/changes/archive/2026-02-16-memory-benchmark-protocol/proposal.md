## Why

The shodh-memory system is integrated into set-core and OpenSpec workflows, but there is no empirical evidence showing its value. We need a reproducible benchmark that demonstrates how persistent developer memory helps AI agents avoid repeated mistakes, dead ends, and design rework across independent sessions. Beyond measuring value, the benchmark must also serve as a diagnostic tool — identifying where memory fell short, what types of knowledge were missing, and what improvements the memory system needs.

## What Changes

- Add a `benchmark/` directory containing a complete benchmark protocol for evaluating shodh-memory effectiveness
- Define a multi-change test project ("CraftBazaar" — multi-vendor artisan marketplace) with known complexity traps
- Provide two CLAUDE.md variants: baseline (no memory) and with-memory (proactive memory enabled)
- Include a scoring rubric, session annotation templates, and comparison report templates
- Include per-change trap documentation so evaluators know what to look for
- Include a diagnostic framework for analyzing memory gaps and improvement opportunities
- Provide a step-by-step run guide covering full toolchain bootstrap (openspec init, set-core init, memory hooks, openspec hooks)
- Include a project-spec document that serves as the initial brief for the test project

## Capabilities

### New Capabilities
- `benchmark-protocol`: The master benchmark protocol — run guide, scoring rubric, diagnostic framework, and CLAUDE.md variants for with/without memory runs
- `benchmark-project-spec`: The CraftBazaar project specification and per-change definitions with trap documentation and acceptance criteria

### Modified Capabilities
<!-- No existing capabilities are modified — this is purely additive documentation -->

## Impact

- New `benchmark/` directory at project root (documentation only, no code changes)
- No changes to existing tools, scripts, or GUI
- No changes to existing specs or OpenSpec configuration
- The benchmark project (CraftBazaar) will be a separate repository — only the protocol and project spec live here
