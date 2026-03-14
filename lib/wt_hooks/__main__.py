"""Python entry point for Claude Code memory hooks.

Called by bin/wt-hook-memory:
    python3 -m wt_hooks <EventName> <InputFile> <CacheFile> [--wt-tools-root DIR]

Reads hook input from the specified file (pre-read by bash wrapper),
dispatches to event handlers, and prints JSON output to stdout.
"""

import json
import os
import sys


def main():
    if len(sys.argv) < 4:
        print(f"Usage: {sys.argv[0]} <EventName> <InputFile> <CacheFile> [--wt-tools-root DIR]", file=sys.stderr)
        sys.exit(1)

    event = sys.argv[1]
    input_file = sys.argv[2]
    cache_file = sys.argv[3]

    wt_tools_root = ""
    if "--wt-tools-root" in sys.argv:
        idx = sys.argv.index("--wt-tools-root")
        if idx + 1 < len(sys.argv):
            wt_tools_root = sys.argv[idx + 1]

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
        wt_tools_root=wt_tools_root,
        transcript_path=input_data.get("transcript_path", ""),
    )

    if result:
        print(result)


if __name__ == "__main__":
    main()
