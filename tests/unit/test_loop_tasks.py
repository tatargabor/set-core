"""Tests for wt_orch.loop_tasks — discovery, completion, manual tasks, done criteria."""

import json
import os
import sys
import tempfile
import shutil

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "lib"))

from wt_orch.loop_tasks import (
    TaskStatus,
    ManualTask,
    find_tasks_file,
    check_completion,
    find_manual_tasks,
    is_done,
    generate_fallback_tasks,
    get_new_commits,
)


@pytest.fixture
def tmp_dir():
    d = tempfile.mkdtemp()
    yield d
    shutil.rmtree(d, ignore_errors=True)


@pytest.fixture
def wt(tmp_dir):
    wt = os.path.join(tmp_dir, "worktree")
    os.makedirs(os.path.join(wt, ".claude"))
    return wt


# ─── find_tasks_file ──────────────────────────────────────────


class TestFindTasksFile:
    def test_root_tasks(self, wt):
        with open(os.path.join(wt, "tasks.md"), "w") as f:
            f.write("# Tasks\n")
        assert find_tasks_file(wt) == os.path.join(wt, "tasks.md")

    def test_nested_tasks(self, wt):
        nested = os.path.join(wt, "openspec", "changes", "my-change")
        os.makedirs(nested)
        with open(os.path.join(nested, "tasks.md"), "w") as f:
            f.write("# Tasks\n")
        result = find_tasks_file(wt)
        assert result is not None
        assert result.endswith("tasks.md")

    def test_not_found(self, wt):
        assert find_tasks_file(wt) is None

    def test_archive_excluded(self, wt):
        archive = os.path.join(wt, "openspec", "changes", "archive", "old")
        os.makedirs(archive)
        with open(os.path.join(archive, "tasks.md"), "w") as f:
            f.write("# Tasks\n")
        assert find_tasks_file(wt) is None


# ─── check_completion ─────────────────────────────────────────


class TestCheckCompletion:
    def test_all_done(self, wt):
        tf = os.path.join(wt, "tasks.md")
        with open(tf, "w") as f:
            f.write("- [x] Task 1\n- [x] Task 2\n- [x] Task 3\n")
        status = check_completion(wt, tf)
        assert status.done == 3
        assert status.pending == 0
        assert status.percent == 100.0

    def test_mixed(self, wt):
        tf = os.path.join(wt, "tasks.md")
        with open(tf, "w") as f:
            f.write("- [x] Task 1\n- [ ] Task 2\n- [?] Task 3\n")
        status = check_completion(wt, tf)
        assert status.done == 1
        assert status.pending == 1
        assert status.manual == 1
        assert status.total == 3

    def test_empty_file(self, wt):
        tf = os.path.join(wt, "tasks.md")
        with open(tf, "w") as f:
            f.write("# Tasks\n\nNo tasks yet.\n")
        status = check_completion(wt, tf)
        assert status.total == 0

    def test_no_file(self, wt):
        status = check_completion(wt)
        assert status.total == 0

    def test_indented_tasks(self, wt):
        tf = os.path.join(wt, "tasks.md")
        with open(tf, "w") as f:
            f.write("  - [x] Done\n  - [ ] Pending\n")
        status = check_completion(wt, tf)
        assert status.done == 1
        assert status.pending == 1

    def test_percent_calculation(self, wt):
        tf = os.path.join(wt, "tasks.md")
        with open(tf, "w") as f:
            f.write("- [x] A\n- [ ] B\n- [ ] C\n- [ ] D\n")
        status = check_completion(wt, tf)
        assert status.percent == 25.0


# ─── find_manual_tasks ────────────────────────────────────────


