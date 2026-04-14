"""Regression: update_change_field(..., "extras", {...}) nests under
change.extras["extras"] instead of replacing the dict.

Bug surfaced on micro-web-run-20260415-0014 foundation-and-content:
  The dispatcher called update_change_field(state, name, "extras",
  {**change.extras, "assigned_e2e_port": N}) intending to replace the
  whole extras dict. But `"extras"` is not in the known-fields set
  (it's explicitly excluded), so the setter routed the write into
  change.extras["extras"] — producing nested `{'extras': {'extras':
  {'assigned_e2e_port': N}}}` across successive dispatches.

Tier 2 code (cross-change regression) reads change.extras.merged_scope_files
at the TOP level, so nesting would silently bypass detection.

This test guards the routing behavior so future code can't regress.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(_ROOT / "lib"))


def _make_state(path: Path) -> None:
    # Change serialization flattens extras into the top-level dict — never
    # write a literal "extras" JSON key here (from_dict would treat it as an
    # unknown field and nest it).
    path.write_text(json.dumps({
        "status": "running",
        "changes": [{"name": "c1", "status": "pending", "scope": ""}],
    }))


def test_update_change_field_extras_key_lands_at_top_level(tmp_path: Path):
    """When writing an individual extras key by name, it must land at
    change.extras[<key>] — NOT change.extras['extras']."""
    from set_orch.state import load_state, update_change_field

    state_file = tmp_path / "state.json"
    _make_state(state_file)
    update_change_field(str(state_file), "c1", "assigned_e2e_port", 4088)

    loaded = load_state(str(state_file))
    change = loaded.changes[0]
    assert change.extras.get("assigned_e2e_port") == 4088
    assert "extras" not in change.extras, (
        f"expected flat extras, got nested: {change.extras!r}"
    )


def test_second_extras_key_write_preserves_first(tmp_path: Path):
    """Writing a second individual key must not clobber the first."""
    from set_orch.state import load_state, update_change_field

    state_file = tmp_path / "state.json"
    _make_state(state_file)
    update_change_field(str(state_file), "c1", "assigned_e2e_port", 4088)
    update_change_field(
        str(state_file), "c1", "merged_scope_files",
        ["src/app/page.tsx", "src/lib/util.ts"],
    )
    loaded = load_state(str(state_file))
    change = loaded.changes[0]
    assert change.extras["assigned_e2e_port"] == 4088
    assert change.extras["merged_scope_files"] == [
        "src/app/page.tsx", "src/lib/util.ts",
    ]
    assert "extras" not in change.extras
