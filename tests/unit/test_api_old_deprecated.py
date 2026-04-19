"""Section 15b.2: ensure `set_orch._api_old` cannot be imported.

The legacy REST surface is preserved on disk for `git blame` / `git log`
archaeology, but importing it must raise `ImportError` so re-introducing
it as a dependency fails fast.
"""

from __future__ import annotations

import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "lib"))


def test_importing_api_old_raises_import_error():
    # Drop the cached module if a prior test imported the package.
    sys.modules.pop("set_orch._api_old", None)
    with pytest.raises(ImportError) as exc:
        import set_orch._api_old  # noqa: F401
    assert "deprecated" in str(exc.value).lower()
    assert "Section 15b.2" in str(exc.value)


def test_active_api_module_still_works():
    # Sanity check: the canonical replacement is importable.
    sys.modules.pop("set_orch.api", None)
    import set_orch.api  # noqa: F401
