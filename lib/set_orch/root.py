"""Resolve set-core installation root directory."""

from pathlib import Path

# lib/set_orch/root.py → lib/set_orch/ → lib/ → set-core root
SET_TOOLS_ROOT = str(Path(__file__).resolve().parent.parent.parent)
