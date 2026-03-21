# Tasks: learnings-to-rules

## 1. Learnings Analyzer Module

- [ ] 1.1 Create `lib/set_orch/learnings_analyzer.py` with `analyze_findings(project_path: str) -> list[RuleCandidate]` function: reads `wt/orchestration/review-findings.jsonl`, extracts recurring patterns (same normalization as `generate_review_findings_summary()`: strip severity tag, first 50 chars, count across changes), filters by threshold (≥3 occurrences, ≥2 changes) [REQ: extract-recurring-patterns-from-findings]
- [ ] 1.2 Add memory cross-reference: recall memories tagged `source:orchestrator,type:review-patterns` via `orch_recall()`, match against current findings patterns, boost confidence for patterns that appear in both current findings and prior memory [REQ: extract-recurring-patterns-from-findings]
- [ ] 1.3 Implement `RuleCandidate` dataclass with fields: id (kebab-case slug from normalized pattern), title, description, severity, occurrence_count, affected_changes (list of change names), file_patterns (extracted from issue file paths), suggested_rule_text, classification (core/web/base/project), confidence (suggested/recommended), status (pending/accepted/dismissed) [REQ: generate-rule-candidates-from-patterns]
- [ ] 1.4 Implement rule text generation from pattern data: use template with optional globs frontmatter (from file_patterns), title, description paragraph, "Guidelines" section (from issue summaries), and "Common Mistakes" section (from issue fix recommendations). Generalize: strip absolute paths, replace specific entity names with generic placeholders [REQ: generate-rule-candidates-from-patterns]
- [ ] 1.5 Implement scope classification: keyword heuristics — scan pattern summary and file paths for framework keywords (react, next, api, component, middleware → "web"; generic coding terms → "core"; specific paths/entities → "project"). If a profile plugin is loaded, call `profile.classify_learning_pattern(pattern)` if the method exists (graceful fallback to heuristic if not) [REQ: classify-rule-candidates-by-scope]
- [ ] 1.6 Implement confidence scoring: ≥3 occurrences in ≥2 changes → "suggested"; ≥5 occurrences in ≥3 changes OR pattern found in memory from prior runs → "recommended" [REQ: confidence-thresholds]
- [ ] 1.7 Add `save_candidates(project_path: str, candidates: list[RuleCandidate])` — writes to `wt/orchestration/rule-candidates.json` as JSON array. Add `load_candidates(project_path: str) -> list[RuleCandidate]` — reads and returns existing candidates [REQ: generate-rule-candidates-from-patterns]
- [ ] 1.8 Add `accept_candidate(project_path: str, candidate_id: str) -> str` — finds candidate by id, generates the rule file, writes it to the correct location based on classification (core: `set-core/.claude/rules/{id}.md`, project: `{project_path}/.claude/rules/{id}.md`), updates status to "accepted" in candidates JSON, returns written path [REQ: generate-rule-candidates-from-patterns]
- [ ] 1.9 Add `dismiss_candidate(project_path: str, candidate_id: str)` — updates status to "dismissed" in candidates JSON, saves to memory with tag `dismissed-rule,slug:{id}` to prevent re-suggestion [REQ: generate-rule-candidates-from-patterns]
- [ ] 1.10 Add dismissed-rule filtering: before returning candidates from `analyze_findings()`, check memory for `dismissed-rule` tagged entries and filter out matching slugs [REQ: generate-rule-candidates-from-patterns]

## 2. API Endpoints

- [ ] 2.1 Add `GET /api/{project}/rule-candidates` endpoint in api.py: call `load_candidates()` from learnings_analyzer, return `{ candidates: [...] }`. If no candidates file exists, call `analyze_findings()` first to generate them [REQ: rule-candidates-api-endpoint]
- [ ] 2.2 Add `POST /api/{project}/rule-candidates/{id}/action` endpoint in api.py: read body `{ action: "accept" | "dismiss" }`, call `accept_candidate()` or `dismiss_candidate()` from learnings_analyzer, return result with status and path (for accept) [REQ: accept-dismiss-rule-candidate-endpoint]

## 3. Learn Skill

