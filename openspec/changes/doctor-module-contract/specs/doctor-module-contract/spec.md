## IN SCOPE
- The `doctor/1` record contract a module doctor prints
- Declaring a module doctor in the set-core config directory, and discovering declarations
- Running each declared module doctor once, merging its records, attributing them to a module and a registered project
- Reporting a declared module whose command is not installed on this machine
- Adapters for the two module doctors that predate the contract
- A guard against a module doctor that itself runs `set-doctor`

## OUT OF SCOPE
- Repairing anything — every doctor stays read-only and prints the fix
- Changing other repositories' doctors from here (they adopt the contract on their side)
- Token-usage measurement from session transcripts
- A remote or multi-machine report — each machine runs its own doctor

## ADDED Requirements

### Requirement: Module doctors speak one record contract

A module doctor's machine output under the `doctor/1` contract SHALL be one JSON object:
`{"schema": "doctor/1", "module": <name>, "checks": [...]}`. Each check SHALL carry `section`,
`name`, `status` (`ok`, `warn`, `fail` or `skip`) and `detail`. A `warn` or `fail` SHALL carry
`fix`. A record about one project SHALL carry that project's path as `path`. `set-doctor` SHALL
reject a status outside the four, and SHALL reject an unknown `schema`, as a `fail` of that
module's run, never by dropping the records silently.

#### Scenario: A conforming module report is merged
- **WHEN** a declared module prints a `doctor/1` object with one `warn` record carrying a `fix`
- **THEN** `set-doctor`'s report contains that record with `module` set to the module's name

#### Scenario: An unknown contract is a failure, not an absence
- **WHEN** a declared module prints `{"schema": "doctor/9", ...}`
- **THEN** `set-doctor` reports a `fail` for that module naming the unexpected schema, and does not report the module as clean

### Requirement: Module doctors are discovered from declarations

`set-doctor` SHALL read every `*.json` file in the `doctors.d` directory of the set-core config
directory. That directory SHALL be resolved the same way as the project registry's
(`SET_CONFIG_DIR`, else `XDG_CONFIG_HOME/set-core`, else `~/.config/set-core`). A declaration
SHALL name `module`, `command` (an argument list), `contract`, and `install` (a one-line hint).
An unreadable or incomplete declaration SHALL be a `fail` naming the file. Two declarations with
the same `module` SHALL be a `fail` naming both files.

#### Scenario: A new module is picked up without a code change
- **WHEN** a declaration file for module `example` is added to `doctors.d`, and its command prints a valid `doctor/1` report
- **THEN** the next `set-doctor` run includes the `example` module's records

#### Scenario: A broken declaration is reported
- **WHEN** a file in `doctors.d` is not valid JSON
- **THEN** `set-doctor` reports a `fail` naming that file, and still runs every other declared module

### Requirement: Each declared module runs once and its records reach the right project

`set-doctor` SHALL run each declared module's command once per invocation, with a timeout. It
SHALL attach a record carrying `path` to the registered project whose path resolves to the same
real path. It SHALL report a record whose path matches no registered project under the module's
own section. A command that exits without a parseable report, or times out, SHALL be a `fail` for
that module with the tail of its error output.

#### Scenario: A per-project record lands on its project
- **WHEN** a module reports a `fail` record with the path of a registered project
- **THEN** that project's block in the text output shows the record, and the JSON record carries both `module` and `project`

#### Scenario: A module that hangs
- **WHEN** a declared module's command does not finish within its timeout
- **THEN** `set-doctor` reports a `fail` for that module saying it timed out, and the rest of the report is complete

### Requirement: A declared module that is not installed is reported

When a declaration's command is not found on `PATH`, `set-doctor` SHALL report a `warn` for that
module. The detail SHALL say it is declared but not installed on this machine, and the `fix`
SHALL be the declaration's `install` hint. It SHALL NOT be reported as `ok` and SHALL NOT be
omitted.

#### Scenario: A second developer's machine without the module
- **WHEN** a declaration names a command that is not on `PATH`
- **THEN** the report has a `warn` for that module with its install hint as the fix

### Requirement: The two pre-contract module doctors keep working through adapters

Until they print `doctor/1`, `sac doctor --json` (`sac.doctor/1`) and `set-kb doctor --json`
SHALL be read through built-in adapters. These adapters SHALL produce the same project records
that `set-doctor` printed before this change. A declaration for one of these modules SHALL
replace its built-in invocation, not add a second run. Once that module's declaration names
`doctor/1`, the adapter SHALL no longer be used.

A declaration may also name the family doctor's own contract, `aiplus-doctor/1`, which keys its
per-repository records by repository name. That adapter SHALL attach every record to the
registered project with the same name. A record for a repository name the registry does not
know SHALL be reported under the module's own section. The family doctor's machine records
SHALL be reported under the module's own section, except its record about `set-doctor` itself,
which describes the run that is reading it. Nothing SHALL be dropped.

#### Scenario: No declaration, no regression
- **WHEN** `doctors.d` is empty
- **THEN** every project still gets its `bus` and `kb` records, as before this change

#### Scenario: A declaration replaces the built-in run
- **WHEN** a declaration for module `sac` exists
- **THEN** `sac doctor` is run once, not twice

#### Scenario: The family doctor's repository findings reach their projects
- **WHEN** a declaration names contract `aiplus-doctor/1`, and its report has a `fail` for a repository registered under the same name
- **THEN** that project's block shows the `fail` with `module` set to the declared module, and a repository the registry does not know appears under the module's section

### Requirement: A module doctor that runs set-doctor does not recurse

`set-doctor` SHALL set `SET_DOCTOR_CHILD=1` in the environment of every module doctor it runs.
When `set-doctor` itself starts with `SET_DOCTOR_CHILD=1`, it SHALL NOT run module doctors, and
SHALL report one `skip` saying the module doctors are run by the parent invocation.

#### Scenario: The family doctor is declared and calls set-doctor
- **WHEN** a declared module's command runs `set-doctor --json`
- **THEN** the inner `set-doctor` runs no module doctors, and the outer run finishes once
