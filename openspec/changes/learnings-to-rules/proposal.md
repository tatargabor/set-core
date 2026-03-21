# Proposal: learnings-to-rules

## Why

The orchestration system captures valuable patterns from gate failures across runs — recurring review findings, common build errors, repeated test failures — but this knowledge dies in log files and memory entries. It never flows back into the rule system that guides future agents. Meanwhile, the `/set:harvest` skill extracts rules from source project files, but nothing extracts rules from **orchestration experience**. The feedback loop from "what went wrong" to "prevent it next time" is completely open.

## What Changes

- **NEW**: `/set:learn` skill — a post-run skill that reads orchestration learnings (review findings, gate stats, memory patterns), clusters recurring issues into rule candidates, classifies them (core vs plugin template), and presents them to the user for approval before writing
- **NEW**: `learnings_analyzer.py` — Python module that reads review-findings.jsonl and memory, extracts actionable patterns, generates rule text, and classifies by scope (core/web/base/project-specific)
- **NEW**: API endpoint `GET /api/{project}/rule-candidates` — returns generated rule candidates for the web UI to display
- **ENHANCE**: LearningsPanel on web dashboard — add "Rule Suggestions" section showing candidates with Accept/Dismiss actions
- **ENHANCE**: `POST /api/{project}/rule-candidates/{id}/accept` — accepts a candidate, writes the rule file, and triggers deploy

## Capabilities

### New Capabilities
- `learnings-analyzer`: Pattern extraction from orchestration findings, rule candidate generation, scope classification
- `learn-skill`: Interactive skill for post-run learning extraction and rule creation

### Modified Capabilities
- `learnings-web-panel`: Add rule suggestions section with Accept/Dismiss UI
- `learnings-api`: Add rule candidates endpoints (GET list, POST accept/dismiss)

## Impact

- **New files**: `.claude/skills/set/learn/SKILL.md`, `lib/set_orch/learnings_analyzer.py`, web component updates
- **Modified files**: `lib/set_orch/api.py` (new endpoints), `web/src/components/LearningsPanel.tsx` (rule suggestions section)
- **Risk**: Rule generation quality depends on pattern clustering — conservative thresholds prevent bad rules. All rules require user approval before being written.
- **Dependencies**: No new packages
