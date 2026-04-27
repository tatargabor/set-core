# Spec: unified-project-routes

## Purpose

TBD — restored after delta-sync structural cleanup. Update Purpose with a one-line statement of what this capability owns.

### In scope
- Single `/p/:name/` URL prefix for all project-specific routes
- Route tree with app segments (`/p/:name/orch/`, `/p/:name/sentinel/`, etc.)
- Legacy redirect from `/set/:project/*` and `/manager/:project/*`
- Project name passed as prop (not useParams) to all page components

### Out of scope
- Deep linking to specific issue IDs or worktree names (keep existing behavior)
- URL-based state persistence (query params for filters, etc.)
- History/back-button behavior changes beyond what React Router provides

## Requirements

### Requirement: Unified URL prefix

All project-specific routes SHALL use the `/p/:name/` prefix. The route tree SHALL be organized by app segment: `/p/:name/orch/*` for Orchestration, `/p/:name/sentinel/*` for Sentinel, `/p/:name/issues/*` for Issues, `/p/:name/memory/*` for Memory, `/p/:name/settings` for Settings.

#### Scenario: Orchestration routes
- **WHEN** the user navigates to `/p/craftbrew-run12/orch`
- **THEN** the Orchestration dashboard renders showing Changes view
- **AND** sub-routes `/orch/sessions`, `/orch/worktrees`, `/orch/log`, `/orch/tokens`, `/orch/learnings` are available

#### Scenario: Sentinel routes
- **WHEN** the user navigates to `/p/craftbrew-run12/sentinel`
- **THEN** the Sentinel page renders showing status, controls, and session list

#### Scenario: Issues routes
- **WHEN** the user navigates to `/p/craftbrew-run12/issues`
- **THEN** the Issues list renders for that project

### Requirement: Legacy redirects

The router SHALL redirect old URL patterns to their new equivalents. `/set/:project` SHALL redirect to `/p/:name/orch`. `/set/:project/worktrees` SHALL redirect to `/p/:name/orch/worktrees`. `/manager/:project/issues` SHALL redirect to `/p/:name/issues`. `/manager/:project/mutes` SHALL redirect to `/p/:name/settings/mutes`. `/manager` (no project) SHALL redirect to `/`.

#### Scenario: Old SET URL redirect
- **WHEN** the user visits `/set/minishop-run2`
- **THEN** the browser redirects to `/p/minishop-run2/orch`

#### Scenario: Old Manager URL redirect
- **WHEN** the user visits `/manager/minishop-run2/issues`
- **THEN** the browser redirects to `/p/minishop-run2/issues`

### Requirement: Prop-based project passing

All page components SHALL receive the project name as a prop from the layout component. Page components SHALL NOT call `useParams()` to extract the project name. The SharedLayout component SHALL extract `:name` from the URL once and pass it down.

#### Scenario: Page receives project prop
- **WHEN** the SharedLayout renders a page component
- **THEN** the page component receives `project` as a string prop
- **AND** the page does not call `useParams()` for the project name
