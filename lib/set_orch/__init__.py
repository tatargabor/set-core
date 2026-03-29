from __future__ import annotations

"""set_orch — Python core for set-core orchestration engine.

Provides reliable implementations of fragile bash internals:
- process: PID lifecycle with identity verification via psutil
- state: Typed JSON state management with dataclasses
- templates: Safe structured text generation with proper escaping
"""

__version__ = "0.1.0"
