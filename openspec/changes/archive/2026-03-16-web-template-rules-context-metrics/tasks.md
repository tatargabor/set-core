# Tasks: web-template-rules-context-metrics

## Part A — set-project-web template corrections
_Repo: `set-project-web`_

### A1. Fix postcss.config.mjs — Tailwind v4 syntax
- [x] Change `tailwindcss: {}` to `"@tailwindcss/postcss": {}` in `wt_project_web/templates/nextjs/postcss.config.mjs`
- [x] Verify `autoprefixer: {}` remains
- [x] `[REQ: nextjs-template-corrections / Correct Tailwind v4 PostCSS config]`

### A2. Fix jest.config.ts — correct key name
- [x] Replace `setupFilesAfterSetup` with `setupFilesAfterEnv` in `wt_project_web/templates/nextjs/rules/testing-conventions.md` (no template jest.config.ts exists — guidance in rule)
- [x] `[REQ: nextjs-template-corrections / Correct Jest config key]`

### A3. Update next.config.js — add images.unoptimized default
- [x] Add `images: { unoptimized: true }` to the config object in `wt_project_web/templates/nextjs/next.config.js`
- [x] `[REQ: nextjs-template-corrections / next.config.js common defaults]`

### A4. Extend data-model.md — worktree DB setup + Prisma version pin
- [x] Added section "## Worktree Setup" to `wt_project_web/templates/nextjs/rules/data-model.md`:
  - `prisma migrate deploy` (not `migrate dev`) in worktrees
  - `prisma db seed` required (dev.db is gitignored)
  - Pin `prisma@6` — Prisma 7 broke datasource `url` field
- [x] `[REQ: nextjs-template-corrections / data-model.md worktree DB guidance]`

### A5. Extend testing-conventions.md — node env + pnpm fix
- [x] Added section "## Prisma Tests — Jest Environment" to `wt_project_web/templates/nextjs/rules/testing-conventions.md`:
  - `@jest-environment node` docblock required for Prisma test files
  - Default jsdom environment breaks Prisma
- [x] Added section "## pnpm Non-Interactive Builds" and "## jest.config.ts — Correct Keys"
- [x] `[REQ: nextjs-template-corrections / testing-conventions.md pnpm and node env guidance]`

### A6. Create new worktree-setup.md rule
- [x] Created `wt_project_web/templates/nextjs/rules/worktree-setup.md` with YAML frontmatter (paths: prisma/**, jest.config*, playwright.config*)
- [x] Content: DB init, port conflicts, pnpm non-interactive
- [x] `[REQ: nextjs-template-corrections / New worktree-setup.md rule]`

### A7. Register worktree-setup.md in manifest.yaml
- [x] Added `rules/worktree-setup.md` to core list in `wt_project_web/templates/nextjs/manifest.yaml`
- [x] `[REQ: nextjs-template-corrections / Rule is deployed by set-project init]`

### A8. Add worktree-setup.md entry to project-knowledge.yaml template
- [x] Added `worktree_setup` feature entry in `wt_project_web/templates/nextjs/project-knowledge.yaml` with `rules_file: .claude/rules/worktree-setup.md` and touches: prisma/**, jest.config*, playwright.config*
- [x] `[REQ: feature-rules-injection / Feature rules resolved at dispatch]`

---

## Part B — Feature rules injection in dispatcher
_Repo: `set-core`_

### B1. Add `_inject_feature_rules()` function to dispatcher.py
- [x] Added `_inject_feature_rules(project_path, wt_path, scope, spec_files)` in `lib/set_orch/dispatcher.py` after `_build_pk_context()`
- [x] Uses `spec_files` glob matching (preferred) + scope keyword fallback; skips if file already exists; logs INFO
- [x] `[REQ: feature-rules-injection / Feature rules resolved at dispatch]`
- [x] `[REQ: feature-rules-injection / Graceful degradation]`

### B2. Call `_inject_feature_rules()` in `dispatch_change()` after bootstrap
- [x] Called after `bootstrap_worktree()` in `dispatch_change()` with `spec_files=change.spec_files`
- [x] `[REQ: feature-rules-injection / Injection happens after bootstrap]`

### B3. Add injection logging
- [x] `logger.info("injected feature rule: %s → .claude/rules/%s", fname, ...)` in `_inject_feature_rules()`
- [x] `[REQ: feature-rules-injection / Injection is logged]`

---

## Part C — Context window metrics in verifier
_Repo: `set-core`_

### C1. Add CONTEXT_WINDOW_SIZE constant to verifier.py
- [x] Added `CONTEXT_WINDOW_SIZE = 200_000` constant to `lib/set_orch/verifier.py`
- [x] `[REQ: context-window-metrics / Context window size constant]`

### C2. Capture context_tokens_start after first iteration
- [x] Added `_capture_context_tokens_start()` in `verifier.py` — reads `iterations[0].cache_create_tokens`, writes once to state
- [x] Called from `poll_change()` after `_accumulate_tokens()`
- [x] `[REQ: context-window-metrics / Context tokens captured at first iteration completion]`

### C3. Capture context_tokens_end at loop completion
- [x] Added `_capture_context_tokens_end()` in `verifier.py` — reads `total_cache_create`, writes to state
- [x] Called at start of `handle_change_done()` via `_capture_context_tokens_end(state_file, change_name, _read_loop_state(wt_path))`
- [x] `[REQ: context-window-metrics / Context tokens captured at loop completion]`

### C4. Verify new fields don't break state serialization
- [x] Added `context_tokens_start: Optional[int] = None` and `context_tokens_end: Optional[int] = None` to `Change` dataclass in `lib/set_orch/state.py`
- [x] `to_dict()` / `load_state()` handle Optional fields gracefully (existing pattern)
- [x] API: `to_dict()` automatically includes new fields — no api.py changes needed

---

## Part D — wt-web context metrics display
_Repo: `set-core`_

### D1. Add context metrics to change list API response
- [x] No changes needed — `c.to_dict()` in `api.py` automatically serializes `context_tokens_start/end` from state

### D2. Display context metrics in change list UI
- [x] Added `context_tokens_start?: number` and `context_tokens_end?: number` to `ChangeInfo` interface in `web/src/lib/api.ts`
- [x] Added `ctx: NNK→NNK (NN%)` display in expanded details and table row in `web/src/components/ChangeTable.tsx`
- [x] `[REQ: context-window-metrics / wt-web change list shows context metrics]`

### D3. Highlight high context utilization (≥80%)
- [x] Applied `text-orange-400` when `context_tokens_end / 200_000 >= 0.8` in ChangeTable.tsx
- [x] `[REQ: context-window-metrics / High context utilization is visually highlighted]`

---

## Part E — Acceptance criteria

- [ ] Deploy updated set-project-web templates to a test project: `set-project init --project-type web` — `pnpm build` must succeed without manual config fixes
- [ ] Run minishop E2E — no "Tailwind CSS v4 PostCSS plugin" or "setupFilesAfterSetup" in agent Issues Fixed log
- [ ] Dispatch a db-schema-type change — confirm `data-model.md` appears in worktree `.claude/rules/` before agent starts
- [ ] After a change completes — confirm `context_tokens_start` and `context_tokens_end` present in orchestration-state.json
- [ ] Open wt-web — confirm `ctx:` display in change list for completed changes
