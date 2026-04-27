# Spec: web-diagnostics

Concrete diagnostic rules for web projects (Next.js, Prisma, npm) in set-project-web.

## Requirements

### REQ-WEBDIAG-001: PrismaClientRule
- Handles `failure_type == "build_broken"` or `"smoke_failed"`
- Detects pattern: `Module '"@prisma/client"' has no exported member` in build_output
- Action: `fix_config` with `config_patches: {"post_merge_command": "npx prisma generate && {existing}"}`
- Also runs `npx prisma generate` immediately in the project dir
- Fixes Bug #29 (recurring across Run #5, #6)

### REQ-WEBDIAG-002: MissingDepsRule
- Handles `failure_type == "build_broken"` or `"smoke_failed"`
- Detects pattern: `Module not found: Can't resolve '{package}'` in build_output
- Checks if package is in package.json but not in node_modules
- Action: runs `pnpm install` (or detected package manager), returns `retry`
- Report: "Missing dependency {package} — ran install"

### REQ-WEBDIAG-003: MergeGapRule
- Handles `failure_type == "build_broken"`
- Detects pattern: `Property '{x}' does not exist on type '{TypeName}'` where the type is in a shared file (i18n, config, types)
- Compares the failing file's imports against the type definition
- Action: `retry` with `retry_context` explaining the gap: "Type '{TypeName}' is missing property '{x}' — add it to the type definition and the corresponding language dictionaries"
- Fixes the i18n Dictionary gap pattern from Run #6

### REQ-WEBDIAG-004: WebProfile.diagnostic_rules()
- `set-project-web` profile class implements `diagnostic_rules()`
- Returns: `[PrismaClientRule(), MissingDepsRule(), MergeGapRule()]`
- Rules loaded by the diagnostic runner via profile interface

## Acceptance Criteria

- [ ] AC-1: WHEN build fails with "has no exported member" from @prisma/client THEN PrismaClientRule adds post_merge_command and retries
- [ ] AC-2: WHEN build fails with "Module not found: Can't resolve" THEN MissingDepsRule runs package install
- [ ] AC-3: WHEN build fails with TypeScript "Property does not exist on type" in a shared type file THEN MergeGapRule provides fix context
- [ ] AC-4: WHEN WebProfile.diagnostic_rules() is called THEN all three rules are returned in order
