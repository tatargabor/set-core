"""Shared fixtures for mobile project type tests."""

import pytest
from set_project_mobile import MobileProjectType


@pytest.fixture
def pt():
    """Return a MobileProjectType instance."""
    return MobileProjectType()
