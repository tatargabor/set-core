"""The process source: its contract, its dispatch, and both backends.

Every backend is driven **on either platform** — the Darwin one from recorded
`ps` and `lsof` output, the Linux one from a `/proc` tree built under `tmp_path`.
A backend verified only where it is already the default is verified only where it
is least likely to break.

What is NOT asserted here, deliberately: that a real `ps` on a real Mac finds a
real agent. That is a measurement, it is recorded in the change, and a test that
mocked it would report the property proven while proving nothing.
"""
from __future__ import annotations

import subprocess

import pytest

from set_orch.fleet import procsource
from set_orch.fleet.procsource import _darwin, _linux
from set_orch.fleet.procsource._types import CONTRACT, OPERATIONS, ProcSourceError


# --------------------------------------------------------------------------- #
# helpers
# --------------------------------------------------------------------------- #

def proc_tree(root, entries):
    """A fake `/proc`: {pid: {"comm":…, "cmdline":[…], "stat":…, "environ":{…}}}."""
    for pid, spec in entries.items():
        d = root / str(pid)
        d.mkdir()
        if "comm" in spec:
            (d / "comm").write_text(spec["comm"] + "\n")
        if "cmdline" in spec:
            (d / "cmdline").write_bytes(b"\0".join(a.encode() for a in spec["cmdline"]) + b"\0")
        if "stat" in spec:
            (d / "stat").write_text(spec["stat"])
        if "environ" in spec:
            blob = b"\0".join(f"{k}={v}".encode() for k, v in spec["environ"].items())
            (d / "environ").write_bytes(blob + b"\0")
    return str(root)


class FakeRun:
    """Stands in for `subprocess.run`, keyed by a substring of the argv."""

    def __init__(self, answers):
        self.answers = answers
        self.calls = []

    def __call__(self, argv, **kwargs):
        self.calls.append(list(argv))
        for key, (rc, out, err) in self.answers.items():
            if key in " ".join(argv):
                return subprocess.CompletedProcess(argv, rc, out, err)
        return subprocess.CompletedProcess(argv, 1, "", "")


# --------------------------------------------------------------------------- #
# the contract
# --------------------------------------------------------------------------- #

def test_both_backends_provide_every_operation_in_the_contract():
    """A fact the fleet needs everywhere belongs in the contract, not on whichever
    backend happened to need it first. Checked as a set so that adding one to a
    single backend fails here rather than on the platform that lacks it."""
    for backend in (_linux, _darwin):
        missing = [op for op in CONTRACT if not callable(getattr(backend, op, None))]
        assert missing == [], f"{backend.__name__} is missing {missing}"


def test_an_operation_outside_the_contract_is_refused_by_name():
    """Not a silent None. A source that answers a question it does not implement
    reads as a measurement, and the caller has no way to tell."""
    with pytest.raises(AttributeError) as caught:
        procsource.number_of_open_files            # noqa: B018 — attribute access is the test
    message = str(caught.value)
    assert "number_of_open_files" in message
    assert procsource.BACKEND in message
    assert "live_pids" in message                  # the contract is named, not just refused


def test_an_unknown_backend_name_is_refused_and_lists_the_real_ones():
    with pytest.raises(ProcSourceError) as caught:
        procsource.backend("plan9")
    assert "darwin" in str(caught.value) and "linux" in str(caught.value)


def test_the_active_backend_is_reportable():
    assert procsource.BACKEND in ("linux", "darwin")
    assert procsource.backend(None) is procsource._BACKENDS[procsource.BACKEND]


# --------------------------------------------------------------------------- #
# dispatch
# --------------------------------------------------------------------------- #

def test_replacing_a_backend_function_is_visible_through_the_dispatcher(monkeypatch):
    """The failure mode this package was shaped around.

    Binding `live_pids = _backend.live_pids` at import would freeze the name to
    the object the backend held then, so a replacement on the backend module
    would change what the backend's own internals see and NOT what reaches
    callers — two halves of one call chain running different code. Twelve tests
    in the preceding platform split failed exactly that way.
    """
    # Called BEFORE the replacement as well as after, and that ordering is the
    # part with teeth. A mutation that froze the lookup lazily — cache on first
    # use — SURVIVED an earlier version of this test, because the test was the
    # first caller and the cache was filled with the replacement itself. The test
    # then reported access-time resolution while a frozen implementation passed.
    procsource.live_pids("anything", root="/proc")

    monkeypatch.setattr(procsource.backend(None), "live_pids", lambda name: [4242])
    assert procsource.live_pids("anything") == [4242]


