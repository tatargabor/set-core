# agent-provider-migration Specification

## Purpose
Moving an older single-provider configuration to the central one, as an explicit command with a bounded deprecation window.

## IN SCOPE

- A command that manages the provider configuration, including one explicit migration from
  the older single-provider configuration file
- What the migration does, what it refuses to do, and what it reports
- A single deprecation window during which the older file is still read, with a warning
- The removal of the configuration tier that read a provider credential from a project's
  own working tree

## OUT OF SCOPE

- The shape of the new configuration (`agent-provider-config`)
- Resolution and precedence (`agent-provider-resolution`)
- Starting agents (`agent-provider-start`)
- Migrating Anthropic OAuth accounts, which are a separate store and are untouched

## Requirements

### Requirement: Migration is an explicit command, never a side effect of reading

The framework SHALL provide a command that converts the older single-provider configuration
file into the provider configuration. That conversion SHALL happen only when the command is
invoked.

Reading the configuration, resolving a provider, or starting an agent MUST NOT create,
rewrite or migrate any configuration file.

#### Scenario: Resolution leaves the configuration untouched

- **WHEN** a provider is resolved while only the older configuration file exists
- **THEN** no configuration file is created or modified

#### Scenario: The command performs the conversion

- **WHEN** the migration command is invoked and the older configuration file exists
- **THEN** a provider configuration is written containing the older file's provider, its endpoint, its credential and its model

#### Scenario: An existing provider configuration is not overwritten silently

- **WHEN** the migration command is invoked and a provider configuration already exists
- **THEN** the command reports what it would change and does not overwrite it without being told to

### Requirement: The older configuration file is read for one release, with a warning

Until the deprecation window closes, the framework SHALL read the older single-provider
configuration file when no provider configuration exists, and SHALL emit a warning naming
that file, the file that replaces it, and the migration command.

After the window closes the older file SHALL NOT be read, and a setup that still relies on
it SHALL fail with a message naming the migration command rather than behaving as though no
provider were configured.

#### Scenario: The old file still works and says it is going away

- **WHEN** only the older configuration file exists and a provider is resolved during the deprecation window
- **THEN** resolution succeeds and a warning names the old file, the new file and the migration command

#### Scenario: A migrated setup stops warning

- **WHEN** a provider configuration exists
- **THEN** the older file is not read and no deprecation warning is emitted

#### Scenario: After the window, the failure names the command

- **WHEN** the deprecation window has closed and only the older configuration file exists
- **THEN** resolution fails with a message naming the migration command, and does not report that no provider is configured

### Requirement: Reading a provider credential from a project's working tree is removed

The framework SHALL NOT read a provider credential from a file inside a project's own
working tree. A setup that previously placed a credential there SHALL fail with a message
that names the removed location, the central configuration that replaces it, and the
migration command.

That failure MUST NOT be reported as a missing credential alone, because the difference
between "you have not configured this" and "the place you configured it is no longer read"
is what makes the message actionable.

#### Scenario: A credential in the project tree no longer takes effect

- **WHEN** a project's working tree contains a file declaring a provider credential and no central configuration declares one
- **THEN** resolution fails, and the failure names the removed location and the central file that replaces it

#### Scenario: The removal is not disguised as an absence

- **WHEN** the failure above is reported
- **THEN** it states that the project-tree location is no longer read, in addition to stating that no credential was found centrally

### Requirement: The migration reports what it moved and never widens permissions

The migration command SHALL report each value it carried across, naming the field and not
its value for anything secret. The configuration it writes SHALL be created with
owner-only permissions.

The command SHALL NOT delete the older file, so that a person can verify the result against
its source before removing it themselves.

#### Scenario: The report names fields, not secrets

- **WHEN** the migration command completes
- **THEN** it lists the fields it carried across, and no credential value appears in its output

#### Scenario: The written configuration is owner-only

- **WHEN** the migration command writes the provider configuration
- **THEN** the file's mode grants no permission beyond the owner's

#### Scenario: The source file survives the migration

- **WHEN** the migration command completes successfully
- **THEN** the older configuration file still exists

### Requirement: The migration does not copy the shipped id mapping

The anthropic declaration the migration generates SHALL carry no `model_ids` block, so the shipped default mapping applies to it and follows every later release. The migration MUST NOT write the shipped table into the file, because a declared block replaces the default whole and a copy stops every later move of a shorthand at the machine.

#### Scenario: A migrated machine follows a release

- **WHEN** a machine was migrated and set-core later moves a shorthand to a new release
- **THEN** a launch on that machine with that shorthand uses the new release, with no edit to the file

### Requirement: An older file's copied id table is brought along by an explicit command

The provider-configuration command SHALL offer a refresh that, as a dry run by default, reports and with an explicit write flag applies these steps to the anthropic declaration:
- When every entry of its `model_ids` block is a copy of a value set-core ships or once shipped for that name, the refresh removes the block.
- When the block also holds an entry set-core never shipped for that name, the refresh keeps that entry, replaces each stale copy with the current shipped value, and adds the shipped names the block lacks.
- The refresh adds to the catalogue the shipped names it does not offer, and never removes a name.

A write SHALL first save a timestamped backup beside the file and SHALL keep the file's permission bits. The refresh SHALL touch nothing outside the anthropic declaration. Running it on an up-to-date file SHALL change nothing.

#### Scenario: A pure copy is removed

- **WHEN** the anthropic block maps `sonnet` to `claude-sonnet-4-6`, a value set-core shipped earlier, and every other entry is a current or earlier shipped value
- **THEN** `refresh --write` removes the block, a backup exists, and `sonnet` then launches the current shipped id

#### Scenario: A real override survives

- **WHEN** the block maps `opus` to an id set-core never shipped for `opus`, and `sonnet` to an earlier shipped value
- **THEN** the refresh keeps the `opus` entry, rewrites `sonnet` to the current value, and reports both decisions

#### Scenario: The dry run writes nothing

- **WHEN** `refresh` runs without the write flag
- **THEN** the file's bytes are unchanged and the planned edits are printed
