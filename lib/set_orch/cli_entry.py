#!/usr/bin/env python3
"""Entry point for set-orch-core when invoked via bash wrapper.

The bash wrapper (bin/set-orch-core) resolves the correct Python interpreter
and exec's this file. This avoids shebang issues on macOS where
/usr/bin/env python3 resolves to system Python 3.9.
"""
from __future__ import annotations

import sys
import os

# Add lib/ to path so set_orch package is importable without pip install
lib_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if lib_dir not in sys.path:
    sys.path.insert(0, lib_dir)

from set_orch.cli import main

if __name__ == "__main__":
    main()
