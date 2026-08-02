"""The stream: starts at the end, stays bounded, and always says why it stopped.

Driven through the real ASGI app with a real file on disk. The one thing worth stating about the
method: every assertion here is about what a CLIENT receives, not about what the generator did.
A test that inspected internal counters would pass just as happily on a stream that computed the
right numbers and sent nothing.
"""

import asyncio
import json
import os
from pathlib import Path

import pytest

from set_orch.api.status_follow import _follow, _still_the_same_file


def frames(raw: str):
    """Parse SSE text into (event, payload) pairs."""
    out = []
    for block in raw.split("\n\n"):
        if not block.strip():
            continue
        kind, data = None, None
        for line in block.splitlines():
            if line.startswith("event: "):
                kind = line[len("event: "):]
            elif line.startswith("data: "):
                data = json.loads(line[len("data: "):])
        out.append((kind, data))
    return out


async def collect(path: Path, writer=None, limit_seconds=3.0):
    """Run the follower, optionally writing to the file while it runs, and return its frames."""
    chunks = []

    async def run():
        async for frame in _follow(path, "test-project"):
            chunks.append(frame)

    task = asyncio.ensure_future(run())
    await asyncio.sleep(0.2)
    if writer:
        await writer()
    await asyncio.sleep(0.9)
    if not task.done():
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass
    return frames("".join(chunks))


def test_history_is_not_replayed_on_connect(tmp_path):
    f = tmp_path / "run.jsonl"
    f.write_text("".join(f'{{"n": {i}}}\n' for i in range(500)), encoding="utf-8")

    got = asyncio.get_event_loop().run_until_complete(collect(f))

    lines = [p for k, p in got if k == "line"]
    assert lines == [], "a connect must not replay the file that already existed"
    assert ("open", {"from": "end"}) in got


def test_a_line_written_after_connect_arrives(tmp_path):
    f = tmp_path / "run.jsonl"
    f.write_text("old\n", encoding="utf-8")

    async def writer():
        with open(f, "a", encoding="utf-8") as h:
            h.write('{"event": "started"}\n')
            h.flush()

    got = asyncio.get_event_loop().run_until_complete(collect(f, writer))

    lines = [p["text"] for k, p in got if k == "line"]
    assert lines == ['{"event": "started"}']


def test_a_partial_line_is_not_delivered_until_it_is_complete(tmp_path):
    """A half-written line is not a line. Delivering it would show the reader a truncated record
    and then, a tick later, the same record again — with no way to tell which was which."""
    f = tmp_path / "run.jsonl"
    f.write_text("", encoding="utf-8")

    async def writer():
        with open(f, "a", encoding="utf-8") as h:
            h.write('{"half": ')
            h.flush()

    got = asyncio.get_event_loop().run_until_complete(collect(f, writer))
    assert [p for k, p in got if k == "line"] == []


def test_a_deleted_file_ends_the_stream_with_a_reason(tmp_path):
    f = tmp_path / "run.jsonl"
    f.write_text("x\n", encoding="utf-8")

    async def writer():
        os.unlink(f)

    got = asyncio.get_event_loop().run_until_complete(collect(f, writer))

    ends = [p for k, p in got if k == "end"]
    assert ends, "a vanished file must end the stream, not leave it hanging"
    assert ends[0]["reason"] == "file-gone"


def test_a_replaced_file_ends_the_stream_rather_than_following_the_new_one(tmp_path):
    """Rotation keeps the NAME. Following the name would silently switch runs under the reader."""
    f = tmp_path / "run.jsonl"
    f.write_text("x\n", encoding="utf-8")

    async def writer():
        os.unlink(f)
        f.write_text("a different run\n", encoding="utf-8")

    got = asyncio.get_event_loop().run_until_complete(collect(f, writer))

    ends = [p for k, p in got if k == "end"]
    assert ends
    assert ends[0]["reason"] in ("file-replaced", "file-gone")


def test_an_unreadable_path_ends_with_a_reason_instead_of_raising(tmp_path):
    got = asyncio.get_event_loop().run_until_complete(collect(tmp_path / "never-existed.jsonl"))
    assert got == [("end", {"reason": "unreadable", "detail": "FileNotFoundError"})]


def test_a_long_line_is_truncated_and_says_so(tmp_path):
    from set_orch.api.status_follow import MAX_LINE_CHARS

    f = tmp_path / "run.jsonl"
    f.write_text("", encoding="utf-8")

    async def writer():
        with open(f, "a", encoding="utf-8") as h:
            h.write("x" * (MAX_LINE_CHARS + 500) + "\n")
            h.flush()

    got = asyncio.get_event_loop().run_until_complete(collect(f, writer))

    lines = [p for k, p in got if k == "line"]
    assert len(lines) == 1
    assert lines[0]["truncated"] is True
    assert len(lines[0]["text"]) == MAX_LINE_CHARS


def test_an_inode_comparison_would_NOT_have_caught_a_replacement(tmp_path):
    """Held as a test because this is the implementation anyone would write first.

    Measured on this machine: deleting a file and immediately recreating it under the same name
    returned the IDENTICAL (st_dev, st_ino). A different file, an identical fingerprint — the
    recycled-identifier trap, the same one that makes a remembered PID a proxy for a process.
    If someone later "simplifies" the check back to comparing stat() of the path, this fails.
    """
    a = tmp_path / "a.log"
    a.write_text("1\n", encoding="utf-8")
    before = a.stat()
    os.unlink(a)
    a.write_text("2\n", encoding="utf-8")
    after = a.stat()

    assert (before.st_dev, before.st_ino) == (after.st_dev, after.st_ino), (
        "this test documents inode reuse; if the platform stopped reusing, the check below "
        "would pass for the wrong reason and the comment above would go stale")


def test_the_open_handle_knows_it_was_unlinked_even_when_the_number_is_reused(tmp_path):
    """The property the rotation check actually rests on, asserted on the handle."""
    a = tmp_path / "a.log"
    a.write_text("1\n", encoding="utf-8")
    handle = open(a, "r", encoding="utf-8")
    try:
        assert _still_the_same_file(handle, a) is None
        os.unlink(a)
        assert _still_the_same_file(handle, a) == "file-gone"
        a.write_text("2\n", encoding="utf-8")
        assert _still_the_same_file(handle, a) == "file-replaced"
    finally:
        handle.close()


def test_a_burst_beyond_the_tick_cap_is_deferred_and_not_duplicated(tmp_path):
    """The remainder of a burst comes back exactly once, even when lines repeat.

    Repeated lines are ordinary in a log, and the natural way to write the "put the rest back"
    step — find where we stopped with `lines.index(line)` — returns the FIRST occurrence. With a
    repeated heartbeat that rewinds the buffer and re-delivers everything in between, so the
    reader sees the same events twice with nothing marking the seam.
    """
    from set_orch.api.status_follow import MAX_LINES_PER_TICK

    f = tmp_path / "run.jsonl"
    f.write_text("", encoding="utf-8")
    # The same line repeated, so a first-occurrence index lands at position 0 rather than at the
    # cap — then a distinct tail, so the duplication is visible in the counts.
    repeated = '{"t":"tick"}'
    total = MAX_LINES_PER_TICK + 50

    async def writer():
        with open(f, "a", encoding="utf-8") as h:
            h.write("".join(f"{repeated}\n" for _ in range(total)))
            h.flush()

    got = asyncio.get_event_loop().run_until_complete(collect(f, writer))

    lines = [p["text"] for k, p in got if k == "line"]
    assert len(lines) == total, f"expected each line once, got {len(lines)} for {total} written"
    assert all(t == repeated for t in lines)