def test_an_explicit_root_selects_the_linux_reader_on_any_platform(tmp_path):
    """This is how ~10 existing suites drive the readers, and it must hold on a
    Mac too — otherwise a `/proc` fixture test would silently run `ps`."""
    root = proc_tree(tmp_path, {7: {"comm": "claude"}, 8: {"comm": "zsh"}})
    assert procsource.live_pids("claude", root=root) == [7]


def test_a_backend_can_be_named_on_the_other_platform(monkeypatch):
    monkeypatch.setattr(_darwin, "live_pids", lambda name: [1])
    monkeypatch.setattr(_linux, "live_pids", lambda name, root="/proc": [2])
    assert procsource.live_pids("x", using="darwin") == [1]
    assert procsource.live_pids("x", using="linux") == [2]


def test_the_literal_proc_root_means_dispatch_not_the_linux_backend(monkeypatch):
    """Every caller carries `proc_root="/proc"` as a DEFAULT and cannot tell a
    default from a choice, so the literal string has to mean "dispatch". On Linux
    that resolves to the backend it names anyway; on macOS it is the difference
    between reading and being blind."""
    monkeypatch.setattr(procsource.backend(None), "live_pids", lambda *a, **k: ["dispatched"])
    assert procsource.live_pids("x", root="/proc") == ["dispatched"]


# --------------------------------------------------------------------------- #
# the None / empty split
# --------------------------------------------------------------------------- #

def test_an_unreadable_root_is_none_and_an_empty_one_is_empty(tmp_path):
    """The whole reason the package states a sentinel. A listing may honestly show
    nothing; the resume guard must never be told "nothing" by a reader that could
    not look, because there an empty set means go ahead."""
    (tmp_path / "empty").mkdir()
    assert procsource.live_pids("claude", root=str(tmp_path / "empty")) == []
    assert procsource.live_pids("claude", root=str(tmp_path / "absent")) is None


def test_every_per_pid_fact_is_none_when_it_cannot_be_read(tmp_path):
    root = proc_tree(tmp_path, {9: {}})           # a pid directory with no files in it
    assert procsource.cwd(9, root=root) is None
    assert procsource.argv(9, root=root) is None
    assert procsource.ppid(9, root=root) is None
    assert procsource.comm(9, root=root) is None
    assert procsource.env_value(9, "ANY", root=root) is None


def test_a_read_table_failure_is_not_an_empty_machine(tmp_path):
    read = procsource.read_table(root=str(tmp_path / "absent"))
    assert read.failed is True
    assert read.rows == {}
    ok = procsource.read_table(root=proc_tree(tmp_path, {3: {"comm": "claude"}}))
    assert ok.failed is False and 3 in ok.rows


def test_a_batch_reports_an_unreadable_pid_individually(tmp_path):
    """A pid that cannot be answered for does not discard the batch — the reason
    is the same on both platforms, and on macOS it is the ordinary case."""
    root = proc_tree(tmp_path, {4: {"comm": "claude"}})
    (tmp_path / "4" / "cwd").symlink_to(tmp_path)
    got = procsource.cwds([4, 5], root=root)
    assert got[4] == str(tmp_path)
    assert got[5] is None
    assert set(got) == {4, 5}                      # every requested pid is a key


# --------------------------------------------------------------------------- #
# the Linux backend
# --------------------------------------------------------------------------- #

def test_identity_is_not_a_substring(tmp_path):
    """31 false positives on the machine the original reader was measured on, all
    of them shells whose path happened to contain the word."""
    root = proc_tree(tmp_path, {
        10: {"comm": "claude"},
        11: {"comm": "zsh", "cmdline": ["/bin/zsh", "-c", "source ~/.claude/snapshot.sh"]},
    })
    assert procsource.live_pids("claude", root=root) == [10]


def test_ppid_survives_a_comm_containing_spaces_and_parentheses(tmp_path):
    """Field 2 of `stat` is a comm in parentheses, and a comm may contain both —
    so the parse starts after the LAST `)`, never at a whitespace split."""
    root = proc_tree(tmp_path, {
        12: {"stat": "12 (weird ) name) S 42 12 12 0 -1 4194304 0 0"},
    })
    assert procsource.ppid(12, root=root) == 42


def test_argv_is_exact_on_linux(tmp_path):
    root = proc_tree(tmp_path, {13: {"cmdline": ["node", "/x/sac.mjs", "wait", "a b"]}})
    assert procsource.argv(13, root=root) == ["node", "/x/sac.mjs", "wait", "a b"]


