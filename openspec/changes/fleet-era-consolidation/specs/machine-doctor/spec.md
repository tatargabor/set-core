## ADDED Requirements

### Requirement: Archived projects are not checked
A registry entry marked archived SHALL NOT be checked. The doctor SHALL print one summary
line with the number of archived entries skipped, and `--project <name>` naming an archived
entry SHALL check it anyway.

#### Scenario: An archived entry in the registry
- **WHEN** the registry holds three archived entries
- **THEN** none of them appears as a project check and one line says "3 archived projects skipped"

#### Scenario: Asking for an archived project by name
- **WHEN** `set-doctor --project <name>` names an archived entry
- **THEN** that project is checked as any other

### Requirement: The project role rule is checked
For each checked project, the doctor SHALL `warn` when the generated project role rule is
missing or older than the role file, with `set-project roles` as the fix, and SHALL `skip`
with the reason when no role file exists.

#### Scenario: A stale role rule
- **WHEN** the role file changed after a project's rule was generated
- **THEN** the role check warns and names `set-project roles` as the fix
