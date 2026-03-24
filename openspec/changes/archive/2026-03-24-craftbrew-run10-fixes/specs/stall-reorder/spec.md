# Stall Detection Reorder

## Requirements

- STALL-001: In the ralph loop iteration handler, done check MUST run BEFORE stall detection. If all tasks are complete, mark done immediately — never stall a completed change.
- STALL-002: When done check passes, reset stall counter to 0 to prevent false stall on the next iteration boundary.