def test_env_value_reads_one_variable_and_reports_an_absent_one_as_unknown(tmp_path):
    root = proc_tree(tmp_path, {14: {"environ": {"A": "1", "SESSION": "abc"}}})
    assert procsource.env_value(14, "SESSION", root=root) == "abc"
    assert procsource.env_value(14, "MISSING", root=root) is None


# --------------------------------------------------------------------------- #
# the Darwin backend, driven from recorded output
# --------------------------------------------------------------------------- #

PS_IDENTITY = (
    "    1     0 /sbin/launchd\n"
    "   94     1 /usr/libexec/logd\n"
    "37343 37323 claude\n"
    "33393  5741 /usr/local/bin/claude\n"
    "46495 46490 /bin/zsh\n"
    "  700     1 /System/Library/CoreServices/Software Update.app/Contents/x/suhelperd\n"
)

PS_ARGS = (
    "37343 claude --dangerously-skip-permissions\n"
    "46495 /bin/zsh -c source /Users/x/.claude/shell-snapshots/claude-snap.sh\n"
    "40000 claude -p 'one shot'\n"
)


@pytest.fixture
def darwin_ps(monkeypatch):
    run = FakeRun({
        "pid=,ppid=,comm=": (0, PS_IDENTITY, ""),
        "pid=,args=": (0, PS_ARGS, ""),
    })
    monkeypatch.setattr(_darwin.subprocess, "run", run)
    return run


def test_darwin_matches_identity_by_basename_and_ignores_command_lines(darwin_ps):
    """`ps -o comm=` prints a bare name for some processes and a full path for
    others, so the basename is compared — and the zsh whose command line contains
    the word is not an agent."""
    assert _darwin.live_pids("claude") == [33393, 37343]


def test_darwin_keeps_a_comm_that_contains_spaces_whole(darwin_ps):
    """Measured: 19 of 632 processes on one machine had a space in `comm`.
    Splitting the whole line on whitespace would cut those in the middle."""
    table = _darwin.read_table()
    assert table.rows[700].comm.endswith("Software Update.app/Contents/x/suhelperd")
    assert table.rows[700].ppid == 1


def test_darwin_never_asks_ps_for_comm_and_args_in_one_command(darwin_ps):
    """`ps` truncates `comm` to a column width when another column follows it —
    measured, pid 94 reported `/usr/libexec/log` beside `args=/usr/libexec/logd`.
    A truncated identity does not fail, it silently stops matching."""
    _darwin.read_table()
    _darwin.argvs()
    for call in darwin_ps.calls:
        fmt = call[-1]
        assert not ("comm=" in fmt and "args=" in fmt), call


def test_darwin_argv_keeps_a_one_shot_flag(darwin_ps):
    """The one consumer of argv that must survive whitespace splitting."""
    assert "-p" in _darwin.argvs()[40000]


def test_darwin_reads_the_whole_table_once_per_pass_and_again_on_the_next(darwin_ps):
    _darwin.live_pids("claude")
    first = len([c for c in darwin_ps.calls if "-A" in c])
    assert first == 1
    _darwin.live_pids("claude")
    assert len([c for c in darwin_ps.calls if "-A" in c]) == 2   # no cross-call cache


def test_darwin_cwds_uses_one_lsof_for_the_whole_batch(monkeypatch):
    run = FakeRun({"lsof": (0, "p1\nfcwd\nn/a\np2\nfcwd\nn/b\n", "")})
    monkeypatch.setattr(_darwin.subprocess, "run", run)
    assert _darwin.cwds([1, 2]) == {1: "/a", 2: "/b"}
    assert len([c for c in run.calls if c[0].endswith("lsof")]) == 1
    assert "1,2" in " ".join(run.calls[0])


def test_darwin_keeps_lsof_output_when_a_dead_pid_sets_the_exit_code(monkeypatch):
    """The measured trap. `lsof -a -d cwd -Fpn -p 37343,999999` prints 37343's
    working directory AND exits 1, so the ordinary `returncode != 0 -> failure`
    rule would report the machine unmeasurable every time one process exited
    mid-pass — which during a discovery pass is ordinary, not exceptional."""
    run = FakeRun({"lsof": (1, "p37343\nfcwd\nn/Users/x/code\n", "")})
    monkeypatch.setattr(_darwin.subprocess, "run", run)
    got = _darwin.cwds([37343, 999999])
    assert got[37343] == "/Users/x/code"
    assert got[999999] is None


