## 1. Create project guide template

- [x] 1.1 Create `templates/core/rules/project-guide.md` with all sections from design D3 [REQ: project-guide-rule-template]
- [x] 1.2 Verify the file deploys correctly as `set-project-guide.md` by running `set-project init` on a test project [REQ: project-guide-rule-template]

## 2. Validate deployment

- [x] 2.1 Run `set-project init` on an existing consumer project and verify `set-project-guide.md` appears in `.claude/rules/` [REQ: deploy-rules-to-project]
- [x] 2.2 Verify existing custom (non-set-*) rules are untouched after re-init [REQ: deploy-rules-to-project]

## Acceptance Criteria (from spec scenarios)

- [x] AC-1: WHEN `set-project init` runs THEN `set-project-guide.md` exists in `.claude/rules/` [REQ: project-guide-rule-template, scenario: guide-deployed-on-init]
- [x] AC-2: WHEN agent reads the guide THEN it understands set-* files are managed and non-prefixed are project-owned [REQ: file-ownership-documentation, scenario: agent-reads-guide-before-modifying-rules]
- [x] AC-3: WHEN agent needs domain-specific rules THEN guide instructs to create without set- prefix [REQ: custom-rule-creation-guidance, scenario: agent-adds-domain-specific-rule]
- [x] AC-4: WHEN agent uses /opsx:new THEN guide explains OpenSpec is available and to respect existing rules [REQ: openspec-change-guidance, scenario: agent-creates-change-respecting-conventions]
- [x] AC-5: WHEN project needs domain patterns THEN guide explains custom rules + knowledge extension [REQ: extension-guidance-for-domain-specific-patterns, scenario: project-needs-mobile-specific-patterns]
- [x] AC-6: WHEN re-init runs THEN only set-* files overwritten, custom rules preserved [REQ: deploy-rules-to-project, scenario: re-init-updates-rules-without-touching-project-rules]
