"""Shared fixtures for set-project-example tests."""

import pytest

from set_project_example import DungeonProjectType


@pytest.fixture
def pt():
    """A fresh DungeonProjectType instance."""
    return DungeonProjectType()


@pytest.fixture
def starter_dir(pt):
    """The starter template directory on disk."""
    d = pt.get_template_dir("starter")
    assert d is not None and d.is_dir()
    return d
