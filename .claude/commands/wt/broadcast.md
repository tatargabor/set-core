Broadcast what you're working on to other agents.

**Usage**: `/wt:broadcast <message>`

**Input**: The argument after the command is the broadcast message — a short free-form description of what you're currently working on.

**What to do**:

1. Read the current `.wt/activity.json` if it exists (to preserve `skill`, `skill_args`, `modified_files`)
2. Update or create `.wt/activity.json` with the broadcast message and current timestamp
3. The file format:
```json
{
  "skill": "<preserved from existing>",
  "skill_args": "<preserved from existing>",
  "broadcast": "<the message from the user>",
  "modified_files": "<preserved from existing>",
  "updated_at": "<current ISO8601 UTC timestamp>"
}
```
4. Confirm the broadcast was set

**Important**:
- The broadcast field OVERWRITES the previous broadcast (not append)
- Preserve all other existing fields from activity.json
- If activity.json doesn't exist, create it with just broadcast and updated_at
- Use UTC timestamps in ISO8601 format (e.g., "2026-02-07T21:00:00Z")

ARGUMENTS: $ARGUMENTS