def test_darwin_reports_unknown_cwd_when_lsof_cannot_be_run_at_all(monkeypatch):
    def boom(*a, **k):
        raise OSError("no lsof")
    monkeypatch.setattr(_darwin.subprocess, "run", boom)
    got = _darwin.cwds([1, 2])
    assert got == {1: None, 2: None}               # unknown, and both pids still keys


def test_darwin_env_value_is_none_rather_than_empty_when_unreadable(monkeypatch):
    monkeypatch.setattr(_darwin.subprocess, "run", FakeRun({"-E": (1, "", "ps: bad")}))
    assert _darwin.env_value(1, "CLAUDE_CODE_SESSION_ID") is None


def test_darwin_env_value_extracts_one_assignment(monkeypatch):
    out = "claude --flag SHELL=/bin/zsh CLAUDE_CODE_SESSION_ID=abc-123 HOME=/Users/x"
    monkeypatch.setattr(_darwin.subprocess, "run", FakeRun({"-E": (0, out, "")}))
    assert _darwin.env_value(1, "CLAUDE_CODE_SESSION_ID") == "abc-123"


def test_darwin_a_dead_pid_is_answered_not_reported_as_a_failure(monkeypatch, caplog):
    """`ps -p <dead pid>` exits non-zero with nothing on either stream. That is an
    answer, and logging it as a failure would put a WARNING in the log every time
    the fleet asked about a pid that had finished."""
    monkeypatch.setattr(_darwin.subprocess, "run", FakeRun({"-p": (1, "", "")}))
    with caplog.at_level("WARNING"):
        assert _darwin.comm(99999) is None
    assert caplog.records == []


def test_darwin_a_real_ps_failure_is_a_failure(monkeypatch, caplog):
    monkeypatch.setattr(
        _darwin.subprocess, "run", FakeRun({"-A": (1, "", "ps: illegal option -- Z")}),
    )
    with caplog.at_level("WARNING"):
        assert _darwin.live_pids("claude") is None
    assert any("ps exited" in r.message for r in caplog.records)


def test_darwin_a_timeout_answers_unknown_and_warns(monkeypatch, caplog):
    def slow(*a, **k):
        raise subprocess.TimeoutExpired(cmd="ps", timeout=1)
    monkeypatch.setattr(_darwin.subprocess, "run", slow)
    with caplog.at_level("WARNING"):
        assert _darwin.live_pids("claude") is None
    assert any("could not be run" in r.message for r in caplog.records)


def test_darwin_failure_logs_carry_no_path_or_command_line(monkeypatch, caplog):
    """The confidentiality boundary is persistence, and a log is persistence. What
    these commands print is working directories and command lines, which carry
    consumer paths."""
    secret = "/Users/x/code/some-consumer-project"
    monkeypatch.setattr(
        _darwin.subprocess, "run",
        FakeRun({"-A": (1, f"1 1 {secret}\n", f"ps: {secret}: bad")}),
    )
    with caplog.at_level("DEBUG"):
        _darwin.live_pids("claude")
    assert all(secret not in r.getMessage() for r in caplog.records)


# --------------------------------------------------------------------------- #
# the environment the readers actually run in
# --------------------------------------------------------------------------- #

def test_the_readers_resolve_their_binaries_by_absolute_path(monkeypatch):
    """Found by opening the running dashboard, not by any test here.

    A launchd service does not inherit a login shell's `PATH`, and the
    dashboard's lacks `/usr/sbin`. Called as a bare name, `lsof` raised
    `FileNotFoundError` in the service, every working directory came back
    unknown, and `discover_agents()` — which skips a pid whose cwd it cannot
    read — returned an EMPTY FLEET. On the screen that is indistinguishable from
    the `/proc` blindness this package was written to remove.

    It passed every unit test, because tests replace `subprocess.run`, and it
    passed every command-line check, because an interactive shell has the
    directory on its `PATH`.
    """
    monkeypatch.setenv("PATH", "/nonexistent")
    assert _darwin._binary("lsof").startswith("/")
    assert _darwin._binary("ps").startswith("/")


def test_a_binary_that_exists_nowhere_is_still_attempted_by_name(monkeypatch):
    """The resolver degrades to the bare name rather than raising. A missing
    binary is already handled one layer up, where it becomes "unknown" for that
    fact — and losing that path would turn a degraded field into an exception on
    the fleet's polling route."""
    monkeypatch.setenv("PATH", "/nonexistent")
    monkeypatch.setattr(_darwin, "FALLBACK_PATHS", {})
    assert _darwin._binary("lsof") == "lsof"


