## IN SCOPE
- Auto-generate .env for Prisma projects in WebProjectType bootstrap
- Config-driven env_vars in orchestration config.yaml
- Never overwrite existing .env

## OUT OF SCOPE
- Modifying the Prisma schema or global-setup.ts
- Supporting non-SQLite database providers for auto-generation
- .env encryption or secrets management

### Requirement: WebProjectType generates .env for Prisma
When `bootstrap_worktree()` runs and `prisma/schema.prisma` exists with `env("DATABASE_URL")` but no `.env` file exists, the web profile SHALL generate `.env` with `DATABASE_URL="file:./dev.db"`.

#### Scenario: Prisma project without .env
- **GIVEN** worktree has `prisma/schema.prisma` with `url = env("DATABASE_URL")`
- **AND** no `.env` file exists in worktree
- **WHEN** bootstrap_worktree runs
- **THEN** `.env` SHALL be created with `DATABASE_URL="file:./dev.db"`

#### Scenario: .env already exists
- **GIVEN** worktree already has `.env`
- **WHEN** bootstrap_worktree runs
- **THEN** `.env` SHALL NOT be modified

### Requirement: Config-driven env_vars
The orchestration `config.yaml` SHALL support an `env_vars` section. These variables SHALL be written to `.env` in every worktree at bootstrap time.

#### Scenario: Config has env_vars
- **GIVEN** config.yaml contains `env_vars: { DATABASE_URL: "file:./dev.db" }`
- **WHEN** a worktree is bootstrapped
- **THEN** `.env` SHALL contain `DATABASE_URL="file:./dev.db"`

#### Scenario: Config env_vars override profile defaults
- **GIVEN** profile generates `DATABASE_URL="file:./dev.db"`
- **AND** config.yaml has `env_vars: { DATABASE_URL: "postgresql://..." }`
- **WHEN** bootstrap runs
- **THEN** `.env` SHALL contain the config value (postgresql), not the profile default
