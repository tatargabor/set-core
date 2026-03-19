## MODIFIED Requirements

### Requirement: Ralph loop Claude invocation
The Ralph loop SHALL use the configured permission mode for Claude Code invocations, with a flag to override.

#### Scenario: wt-loop uses config permission mode
- **WHEN** `wt-loop` starts without `--permission-mode`
- **THEN** it SHALL read `claude.permission_mode` from `~/.config/set-core/config.json`
- **AND** invoke Claude with the corresponding flags:
  - `auto-accept` → `--dangerously-skip-permissions`
  - `allowedTools` → `--allowedTools "Edit,Write,Bash,Read,Glob,Grep,Task"`
  - `plan` → no permission flags

#### Scenario: wt-loop --permission-mode flag
- **WHEN** `wt-loop --permission-mode <mode>` is run
- **THEN** it SHALL use the specified mode instead of config
- **AND** valid values are: `auto-accept`, `plan`, `allowedTools`
- **AND** the config.json SHALL NOT be modified

#### Scenario: wt-loop refuses plan mode
- **WHEN** wt-loop would start with permission mode `plan` (either from config or flag)
- **THEN** it SHALL print: "Error: Plan mode is incompatible with Ralph loop (requires interactive approval)"
- **AND** it SHALL exit with code 1
- **AND** if `--force` is also specified, it SHALL start with a warning instead of refusing

#### Scenario: wt-loop help shows permission flag
- **WHEN** `wt-loop --help` is run
- **THEN** the `--permission-mode` flag SHALL be listed
- **AND** its description SHALL mention the three valid values and the config default
