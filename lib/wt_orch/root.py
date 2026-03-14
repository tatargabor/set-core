"""Resolve wt-tools installation root directory."""

from pathlib import Path

# lib/wt_orch/root.py → lib/wt_orch/ → lib/ → wt-tools root
WT_TOOLS_ROOT = str(Path(__file__).resolve().parent.parent.parent)