- [ ] 3.1 Create `.claude/skills/set/learn/SKILL.md`: skill definition with input (optional project name), steps (detect project → run analyzer → present candidates → get approval → write rules → report), and guardrails (never auto-deploy, always generalize, respect dismissals) [REQ: skill-invocation-and-project-detection]
- [ ] 3.2 In skill steps: project detection — if arg provided use it, else detect from CWD via `openspec list --json` or project registry lookup. Verify review-findings.jsonl exists [REQ: skill-invocation-and-project-detection]
- [ ] 3.3 In skill steps: run analysis — call `python3 -c "from lib.set_orch.learnings_analyzer import analyze_findings; ..."` or use the API endpoint to get candidates [REQ: present-rule-candidates-for-approval]
- [ ] 3.4 In skill steps: presentation and approval — for each candidate show title, classification badge, confidence, occurrence count, affected changes, and rule text preview. Use AskUserQuestion for approve/edit/dismiss per candidate [REQ: present-rule-candidates-for-approval]
- [ ] 3.5 In skill steps: write approved rules — call accept_candidate() for approved ones, report written paths. For core rules suggest `set-project init` on consumers. For project-local rules note they're immediately available [REQ: post-accept-deployment]
- [ ] 3.6 In skill steps: dismissed rules handling — call dismiss_candidate() for dismissed ones, confirm they won't be re-suggested [REQ: avoid-re-suggesting-dismissed-rules]

## 4. Web UI — Rule Suggestions Section

- [ ] 4.1 Add `getRuleCandidates()` and `postRuleCandidateAction()` fetch functions and `RuleCandidate` type in `web/src/lib/api.ts` [REQ: rule-suggestions-section-in-learningspanel]
- [ ] 4.2 Add "Rule Suggestions" section to LearningsPanel.tsx: fetch candidates via `getRuleCandidates()`, show each as expandable card with title, classification badge (core/web/project color-coded), confidence level, occurrence count [REQ: rule-suggestions-section-in-learningspanel]
- [ ] 4.3 Expanded candidate card shows: full rule text in pre/code block, affected changes list, Accept and Dismiss buttons [REQ: rule-suggestions-section-in-learningspanel]
- [ ] 4.4 Accept button: calls `postRuleCandidateAction(id, "accept")`, shows success notification with written path, removes from list [REQ: rule-suggestions-section-in-learningspanel]
- [ ] 4.5 Dismiss button: calls `postRuleCandidateAction(id, "dismiss")`, removes from list [REQ: rule-suggestions-section-in-learningspanel]
- [ ] 4.6 Empty state: "No rule suggestions — run `/set:learn` after an orchestration run to analyze patterns" [REQ: rule-suggestions-section-in-learningspanel]

## Acceptance Criteria (from spec scenarios)

- [ ] AC-1: WHEN review-findings.jsonl has a pattern in 3+ occurrences across 2+ changes THEN a rule candidate is generated [REQ: extract-recurring-patterns-from-findings, scenario: patterns-across-changes-in-one-run]
- [ ] AC-2: WHEN a pattern also exists in memory from prior runs THEN confidence is "recommended" [REQ: extract-recurring-patterns-from-findings, scenario: patterns-across-runs-via-memory]
- [ ] AC-3: WHEN candidate is generated THEN it includes id, title, classification, confidence, occurrence_count, affected_changes, and suggested_rule_text [REQ: generate-rule-candidates-from-patterns, scenario: rule-candidate-structure]
- [ ] AC-4: WHEN pattern references React/Next.js/API routes THEN classification is "web" [REQ: classify-rule-candidates-by-scope, scenario: plugin-classification]
- [ ] AC-5: WHEN pattern is about generic coding (imports, null checks) THEN classification is "core" [REQ: classify-rule-candidates-by-scope, scenario: core-classification]
- [ ] AC-6: WHEN user approves a candidate via skill THEN rule file is written to correct location [REQ: present-rule-candidates-for-approval, scenario: user-approves-candidate]
- [ ] AC-7: WHEN user dismisses a candidate THEN it is not shown in future runs [REQ: avoid-re-suggesting-dismissed-rules, scenario: previously-dismissed-pattern]
- [ ] AC-8: WHEN user clicks Accept in web UI THEN API writes rule file and returns path [REQ: accept-dismiss-rule-candidate-endpoint, scenario: accept-action]
- [ ] AC-9: WHEN no recurring patterns exist THEN no candidates are generated and UI shows empty state [REQ: extract-recurring-patterns-from-findings, scenario: no-recurring-patterns]
