## 1. WebProjectType .env generation

- [x] 1.1 In `WebProjectType.bootstrap_worktree()`: check if `prisma/schema.prisma` exists and contains `env("DATABASE_URL")` [REQ: webprojecttype-generates-env-for-prisma]
- [x] 1.2 If prisma detected and no `.env` exists, generate `.env` with `DATABASE_URL="file:./dev.db"` [REQ: webprojecttype-generates-env-for-prisma, scenario: prisma-project-without-env]
- [x] 1.3 If `.env` already exists, skip (never overwrite) [REQ: webprojecttype-generates-env-for-prisma, scenario: env-already-exists]

## 2. Config-driven env_vars

- [x] 2.1 In `dispatcher.py dispatch_change()`: after profile bootstrap, read `env_vars` from directives [REQ: config-driven-env-vars]
- [x] 2.2 Write env_vars to `.env` in worktree (append if file exists from profile, create if not) [REQ: config-driven-env-vars, scenario: config-has-env-vars]
- [x] 2.3 Config values override profile-generated values for same key [REQ: config-driven-env-vars, scenario: config-env-vars-override-profile-defaults]

## 3. Tests

- [x] 3.1 Unit test: Prisma project without .env → .env generated with DATABASE_URL
- [x] 3.2 Unit test: .env already exists → not modified
- [x] 3.3 Unit test: config.yaml env_vars written to .env
- [x] 3.4 Unit test: config overrides profile default for same key
- [x] 3.5 Integration test: run e2e on craftbrew worktree after bootstrap — passes without manual .env creation
- [x] 3.6 Run existing tests: must all pass (1 pre-existing failure unrelated)
