"""Where the owner listens, and what an operator is told to run — per platform.

Every test here parameterises `sys.platform` rather than skipping on the one it
is not running on. A skipped test is a test that reports green for a platform it
never executed, and the whole point of this file is the platform that CI does not
run: a Linux CI that skips the macOS cases would have said nothing was wrong
while the start control was dead on every Mac.
"""
from __future__ import annotations

import os

import pytest

from set_orch.fleet import ownerd as ownerd_mod
from set_orch.fleet import owner_client as client_mod
from set_orch.fleet.owner import OwnerError
from set_orch.fleet.owner_client import OwnerClient, OwnerUnavailable, start_command
from set_orch.fleet.ownerd import SOCKET_NAME, default_socket_path


@pytest.fixture
def as_platform(monkeypatch):
    """Run a body as though this were another platform."""
    def _set(name: str):
        monkeypatch.setattr(ownerd_mod.sys, "platform", name)
        monkeypatch.setattr(client_mod.sys, "platform", name)
    return _set


# --- where the socket lives ------------------------------------------------ #

def test_macos_resolves_a_path_that_exists(as_platform, monkeypatch):
    """AC-1. The failure this replaces named `/run/user/501`, a directory macOS
    has never had — so the reader was sent to look for something that could not
    be there."""
    as_platform("darwin")
    monkeypatch.delenv("XDG_RUNTIME_DIR", raising=False)

    path = default_socket_path()

    assert not path.startswith("/run/user/")
    from set_orch.paths import SET_TOOLS_DATA_DIR
    assert path.startswith(SET_TOOLS_DATA_DIR)
    assert path.endswith(SOCKET_NAME)


def test_linux_keeps_the_unit_files_expansion(as_platform, monkeypatch):
    """AC-2. `%t` in the systemd unit expands to `$XDG_RUNTIME_DIR`. If this
    resolver drifted from it, the service would bind one path and every client
    would connect to another."""
    as_platform("linux")
    monkeypatch.setenv("XDG_RUNTIME_DIR", "/run/user/4242")

    assert default_socket_path() == os.path.join("/run/user/4242", SOCKET_NAME)


def test_linux_falls_back_to_run_user_when_the_variable_is_absent(as_platform, monkeypatch):
    as_platform("linux")
    monkeypatch.delenv("XDG_RUNTIME_DIR", raising=False)

    assert default_socket_path() == os.path.join(f"/run/user/{os.getuid()}", SOCKET_NAME)


def test_the_client_and_the_service_agree(as_platform, monkeypatch):
    """AC-3. Asserted through the client's own default rather than by calling the
    resolver twice: the question is whether the CLIENT uses it, and a test that
    calls the resolver directly would pass on a client that hardcoded a path."""
    as_platform("darwin")
    monkeypatch.delenv("XDG_RUNTIME_DIR", raising=False)

    assert OwnerClient().socket_path == default_socket_path()


def test_looking_up_the_path_does_not_create_the_directory(as_platform, monkeypatch, sock_dir):
    """A client asking where the socket is must not bring the runtime directory
    into being. If it did, "the owner is not running" and "nothing has ever run
    on this machine" would leave the same trace on disk."""
    as_platform("darwin")
    target = sock_dir / "never-created"
    monkeypatch.setattr(ownerd_mod, "_runtime_dir", lambda: str(target))

    default_socket_path()
    assert not target.exists()

    default_socket_path(create=True)
    assert target.is_dir()


# --- the length limit ------------------------------------------------------ #

def test_an_over_long_path_is_named_as_such(as_platform, monkeypatch):
    """AC-4. The errno this replaces is ENOENT, which reads as a missing
    directory — so the assertion is not only that it fails, but that it fails
    without sending the reader down that path."""
    as_platform("darwin")
    monkeypatch.setattr(ownerd_mod, "_runtime_dir", lambda: "/" + "x" * 120)

    with pytest.raises(OwnerError) as excinfo:
        default_socket_path()

    message = str(excinfo.value)
    assert "104" in message, "the limit is not named"
    assert str(len(("/" + "x" * 120 + "/" + SOCKET_NAME).encode())) in message, \
        "the actual byte length is not named"
    assert "x" * 120 in message, "the path itself is not named"
    # Not "these words are absent" — the message deliberately contains them, in
    # order to deny the reading. What must be absent is the errno phrasing
    # presented AS the cause, which is what `bind()` would have produced.
    assert "is not a missing directory" in message, \
        "the message does not head off the reading it exists to prevent"
    assert not message.startswith("[Errno")


def test_a_path_that_fits_on_linux_but_not_on_macos_is_judged_per_platform(
    as_platform, monkeypatch,
):
    """The four-byte band where the platform actually decides the answer.

    Without this, a single-platform test could pass against a hardcoded limit of
    either 104 or 108 and nobody would learn which one was wrong.
    """
    # A path of exactly 106 bytes: inside Linux's 108, outside macOS's 104.
    filler = 106 - len("/") - len("/") - len(SOCKET_NAME)
    directory = "/" + "y" * filler
    candidate = os.path.join(directory, SOCKET_NAME)
    assert len(candidate.encode()) == 106, "the fixture no longer sits in the band"

    monkeypatch.setattr(ownerd_mod, "_runtime_dir", lambda: directory)

    as_platform("linux")
    assert default_socket_path() == candidate

    as_platform("darwin")
    with pytest.raises(OwnerError):
        default_socket_path()


# --- the command an operator is shown -------------------------------------- #

def test_macos_is_not_told_to_run_systemctl(as_platform):
    """AC-8. The reported defect: a Mac was told to run `systemctl --user start
    set-agent-owner.service`, which produces an error about an unknown command
    and says nothing about the owner."""
    as_platform("darwin")

    command = start_command()
    assert "systemctl" not in command
    assert command.startswith("launchctl ")
    assert str(os.getuid()) in command


def test_linux_keeps_its_command(as_platform):
    """AC-9."""
    as_platform("linux")

    assert start_command() == "systemctl --user start set-agent-owner.service"


@pytest.mark.parametrize("platform", ["darwin", "linux"])
def test_the_reason_is_reported_not_replaced_by_the_remedy(as_platform, sock_dir, platform):
    """AC-10. A remedy without a diagnosis is a guess the reader cannot check —
    and on the path where the socket exists but nothing answers, the remedy is
    not even the right one."""
    as_platform(platform)
    absent = str(sock_dir / "nothing.sock")

    with pytest.raises(OwnerUnavailable) as excinfo:
        OwnerClient(absent).health()

    message = str(excinfo.value)
    assert absent in message, "the path that failed is not named"
    assert "No such file or directory" in message, "the underlying reason is gone"
    assert start_command() in message, "the command for this platform is not offered"
