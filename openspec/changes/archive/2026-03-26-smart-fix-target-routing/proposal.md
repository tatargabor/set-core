## Why

The investigation agent uses keyword matching to decide whether a bug is a framework issue (fix in set-core) or a consumer issue (fix locally). This is unreliable — "merger" appearing in a proposal doesn't mean the merger code is broken; it might be a project-specific merge conflict.

In minishop-run5, middleware.ts conflicts are project-specific (two agents wrote to the same file), but the keyword "merge" would route this to set-core as a framework fix — wrong.

There are actually three fix targets:
1. **framework** — bug affects all projects (merger, gate, dispatcher code) → fix in set-core, deploy to consumer
2. **consumer** — bug is specific to this project (merge conflict, missing config) → fix locally
3. **both** — root cause in framework/template but symptom needs local fix too (e.g., template deployed broken seed URLs, now need to fix template AND existing seed)

## What Changes

- Replace keyword-based `fix_target` detection with explicit LLM classification in the investigation prompt
- Add `fix_target: "both"` support — framework fix + local fix
- Investigation prompt asks: "Would this bug affect OTHER projects using set-core?"
- Fixer handles `both` target: fix set-core first, deploy, then fix consumer

## Capabilities

### Modified Capabilities
- `fix-target-classification` — LLM-driven fix target routing (framework vs consumer vs both)

## Impact

- `lib/set_orch/issues/investigator.py` — investigation prompt + parse logic
- `lib/set_orch/issues/fixer.py` — handle `both` target
