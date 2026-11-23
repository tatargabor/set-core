## IN SCOPE
- `set-project init` installing the auto-clear package templates, its two hooks and a started watcher unit by default
- Refusing to overwrite a locally modified package file, and recognising a project's own reload or arm mechanism
- Leaving an existing watcher unit unchanged, and reporting overriding flags in it
- Dry-run planning, a per-project opt-out, and skipping archived and data projects

## OUT OF SCOPE
- The gate, watcher and hook behaviour themselves (owned by the handoff package)
- Committing or pushing the resulting files in a consumer repository
- A fleet-side rotation that would type `/clear` itself (a later change must call this executor instead)
- Rewriting a project's keep-going hook arguments in its settings

## ADDED Requirements

### Requirement: Init installs auto-clear by default
`set-project init` SHALL install auto-clear in every registered project that is not archived, not
`deploy: false` and not opted out with `auto_clear: false`. The install SHALL consist of the handoff
package's own templates, the reload hook (`SessionStart`, matcher `clear|compact`) and the arm hook
(`PostToolUse`, matcher `Write|Edit|MultiEdit|Bash`) merged additively into `.claude/settings.json`,
and a systemd user unit `<project>-auto-clear.service` that runs the package's watcher with no
threshold or background flags, enabled and started.

#### Scenario: A project with nothing installed
- **WHEN** `set-project init` runs on a registered, non-archived project with no auto-clear files, hooks or unit
- **THEN** the package templates exist under `.claude/hooks/`, both hooks are present in `.claude/settings.json`, and `<project>-auto-clear.service` is active
- **AND** the unit's command line contains `--dir <project path>` and none of `--threshold`, `--compact-threshold`, `--background-work-blocks`

#### Scenario: An archived, data or opted-out project
- **WHEN** init runs on a project that is archived, or has `deploy: false`, or has `auto_clear: false`
- **THEN** no template, hook or unit is written and one line names the project and the reason

#### Scenario: Re-running init is idempotent
- **WHEN** init runs a second time on a project where the first run completed
- **THEN** no file changes, no hook is duplicated, the unit is not restarted, and the step reports it is up to date

### Requirement: A locally modified package file is kept
Init SHALL overwrite a package-owned template only when its current content equals some version the
package has shipped (compared by content hash), or when the file is absent. A file whose content
matches no shipped version SHALL be left unchanged and named in the output with the reason.

#### Scenario: A pristine older version is upgraded
- **WHEN** `.claude/hooks/clear-gate.mjs` holds a version the package shipped earlier
- **THEN** init replaces it with the current version

#### Scenario: A hand-edited file survives
- **WHEN** `.claude/hooks/watch-auto-clear.sh` differs from every shipped version
- **THEN** init leaves it byte-identical and prints that it was kept as locally modified

### Requirement: A project's own reload or arm mechanism is not duplicated
The hook merge SHALL NOT add the package's reload hook when the project's `SessionStart` entries
already run a command whose name contains `reinject` for the `clear` source, and SHALL NOT add the
arm hook when a `PostToolUse` entry already runs a command containing `handoff-arm`. The skip SHALL
be reported.

#### Scenario: A project with its own reload script
- **WHEN** a project's `SessionStart` `clear|compact` entry runs its own `scripts/hooks/handoff-reinject.mjs`
- **THEN** init does not add the package's reload hook and prints that the project's own reload was found

### Requirement: An existing watcher unit is never rewritten
When `<project>-auto-clear.service` (or any user unit whose command runs that project's
`watch-auto-clear.sh`) already exists, init SHALL leave it unchanged and SHALL name every flag in it
that overrides a package default.

#### Scenario: A hand-written unit with an old threshold
- **WHEN** an existing unit passes `--compact-threshold 500000`
- **THEN** the unit file is byte-identical after init, and the output names the flag and the command that would remove it

### Requirement: Dry-run plans and writes nothing
`set-project init --dry-run` SHALL print, per project, which templates it would write or keep, which
hooks it would add or skip, and whether it would create and start a unit — and SHALL write no file
and start no unit.

#### Scenario: Dry-run on a project with nothing installed
- **WHEN** `set-project init --dry-run` runs on a project with no auto-clear install
- **THEN** the plan lists the templates, both hooks and the unit, and a content hash of the project tree and of `~/.config/systemd/user/` is unchanged afterwards

### Requirement: A missing package checkout is announced, not fatal
When the handoff package checkout cannot be resolved from the project registry, init SHALL skip the
auto-clear step with one line saying so and SHALL complete the rest of the deploy.

#### Scenario: No package checkout
- **WHEN** the registry has no entry for the handoff package, or its path does not exist
- **THEN** init exits 0, prints that auto-clear was skipped and why, and writes nothing for it
