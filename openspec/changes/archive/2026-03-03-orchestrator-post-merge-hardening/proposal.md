## Why

The v7 sales-raketa orchestration run exposed 3 critical failure modes in the post-merge pipeline: (1) Prisma client not regenerated after schema merge, causing phantom build passes, (2) orchestrator marking a change as "merged" when only openspec artifacts landed but no implementation code, (3) sentinel removing smoke_command from orchestration.yaml — overstepping its supervisor role. These cost 0.8M tokens (lost change), 2 hours of manual intervention, and 3 orchestrator crashes.

## What Changes

- Add `post_merge_command` directive — project-specific command (e.g. `pnpm db:generate`) that runs after merge, after dep install, before build verification. Already partially implemented in code, needs directives persistence fix and documentation.
- Add scope verification to the merge gate — after merge, diff the actual changed files against the change's task scope to detect "merged but no implementation" scenarios.
- Harden sentinel role boundary — sentinel can observe, diagnose, clear transient errors, and restart, but MUST NOT modify project files, configs, or quality gates. If it can't fix with a simple restart, it stops and reports. Already partially updated in sentinel.md, needs spec coverage.

## Capabilities

### New Capabilities
- `post-merge-command`: Configurable project-specific command that runs in the post-merge pipeline between dependency install and build verification
- `scope-verify`: Post-merge validation that checks whether the change's implementation files actually landed in the merge diff

### Modified Capabilities
- `sentinel-polling`: Sentinel role boundary hardened — cannot modify orchestration config or project files, must stop and report instead
- `post-merge-verification`: Pipeline extended with post_merge_command hook point and scope verification step

## Impact

- `bin/set-orchestrate` — directive parsing, state persistence, merge flow
- `.claude/commands/wt/sentinel.md` — guardrails section
- `.claude/orchestration.yaml` in target projects — new `post_merge_command` directive
- Orchestration docs — new directive documentation
