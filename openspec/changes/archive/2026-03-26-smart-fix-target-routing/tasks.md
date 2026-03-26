## 1. Investigation Prompt

- [x] 1.1 Add "Fix Target Classification" section to INVESTIGATION_PROMPT in `lib/set_orch/issues/investigator.py` — instruct agent to add "## Fix Target" with **Target:** and **Reasoning:** [REQ: fix-target-classification/REQ-1]

## 2. Proposal Parsing

- [x] 2.1 Add explicit fix_target extraction in `_parse_proposal()` — regex for `**Target:** (framework|consumer|both)` [REQ: fix-target-classification/REQ-2]
- [x] 2.2 Keep keyword heuristic as fallback when no explicit target found [REQ: fix-target-classification/REQ-3]

## 3. Fixer "both" Support

- [x] 3.1 Update `_resolve_fix_target()` in fixer.py to handle `fix_target="both"` — routes to set-core like "framework" [REQ: fix-target-classification/REQ-4]
- [x] 3.2 "both" uses FRAMEWORK_FIX_PROMPT which includes set-project init deploy — covers both framework + consumer fix [REQ: fix-target-classification/REQ-5]
