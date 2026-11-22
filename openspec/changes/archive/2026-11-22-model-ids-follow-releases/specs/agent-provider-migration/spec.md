## ADDED Requirements

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
