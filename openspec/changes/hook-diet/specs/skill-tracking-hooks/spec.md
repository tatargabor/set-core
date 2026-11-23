## REMOVED Requirements

### Requirement: Stop hook refreshes skill timestamp
**Reason**: `hook-diet` (stage 3 of `fleet-era-consolidation`): the skill timestamp it refreshes is read only by orchestration-era routes and the git-bus MCP tools, both being retired; the fleet reads neither. The hook spawned a process on every Stop in every project.
**Migration**: none needed. `set-deploy-hooks` strips `set-hook-stop` from a project's settings on the next `set-project init`; the binary stays installed until every registered project has been re-initialised, so a not-yet-updated project never calls a missing command.
