# Orchestration Directive Integration Specification

## Purpose

TBD — restored after delta-sync structural cleanup. Update Purpose with a one-line statement of what this capability owns.

### In scope
- Engine loads plugin orchestration directives via profile method
- Directives influence dispatch serialization and post-merge actions
- NullProfile provides empty default

### Out of scope
- Defining new directive action types
- Changing the OrchestrationDirective dataclass in set-project-base

## Requirements

### Requirement: NullProfile defines get_orchestration_directives
`NullProfile` in `profile_loader.py` SHALL define `get_orchestration_directives()` returning an empty list.

#### Scenario: NullProfile returns empty directives
- **WHEN** no plugin is loaded and NullProfile is active
- **THEN** `profile.get_orchestration_directives()` returns `[]`

### Requirement: Engine loads plugin directives at startup
The engine SHALL call `profile.get_orchestration_directives()` and merge the returned directives with any directives from `orchestration.yaml`.

#### Scenario: Plugin directives loaded
- **WHEN** the engine starts and the loaded profile returns 7 orchestration directives
- **THEN** all 7 directives are active for the orchestration run

### Requirement: Directives influence dispatch behavior
Directives with `action: "serialize"` SHALL cause the engine to dispatch matching changes sequentially instead of in parallel.

#### Scenario: Serialize directive prevents parallel dispatch
- **WHEN** a directive specifies `action: "serialize"` with trigger matching i18n changes
- **AND** two i18n-related changes are ready for dispatch
- **THEN** the engine dispatches them one at a time, not in parallel

### Requirement: Directives influence post-merge behavior
Directives with `action: "post-merge"` SHALL cause the engine to run the specified command after a matching change is merged.

#### Scenario: Post-merge directive runs command
- **WHEN** a directive specifies `action: "post-merge"` with config `{"command": "npx prisma generate"}`
- **AND** a change matching the trigger is successfully merged
- **THEN** the engine runs `npx prisma generate` after the merge
