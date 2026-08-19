"""The pty's geometry, and why it is READ rather than remembered — B-16.

Reported 2026-08-19: *"terminal also status bar elromlik ha projektet valtok,
beleirok, majd visszavaltok"*, with the half that names the cause —
*"beiras utan megjavul"*. A keystroke changes nothing about the socket, the pty
or the buffer; it makes the remote program repaint. So the screen was stale, and
a stale screen after a re-attach means the replay was rendered on a grid it was
not composed for.

The repair carries the geometry in the `attached` ack, which reaches the browser
BEFORE any replay byte. This file asserts the half that a test double cannot:
that the number is the pty's, now.
"""
import fcntl
import os
import pty
import struct
import sys
import termios
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "lib"))

from set_orch.fleet.owner import AgentOwner, OwnedAgent, OwnerError  # noqa: E402


def _owner_holding_a_pty():
    """An owner holding one real pty, with no systemd and no child process."""
    master, slave = pty.openpty()
    owner = AgentOwner.__new__(AgentOwner)
    owner._agents = {
        "term": OwnedAgent(
            label="term",
            unit="set-agent@term.scope",
            pid=os.getpid(),
            master_fd=master,
            cwd="/tmp",
        )
    }
    return owner, master, slave


def test_the_window_is_the_pty_s_own_size():
    owner, master, slave = _owner_holding_a_pty()
    try:
        owner.resize("term", 30, 100)
        assert owner.window("term") == (30, 100)
    finally:
        os.close(master)
        os.close(slave)


def test_a_size_set_behind_the_owner_s_back_is_still_reported():
    """The load-bearing one: a REMEMBERED size would pass the test above and
    fail this.

    `resize` is not the only thing that changes a window — another viewer, the
    program itself, a `stty` in the session. A stored copy is a second place,
    and it drifts silently in the direction that matters here: the viewer would
    render the replay on a grid the pty has not had for a while.
    """
    owner, master, slave = _owner_holding_a_pty()
    try:
        owner.resize("term", 30, 100)
        # Straight at the fd — the owner is not told.
        fcntl.ioctl(master, termios.TIOCSWINSZ, struct.pack("HHHH", 44, 132, 0, 0))
        assert owner.window("term") == (44, 132), (
            "the geometry was remembered rather than read; a replay would be "
            "rendered on a grid the pty no longer has"
        )
    finally:
        os.close(master)
        os.close(slave)


def test_a_dead_fd_says_nothing_rather_than_guessing():
    """`None`, never a default. A wrong geometry is worse than an absent one
    because the viewer APPLIES it — `(24, 80)` would silently reformat a screen
    that was drawn at 200 columns.
    """
    owner, master, slave = _owner_holding_a_pty()
    os.close(master)
    os.close(slave)
    assert owner.window("term") is None


def test_an_unheld_label_is_an_error_and_not_an_absent_size():
    """Two different answers to two different questions. `None` means *the
    terminal is here and could not be measured*; a label nobody holds is not a
    measurement problem, and collapsing them would make a typo look like a
    hardware quirk.
    """
    owner, master, slave = _owner_holding_a_pty()
    try:
        try:
            owner.window("nobody")
        except OwnerError:
            pass
        else:
            raise AssertionError("an unheld label answered as if it had a size")
    finally:
        os.close(master)
        os.close(slave)
