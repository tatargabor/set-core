"""The whole vertical slice, against the REAL owner: start → terminal → stop.

**Why this exists as a file rather than as measurements in a commit message.**
Every hazard this slice has is one a unit test cannot reach, because each is a
property of a real process under a real pty:

- an agent whose pty nobody drains **freezes after about a screenful** — measured
  at 17 408 bytes, and a frozen agent looks exactly like a thinking one;
- a scope in `deactivating` is not gone, and a stop that believes otherwise
  reports success while the agent runs on;
- the owner's own forked child becomes a zombie if nobody reaps it, and `ps -p`
  reports a zombie as an existing process;
- closing a terminal view must not stop the agent.

All four were found by running this by hand on 2026-08-18/19. Running it by hand
again is what this file replaces.

**It is skipped unless asked for**, because it starts real agent processes:

    SET_FLEET_LIVE=1 python -m pytest tests/integration/test_fleet_vertical_slice.py -q

Everything it starts, it stops — including on failure.
"""

from __future__ import annotations

import asyncio
import os
import subprocess
import time

import pytest

pytestmark = pytest.mark.skipif(
    os.environ.get("SET_FLEET_LIVE") != "1",
    reason="starts real agent processes; set SET_FLEET_LIVE=1 to run",
)

LABEL = "vertical-slice-probe"
CWD = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


@pytest.fixture
def owner_client():
    from set_orch.fleet.owner_client import OwnerClient, OwnerClientError

    client = OwnerClient()
    try:
        client.health()
    except OwnerClientError as exc:
        pytest.skip(f"the agent owner is not running: {exc}")
    # Leave nothing behind from an earlier failed run.
    try:
        client.stop(LABEL)
    except OwnerClientError:
        pass
    yield client
    try:
        client.stop(LABEL)
    except OwnerClientError:
        pass


def _pid_alive(pid: int) -> bool:
    """Whether a pid names a RUNNING process — a zombie does not count.

    `ps -p` answers yes for a zombie, which is the proxy that misfired while
    measuring the stop path: an agent that was dead read as alive.
    """
    try:
        with open(f"/proc/{pid}/stat", encoding="utf-8") as handle:
            fields = handle.read()
    except OSError:
        return False
    state = fields[fields.rfind(")") + 2:].split()[0]
    return state != "Z"


def test_a_started_agent_does_not_freeze_behind_an_undrained_pty(owner_client):
    """The measurement that turned a design word into a mechanism.

    A writer under a pty stops when the buffer fills — 17 408 bytes here — so an
    owner that holds a master without reading it does not fail, it FREEZES the
    agent. This drives far past that bound and asserts the writer finished.
    """
    import sys

    marker = f"/tmp/fleet-slice-{os.getpid()}.txt"
    child = (
        "import sys\n"
        "for _ in range(400):\n"
        "    sys.stdout.write('y' * 1000); sys.stdout.flush()\n"
        f"open({marker!r}, 'w').write('done')\n"
    )
    try:
        agent = owner_client.start(
            label=LABEL, cwd=CWD, argv=[sys.executable, "-c", child]
        )
        assert agent["population"] == "started-here"
        deadline = time.time() + 30
        while time.time() < deadline and not os.path.exists(marker):
            time.sleep(0.2)
        assert os.path.exists(marker), (
            "the child never finished: 400 000 bytes did not get through, so the "
            "pty is not being drained and a real agent would be frozen"
        )
        tail = owner_client.tail(LABEL)
        assert tail["drained_total"] >= 400_000
    finally:
        if os.path.exists(marker):
            os.unlink(marker)


def test_the_scope_is_a_sibling_of_the_web_service_not_a_child(owner_client):
    """The guarantee the whole split rests on: a scope inside the dashboard's
    cgroup would die with it while the surface went on promising survival.
    """
    import sys

    owner_client.start(label=LABEL, cwd=CWD,
                       argv=[sys.executable, "-c", "import time; time.sleep(60)"])
    cgroup = subprocess.run(
        ["systemctl", "--user", "show", f"set-agent-{LABEL}.scope", "-p", "ControlGroup", "--value"],
        capture_output=True, text=True,
    ).stdout.strip()
    service = subprocess.run(
        ["systemctl", "--user", "show", "set-web.service", "-p", "ControlGroup", "--value"],
        capture_output=True, text=True,
    ).stdout.strip()
    assert cgroup and service
    assert not cgroup.startswith(service + "/"), "the agent landed INSIDE the dashboard's cgroup"
    assert os.path.dirname(cgroup) == os.path.dirname(service), "not a sibling"


def test_stop_only_reports_gone_when_the_process_really_is(owner_client):
    """Measured 2026-08-18: `stop()` returned `gone=True` in 0.0 seconds while
    the agent ran on for four minutes, because `deactivating` is not `active` and
    that was being read as gone. The assertion is on the PROCESS, and a zombie
    does not count as alive — `ps -p` says it does, which is how this was nearly
    mis-measured in the other direction.
    """
    import sys

    agent = owner_client.start(label=LABEL, cwd=CWD,
                               argv=[sys.executable, "-c", "import time; time.sleep(300)"])
    pid = agent["pid"]
    assert _pid_alive(pid)

    result = owner_client.stop(LABEL)
    assert result["found"] is True and result["gone"] is True
    assert not _pid_alive(pid), "stop reported gone while the process was still running"


def test_the_owner_reaps_its_children_and_keeps_none(owner_client):
    """One start/stop cycle used to leave a `Zs [claude] <defunct>` child for the
    life of a service whose whole point is to be long-lived.
    """
    import sys

    owner_pid = owner_client.health()["pid"]
    owner_client.start(label=LABEL, cwd=CWD,
                       argv=[sys.executable, "-c", "import time; time.sleep(60)"])
    owner_client.stop(LABEL)
    time.sleep(1)
    children = subprocess.run(
        ["ps", "-o", "pid=,stat=", "--ppid", str(owner_pid)], capture_output=True, text=True
    ).stdout.strip()
    assert "Z" not in children, f"the owner is holding a zombie: {children!r}"


def test_a_viewer_that_leaves_does_not_take_the_agent_with_it(owner_client):
    """Task 5.4, over the real socket: attach, read the replayed screen, detach —
    and the agent is still held and still running afterwards.
    """
    import sys

    from set_orch.fleet.owner_client import OwnerStream

    agent = owner_client.start(
        label=LABEL, cwd=CWD,
        argv=[sys.executable, "-c",
              "import sys,time\nsys.stdout.write('HELLO-SLICE\\n'); sys.stdout.flush()\ntime.sleep(60)"],
    )
    time.sleep(2)

    async def watch():
        stream = OwnerStream(LABEL)
        ack = await asyncio.wait_for(stream.open(), timeout=10)
        frame, replay = await asyncio.wait_for(stream.frames().__anext__(), timeout=10)
        await stream.close()
        return ack, frame, replay

    loop = asyncio.new_event_loop()
    try:
        ack, frame, replay = loop.run_until_complete(watch())
    finally:
        loop.close()

    assert ack["attached"] == LABEL and replay is True
    assert b"HELLO-SLICE" in frame, "the replayed screen did not carry what was already printed"
    assert _pid_alive(agent["pid"]), "closing the view stopped the agent"
    assert [a["label"] for a in owner_client.list_agents()] == [LABEL]
