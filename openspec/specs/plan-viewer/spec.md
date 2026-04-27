# Plan Viewer Specification

## Purpose

TBD — restored after delta-sync structural cleanup. Update Purpose with a one-line statement of what this capability owns.

## Requirements

### Requirement: Decompose plan viewer
Display the orchestration decompose plan in a structured view.

#### Scenario: View current plan
- **WHEN** the dashboard loads for a project with orchestration plans
- **THEN** a "Plan" tab or section is available
- **THEN** it shows the plan version, change count, and a table/tree of planned changes

#### Scenario: Plan change details
- **WHEN** viewing the plan
- **THEN** each change shows: name, complexity, scope, dependencies, change_type
- **THEN** dependencies are visualized (indentation or arrows)

#### Scenario: Multiple plan versions
- **WHEN** multiple plan files exist (e.g., `plan-v1-*.json`, `plan-v2-*.json`)
- **THEN** the user can switch between plan versions
- **THEN** the latest version is shown by default

### Requirement: Plan API endpoint

#### Scenario: List plans
- **WHEN** `GET /api/{project}/plans` is called
- **THEN** returns a list of plan files with version and creation date

#### Scenario: Read plan
- **WHEN** `GET /api/{project}/plans/{filename}` is called
- **THEN** returns the parsed plan JSON
