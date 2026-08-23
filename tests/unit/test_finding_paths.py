"""Tests for resolving a stored finding path against its declared base.

The rule under test is `store relative, display absolute`: nothing here may change what
gets stored, and every case where the base is unknown must yield an empty string rather
than a path assembled from a guess — a path built from the wrong base looks openable,
which is worse than showing nothing.
"""

import os

from set_orch.finding_paths import (
    BASE_FIELD,
    BASE_REPO_ROOT,
    base_of,
    resolve_finding_path,
)


class TestResolveFindingPath:
    def test_relative_path_is_joined_to_the_root(self):
        assert resolve_finding_path("src/api/orders.ts", "/home/u/p") == (
            "/home/u/p/src/api/orders.ts"
        )

    def test_join_is_normalized(self):
        assert resolve_finding_path("./src/../src/a.ts", "/home/u/p/") == (
            "/home/u/p/src/a.ts"
        )

    def test_absolute_path_is_returned_without_the_root(self):
        out = resolve_finding_path("/already/abs/b.ts", "/home/u/p")
        assert out == "/already/abs/b.ts"
        assert "/home/u/p" not in out

    def test_absolute_path_is_normalized(self):
        assert resolve_finding_path("/already//abs/./b.ts", "/home/u/p") == (
            "/already/abs/b.ts"
        )

    def test_empty_file_yields_empty_not_the_bare_root(self):
        # The root on its own is a directory, not the file a finding names. Returning it
        # would render as an openable path pointing at the wrong thing.
        assert resolve_finding_path("", "/home/u/p") == ""
        assert resolve_finding_path("   ", "/home/u/p") == ""

    def test_empty_root_yields_empty_rather_than_a_guessed_base(self):
        assert resolve_finding_path("src/a.ts", "") == ""
        assert resolve_finding_path("src/a.ts", "   ") == ""

    def test_empty_root_still_resolves_an_absolute_path(self):
        # An absolute path needs no base, so a missing root must not suppress it.
        assert resolve_finding_path("/abs/a.ts", "") == "/abs/a.ts"

    def test_surrounding_whitespace_is_stripped(self):
        assert resolve_finding_path("  src/a.ts  ", "/home/u/p") == "/home/u/p/src/a.ts"

    def test_result_is_absolute(self):
        assert os.path.isabs(resolve_finding_path("src/a.ts", "/home/u/p"))


class TestBaseOf:
    def test_declared_base_is_returned(self):
        assert base_of({BASE_FIELD: "repo-root"}) == "repo-root"

    def test_missing_base_defaults_to_repo_root(self):
        # An entry written before the base was recorded carries no field. Failing here
        # would drop the path from every historical finding.
        assert base_of({}) == BASE_REPO_ROOT

    def test_empty_base_defaults_to_repo_root(self):
        assert base_of({BASE_FIELD: ""}) == BASE_REPO_ROOT
        assert base_of({BASE_FIELD: "   "}) == BASE_REPO_ROOT

    def test_non_dict_defaults_to_repo_root(self):
        assert base_of(None) == BASE_REPO_ROOT
        assert base_of("repo-root") == BASE_REPO_ROOT

    def test_base_constant_is_symbolic_not_a_path(self):
        # A literal root would be an absolute path — exactly what a committed artifact
        # must not carry.
        assert not os.path.isabs(BASE_REPO_ROOT)
        assert "/" not in BASE_REPO_ROOT
