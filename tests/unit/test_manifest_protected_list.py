"""A manifest's top-level `protected:` list must actually protect something.

Measured 2026-07-31: two shipped templates declare their protected paths in a top-level list
rather than per entry, and NOTHING READ THAT LIST. The manifest stated a guard that did not
exist — the reassuring direction, and invisible from either side: the file says the path is
protected, and a forced re-init overwrites it anyway.

Found sideways, while checking whether a consumer's hand-edited rules were at risk. They were
not (a different guard covers them), but the check walked past this one.
"""
import textwrap

import pytest

from set_orch.profile_deploy import _resolve_file_list


def _template(tmp_path, manifest_text, files):
    for f in files:
        p = tmp_path / f
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(f"contents of {f}")
    (tmp_path / "manifest.yaml").write_text(textwrap.dedent(manifest_text))
    import yaml
    return yaml.safe_load((tmp_path / "manifest.yaml").read_text())


def test_a_path_in_the_top_level_list_is_protected(tmp_path):
    manifest = _template(
        tmp_path,
        """
        core:
          - config.ts
          - rules/conventions.md
        protected:
          - config.ts
        """,
        ["config.ts", "rules/conventions.md"],
    )
    entries, warns = _resolve_file_list(tmp_path, manifest, None)
    by_path = {e.path: e for e in entries}
    assert by_path["config.ts"].protected is True, (
        "the manifest declared this path protected; before the fix the list was never read"
    )
    assert by_path["rules/conventions.md"].protected is False
    assert warns == []


def test_the_per_entry_flag_still_wins_when_both_are_present(tmp_path):
    # The list may only ADD protection. A broad list silently clearing a specific flag would
    # be the opposite of what either spelling looks like it means.
    manifest = _template(
        tmp_path,
        """
        core:
          - path: rules/conventions.md
            protected: true
        protected:
          - config.ts
        """,
        ["config.ts", "rules/conventions.md"],
    )
    entries, _ = _resolve_file_list(tmp_path, manifest, None)
    assert {e.path: e.protected for e in entries} == {"rules/conventions.md": True}


def test_an_absent_or_malformed_list_changes_nothing(tmp_path):
    # A manifest without the key, and one whose key is the wrong shape, must both behave
    # exactly as before — a parser that throws here would break every existing template.
    for decl in ("", "protected:\n", "protected: not-a-list\n"):
        manifest = _template(
            tmp_path,
            "core:\n  - config.ts\n" + decl,
            ["config.ts"],
        )
        entries, _ = _resolve_file_list(tmp_path, manifest, None)
        assert [e.protected for e in entries] == [False], decl


@pytest.mark.parametrize(
    "template,paths",
    [
        (
            "modules/mobile/set_project_mobile/templates/capacitor-nextjs",
            ["capacitor.config.ts", "rules/capacitor-conventions.md", "rules/native-bridge.md"],
        ),
        (
            "modules/example/set_project_example/templates/starter",
            ["rules/dungeon-integrity.md", "rules/contribution-guide.md"],
        ),
    ],
)
def test_the_shipped_templates_that_use_this_spelling_are_covered(template, paths):
    """The two templates this was found on — asserted against the real files, not a fixture.

    Without this, the fix could be correct in the abstract while the shipped manifest still
    spells it a third way nobody parses.
    """
    import pathlib
    import yaml

    root = pathlib.Path(__file__).resolve().parents[2] / template
    if not root.exists():                      # template removed → nothing to guard
        pytest.skip(f"{template} not present")
    manifest = yaml.safe_load((root / "manifest.yaml").read_text())
    entries, _ = _resolve_file_list(root, manifest, None)
    by_path = {e.path: e for e in entries}
    for p in paths:
        assert p in by_path, f"{p} is not deployed by {template}"
        assert by_path[p].protected is True, (
            f"{template} declares {p} protected and the parser must honour it"
        )
