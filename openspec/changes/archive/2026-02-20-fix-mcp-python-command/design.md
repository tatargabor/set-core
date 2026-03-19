## Context

`bin/set-project` registers the set-memory MCP server via:
```bash
claude mcp add set-memory -- python "$mcp_server"
```

This writes `"command": "python"` into `~/.claude.json`. On systems where only `python3` exists (most Linux distros), the MCP server fails to start with `python: command not found`.

The script `bin/set-memory-mcp-server.py` already has `#!/usr/bin/env python3` and is installed as executable.

## Goals / Non-Goals

**Goals:**
- MCP registration works on any platform without hardcoding a python binary
- Existing broken configs get fixed on next `set-project init`

**Non-Goals:**
- Windows support (shebangs don't apply)
- Changing how the set-core MCP server (uv-based) is registered

## Decisions

### Run the script directly via shebang

**Choice**: `claude mcp add set-memory -- "$mcp_server"` (no `python` prefix)

**Why**: The script's `#!/usr/bin/env python3` shebang handles interpreter resolution. The OS finds the right python — works on Linux, macOS, any Unix. No platform detection, no hardcoded binary.

**Alternative considered**: Detect python at registration time (`command -v python3 || command -v python`). Rejected because it bakes in an absolute path that goes stale if the user changes python installations.

### Migration: re-register on every init

**Choice**: Remove the `_is_mcp_registered` early-return guard and always re-register. `claude mcp add` is idempotent (overwrites existing entry).

**Why**: Simple, no JSON parsing needed. Re-running `claude mcp add` with the correct command overwrites the stale `"command": "python"` entry. Also future-proofs against any config drift.

## Risks / Trade-offs

- **[Risk]** Script not executable after manual copy → Mitigation: `install.sh` already does `chmod +x`. The script also has the shebang as line 1.
- **[Risk]** `claude mcp add` overwrites user customizations → Acceptable: the command and args are fully controlled by set-core, no user-customizable fields.
