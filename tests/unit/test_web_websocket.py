"""Tests for set_orch WebSocket connection manager."""

import asyncio
import json
import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "lib"))

from set_orch.websocket import ConnectionManager


def test_manager_connect_disconnect():
    """ConnectionManager tracks client count correctly."""
    mgr = ConnectionManager()
    assert mgr.client_count("proj") == 0


def test_manager_broadcast_no_clients():
    """Broadcasting with no clients is a no-op."""
    mgr = ConnectionManager()
    # Run async broadcast in sync context
    asyncio.get_event_loop().run_until_complete(
        mgr.broadcast("proj", {"event": "test", "data": {}})
    )


def test_manager_disconnect_nonexistent():
    """Disconnecting from unknown project doesn't crash."""
    mgr = ConnectionManager()

    class FakeWS:
        pass

    mgr.disconnect("proj", FakeWS())  # should not raise