class TestFindManualTasks:
    def test_confirm_task(self, wt):
        tf = os.path.join(wt, "tasks.md")
        with open(tf, "w") as f:
            f.write("- [?] 3.1 Set up API key [confirm]\n")
        tasks = find_manual_tasks(wt, tf)
        assert len(tasks) == 1
        assert tasks[0].id == "3.1"
        assert tasks[0].type == "confirm"
        assert "API key" in tasks[0].description

    def test_input_task(self, wt):
        tf = os.path.join(wt, "tasks.md")
        with open(tf, "w") as f:
            f.write("- [?] 2.5 Enter database URL [input:DATABASE_URL]\n")
        tasks = find_manual_tasks(wt, tf)
        assert len(tasks) == 1
        assert tasks[0].type == "input"
        assert tasks[0].input_key == "DATABASE_URL"

    def test_no_manual_tasks(self, wt):
        tf = os.path.join(wt, "tasks.md")
        with open(tf, "w") as f:
            f.write("- [x] Done\n- [ ] Pending\n")
        tasks = find_manual_tasks(wt, tf)
        assert tasks == []

    def test_multiple_manual_tasks(self, wt):
        tf = os.path.join(wt, "tasks.md")
        with open(tf, "w") as f:
            f.write(
                "- [?] 1.1 First [confirm]\n"
                "- [x] Done task\n"
                "- [?] 2.2 Second [input:KEY]\n"
            )
        tasks = find_manual_tasks(wt, tf)
        assert len(tasks) == 2

    def test_no_file(self, wt):
        assert find_manual_tasks(wt) == []


# ─── is_done ──────────────────────────────────────────────────


class TestIsDone:
    def test_tasks_done(self, wt):
        tf = os.path.join(wt, "tasks.md")
        with open(tf, "w") as f:
            f.write("- [x] A\n- [x] B\n")
        assert is_done(wt, "tasks") is True

    def test_tasks_not_done(self, wt):
        tf = os.path.join(wt, "tasks.md")
        with open(tf, "w") as f:
            f.write("- [x] A\n- [ ] B\n")
        assert is_done(wt, "tasks") is False

    def test_tasks_empty(self, wt):
        """No tasks file → not done (total=0)."""
        assert is_done(wt, "tasks") is False

    def test_manual_done(self, wt):
        state_file = os.path.join(wt, ".claude", "loop-state.json")
        with open(state_file, "w") as f:
            json.dump({"manual_done": True}, f)
        assert is_done(wt, "manual") is True

    def test_manual_not_done(self, wt):
        state_file = os.path.join(wt, ".claude", "loop-state.json")
        with open(state_file, "w") as f:
            json.dump({"manual_done": False}, f)
        assert is_done(wt, "manual") is False


# ─── generate_fallback_tasks ──────────────────────────────────


class TestGenerateFallbackTasks:
    def test_creates_tasks(self, wt):
        change_dir = os.path.join(wt, "openspec", "changes", "my-change")
        os.makedirs(change_dir)
        with open(os.path.join(change_dir, "proposal.md"), "w") as f:
            f.write("# Proposal\n\nDo things.\n")
        assert generate_fallback_tasks(wt, "my-change") is True
        assert os.path.isfile(os.path.join(change_dir, "tasks.md"))

    def test_no_overwrite(self, wt):
        change_dir = os.path.join(wt, "openspec", "changes", "my-change")
        os.makedirs(change_dir)
        with open(os.path.join(change_dir, "proposal.md"), "w") as f:
            f.write("# Proposal\n")
        with open(os.path.join(change_dir, "tasks.md"), "w") as f:
            f.write("# Existing tasks\n")
        assert generate_fallback_tasks(wt, "my-change") is True
        with open(os.path.join(change_dir, "tasks.md"), "r") as f:
            assert "Existing tasks" in f.read()

    def test_no_proposal(self, wt):
        change_dir = os.path.join(wt, "openspec", "changes", "my-change")
        os.makedirs(change_dir)
        assert generate_fallback_tasks(wt, "my-change") is False

    def test_with_design(self, wt):
        change_dir = os.path.join(wt, "openspec", "changes", "my-change")
        os.makedirs(change_dir)
        with open(os.path.join(change_dir, "proposal.md"), "w") as f:
            f.write("# Proposal\n")
        with open(os.path.join(change_dir, "design.md"), "w") as f:
            f.write("# Design\n")
        generate_fallback_tasks(wt, "my-change")
        with open(os.path.join(change_dir, "tasks.md"), "r") as f:
            assert "proposal.md and design.md" in f.read()


# ─── TaskStatus dataclass ─────────────────────────────────────


class TestTaskStatus:
    def test_defaults(self):
        s = TaskStatus()
        assert s.total == 0
        assert s.percent == 0.0

    def test_with_values(self):
        s = TaskStatus(total=10, done=7, pending=2, manual=1, percent=70.0)
        assert s.done == 7
