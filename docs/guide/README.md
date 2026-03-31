[< Back to Index](../INDEX.md)

# Guides

How-to workflows for common tasks. Start with [Quick Start](quick-start.md) if this is your first time using set-core.

| Guide | Description |
|-------|-------------|
| [Quick Start](quick-start.md) | Install set-core and run your first autonomous orchestration |
| **[Writing Specs](writing-specs.md)** | **How to write specs that produce apps matching your vision** |
| [Design Integration](design-integration.md) | Bridge Figma designs to agents via `set-design-sync` |
| [Orchestration](orchestration.md) | The full pipeline: digest, decompose, dispatch, verify, merge |
| [Sentinel](sentinel.md) | Supervisor setup, crash recovery, and checkpoint handling |
| [Worktrees](worktrees.md) | Parallel development with git worktrees and the Ralph loop |
| [OpenSpec](openspec.md) | Artifact-driven development: proposal, specs, design, tasks |
| [Memory](memory.md) | Persistent cross-session memory with automatic hooks |
| [Issues](issues.md) | Self-healing issue pipeline: detect, investigate, fix, verify |
| [Dashboard](dashboard.md) | Web dashboard for real-time orchestration monitoring |
| [Team Sync](team-sync.md) | Multi-agent communication and cross-machine coordination |

## Reading Order

If you are new to set-core, read the guides in this order:

1. **[Quick Start](quick-start.md)** -- Install and see it work end to end
2. **[Writing Specs](writing-specs.md)** -- The most important guide — spec quality = output quality
3. **[Design Integration](design-integration.md)** -- Figma Make → design tokens → agents
4. **[OpenSpec](openspec.md)** -- Understand the artifact workflow agents follow
5. **[Orchestration](orchestration.md)** -- Deep dive into the autonomous pipeline
4. **[Sentinel](sentinel.md)** -- How the supervisor keeps runs on track
5. **[Worktrees](worktrees.md)** -- Manual worktree commands for hands-on work
6. **[Dashboard](dashboard.md)** -- Monitor everything from your browser
7. **[Memory](memory.md)** -- Cross-session recall for agents
8. **[Team Sync](team-sync.md)** -- Multi-agent coordination

## Related

- [CLI Reference](../reference/cli.md) -- All `set-*` command details
- [Configuration](../reference/configuration.md) -- `orchestration.yaml` reference
- [Architecture](../reference/architecture.md) -- System design and module structure
- [Screenshot Pipeline](../reference/screenshot-pipeline.md) -- How docs screenshots are generated
- [Examples](../examples/README.md) -- MiniShop walkthrough and first project setup

<!-- specs: documentation-system, guide-index -->
