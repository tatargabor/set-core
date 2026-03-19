"""Python entry point for Claude Code memory hooks.

Called by bin/set-hook-memory:
    python3 -m set_hooks <EventName> <InputFile> <CacheFile> [--set-core-root DIR]

Reads hook input from the specified file (pre-read by bash wrapper),
dispatches to event handlers, and prints JSON output to stdout.
"""

import json
import os
import sys


def main():
    if len(sys.argv) < 4:
        print(f"Usage: {sys.argv[0]} <EventName> <InputFile> <CacheFile> [--set-core-root DIR]", file=sys.stderr)
        sys.exit(1)

    event = sys.argv[1]
    input_file = sys.argv[2]
    cache_file = sys.argv[3]

    set_tools_root = ""
    if "--set-core-root" in sys.argv:
        idx = sys.argv.index("--set-core-root")
        if idx + 1 < len(sys.argv):
            set_tools_root = sys.argv[idx + 1]

    # Read input data
    try:
        with open(input_file, "r") as f:
            input_data = json.load(f)
    except (json.JSONDecodeError, OSError):
        input_data = {}

    # Dispatch to event handler
    from .events import handle_event

    result = handle_event(
        event,
        input_data,
        cache_file,
        set_tools_root=set_tools_root,
        transcript_path=input_data.get("transcript_path", ""),
    )

    if result:
        print(result)


if __name__ == "__main__":
    main()
