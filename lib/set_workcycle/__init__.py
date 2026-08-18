"""set_workcycle — the work-unit engine.

A *work unit* is a piece of work run in a fresh agent context and closed by a verdict,
a gate and a commit — or set aside with a named resume condition.

This package sits **beside** the orchestration core, not inside it. The dependency
direction is a requirement, not a preference:

    set_workcycle  ->  set_orch        allowed
    set_orch       ->  set_workcycle   FORBIDDEN

Orchestration must keep working with this package deleted. The direction is asserted
by ``tests/unit/test_workcycle_dependency_direction.py`` rather than promised here.
"""

import logging

__all__ = ["__version__"]

# The module's own version, as required by `module-install`. Kept distinct from the
# framework's version: a project declares the module version it expects, and a
# mismatch against what is installed machine-wide has to be reportable.
__version__ = "0.1.0"

logger = logging.getLogger(__name__)