# --------------------------------------------------------------------------- #
# the property, held as a test rather than as a rule somebody remembers
# --------------------------------------------------------------------------- #

FLEET_READERS = ("discovery.py", "instruct.py", "purpose.py", "awaiting.py", "roster.py")


def _fleet_source(name):
    from pathlib import Path
    return (Path(__file__).resolve().parents[2] / "lib" / "set_orch" / "fleet" / name).read_text()


def test_no_reader_branches_on_the_platform_to_read_a_process_fact():
    """The knowledge of which platform this is belongs in ONE place.

    Written as a test because the alternative is a rule in a document: the
    previous change left a single `sys.platform == "darwin"` branch inside one
    function, which was reasonable when there was no package to put it in and
    became the thing a reader copies once there was.
    """
    offenders = [n for n in FLEET_READERS if "sys.platform" in _code_only(_fleet_source(n))]
    assert offenders == [], f"{offenders} decide a process read by platform"


def _code_only(source: str) -> str:
    """The source with DOCSTRINGS and comments removed — and nothing else.

    Two mistakes were made here in a row, and both are worth the space.

    First the check matched raw text, and flagged `awaiting.py` for a docstring
    that QUOTES the `/proc` expression it no longer uses. Prose read as fact.

    Then the repair dropped every STRING token, which made the check blind to
    the thing it exists to find. Measured against three real violation shapes:
    `f"/proc/{pid}"` was still caught (f-strings tokenize separately), but
    `"/proc/" + str(pid)` and `os.path.join("/proc", str(pid))` both PASSED. A
    guard widened until it reports nothing is worse than no guard, because it
    also reports success. So only docstrings go — they are the strings that
    describe the code rather than run in it.
    """
    import ast

    doc_lines = set()
    tree = ast.parse(source)
    for node in ast.walk(tree):
        body = getattr(node, "body", None)
        if not isinstance(node, (ast.Module, ast.ClassDef,
                                 ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        if body and isinstance(body[0], ast.Expr) and isinstance(body[0].value, ast.Constant) \
                and isinstance(body[0].value.value, str):
            doc_lines.update(range(body[0].lineno, (body[0].end_lineno or body[0].lineno) + 1))

    # The comment strip is deliberately crude — it cuts at the first `#`, which
    # can also cut a string. That direction is safe here: it can only remove text
    # AFTER a `#`, and a `/proc/` path written before one is still visible.
    return "\n".join(
        line.split("#", 1)[0]
        for i, line in enumerate(source.splitlines(), 1)
        if i not in doc_lines
    )


def test_no_reader_builds_a_proc_path_outside_the_source_package():
    """`proc_root` DEFAULTS are allowed — they are the dispatch sentinel. What is
    not allowed is joining a path under one, which is a `/proc` read by hand.

    Note what this can and cannot see: with string literals stripped, a `/proc`
    path built by concatenating variables would slip through. It catches the
    shape that has actually appeared here twice, and says so rather than implying
    more."""
    import re
    # The ONE allowed spelling: `/proc` as a default or compared as a sentinel.
    allowed = re.compile(r"""[=!]=?\s*["']/proc["']""")
    offenders = []
    for name in FLEET_READERS:
        code = allowed.sub("", _code_only(_fleet_source(name)))
        if "/proc" in code:
            offenders.append(name)
    assert offenders == [], f"{offenders} build a /proc path directly"


def test_darwin_reads_the_parent_pid_of_one_process(monkeypatch):
    """Asked per pid rather than from the table: the ancestry walk climbs through
    processes the table's identity read has no reason to have kept."""
    monkeypatch.setattr(
        _darwin.subprocess, "run", FakeRun({"pid=,ppid=": (0, "37343 37323\n", "")}),
    )
    assert _darwin.ppid(37343) == 37323


def test_darwin_argv_equals_the_real_argument_vector_when_it_has_no_spaces(monkeypatch):
    """The stated limitation, stated from the other side. `ps` joins arguments
    with spaces, so an argument containing one cannot be recovered here — but a
    vector without them round-trips exactly, which is what every current consumer
    relies on."""
    real = ["node", "/opt/sac/sac.mjs", "wait", "room-a", "room-b"]
    monkeypatch.setattr(
        _darwin.subprocess, "run",
        FakeRun({"pid=,args=": (0, "4242 " + " ".join(real) + "\n", "")}),
    )
    assert _darwin.argv(4242) == real
