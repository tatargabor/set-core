# Spec: REQ-ID Enforcement

## AC-1: Planning rules include REQ-ID naming requirement
GIVEN the web module's planning_rules.txt
WHEN deployed to a consumer project
THEN it contains a rule requiring REQ-XXX-NNN prefix in E2E test names

## AC-2: Testing rules deployed to consumer projects
GIVEN set-testing.md or equivalent rule file
WHEN deployed via set-project init
THEN agents see explicit REQ-ID naming instructions during implementation

## AC-3: Rule includes example format
GIVEN the REQ-ID rule
WHEN an agent reads it
THEN it shows the exact format: `test('REQ-HOME-001: Hero heading visible', ...)`
