## Why

E2E run logs show LLM agents re-discovering the same Next.js/Prisma/Tailwind configuration issues on every run — consuming verify retries, triggering interventions, and wasting tokens. The `wt-project-web` plugin exists but its rules never reach the agent, and the dispatcher ignores `project-knowledge.yaml` entirely. Additionally there is no visibility into per-change context window utilization, making it impossible to detect when agent performance degrades due to context pressure.

## What Changes

- **wt-project-web template corrections**: Fix `postcss.config.mjs` (Tailwind v4 syntax), `jest.config.ts` (correct key + node env for Prisma), `next.config.js` (common defaults). Extend `data-model.md` and `testing-conventions.md` rules with worktree-specific guidance. Add new `worktree-setup.md` rule covering db init, port conflicts, pnpm env.
- **Feature rules injection at dispatch**: The dispatcher reads `project-knowledge.yaml`, matches the change's `proposal.md` file paths against feature `touches` globs, and injects the matching `rules_file` content into the worktree's `.claude/rules/` before the agent starts.
- **Context window metrics per change**: At Ralph loop start and end, record context window utilization (tokens used / window size) into the change's orchestration state entry. Display in wt-web change list.

## Capabilities

### New Capabilities
- `nextjs-template-corrections`: Correct template files and rules in `wt-project-web` to eliminate per-run rediscovery of known Next.js/Prisma/Tailwind configuration issues
- `feature-rules-injection`: Dispatcher injects path-scoped rules from `project-knowledge.yaml` features into the worktree at dispatch time, so agents receive relevant conventions without requiring manual context
- `context-window-metrics`: Ralph loop records context window start/end utilization per change session; orchestration state stores it; wt-web displays it alongside token counts

### Modified Capabilities
- `project-knowledge`: R3 (Features Section) gains concrete dispatch behavior — `rules_file` is actively injected at dispatch time, not just described as "used for context injection"

## Impact

- **wt-project-web** (`wt_project_web/templates/nextjs/`): postcss.config.mjs, jest.config.ts, next.config.js, rules/data-model.md, rules/testing-conventions.md, new rules/worktree-setup.md
- **wt-tools dispatcher** (`lib/wt_orch/dispatcher.py`): reads project-knowledge.yaml, resolves feature rules, copies to worktree `.claude/rules/`
- **wt-tools Ralph loop** (`lib/loop/state.sh` or wt_orch layer): reads context utilization at loop start/end via Claude API usage headers or wt-usage
- **Orchestration state schema**: two new optional fields per change: `context_tokens_start`, `context_tokens_end`
- **wt-web** (`src/app/`): change list UI shows context metrics alongside token count
