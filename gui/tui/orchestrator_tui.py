#!/usr/bin/env python3
# NOTE: Requires python with textual package installed (pip install textual)
"""Orchestrator TUI — live terminal dashboard for wt-orchestrate."""

import json
import os
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path

try:
    from textual.app import App, ComposeResult
except ImportError:
    print("Error: 'textual' package is required. Install it: pip install textual", file=sys.stderr)
    sys.exit(1)
from textual.binding import Binding
from textual.containers import Vertical
from textual.widgets import DataTable, Footer, Header, RichLog, Static


# ─── Status colors and icons ─────────────────────────────────────────

STATUS_DISPLAY = {
    "running":        ("green",         "●"),
    "verifying":      ("cyan",          "◎"),
    "done":           ("blue",          "✓"),
    "merged":         ("bright_green",  "✓✓"),
    "pending":        ("dim",           "○"),
    "dispatched":     ("yellow",        "▶"),
    "failed":         ("red bold",      "✗"),
    "verify-failed":  ("red",           "⚠"),
    "stalled":        ("magenta",       "⚠"),
    "merge-blocked":  ("yellow",        "⛔"),
    "checkpoint":     ("yellow bold",   "⏸"),
    "paused":         ("dim",           "⏸"),
    "stopped":        ("dim",           "■"),
    "time_limit":     ("yellow",        "⏱"),
}

GATE_PASS = "[green]✓[/]"
GATE_FAIL = "[red bold]✗[/]"
GATE_SKIP = "[dim]⊘[/]"
GATE_NONE = "[dim]-[/]"


# ─── Helpers ──────────────────────────────────────────────────────────

def format_tokens(n):
    """Format token count with K/M suffix."""
    if n is None or n == 0:
        return "-"
    if n >= 1_000_000:
        return f"{n / 1_000_000:.1f}M"
    if n >= 1_000:
        return f"{n / 1_000:.0f}K"
    return str(n)


def format_duration(seconds):
    """Format seconds as human-readable duration."""
    if seconds is None or seconds <= 0:
        return "-"
    seconds = int(seconds)
    if seconds < 60:
        return f"{seconds}s"
    if seconds < 3600:
        return f"{seconds // 60}m"
    h = seconds // 3600
    m = (seconds % 3600) // 60
    if m == 0:
        return f"{h}h"
    return f"{h}h{m:02d}m"


def gate_str(result):
    """Convert a gate result to a display string."""
    if result == "pass":
        return GATE_PASS
    if result == "fail":
        return GATE_FAIL
    if result == "skipped":
        return GATE_SKIP
    return GATE_NONE


def format_gates(change):
    """Format gate results: pre-merge T/B/R/V, post-merge +S (smoke runs post-merge only)."""
    test = change.get("test_result")
    build = change.get("build_result")
    smoke = change.get("smoke_result")
    review = change.get("review_result")
    # Verify is implied by status
    status = change.get("status", "")
    verify = "pass" if status in ("done", "merged") else (
        "fail" if status == "verify-failed" else None
    )

    parts = []
    parts.append(f"T{gate_str(test)}")
    parts.append(f"B{gate_str(build)}")
    parts.append(f"R{gate_str(review)}")
    parts.append(f"V{gate_str(verify)}")
    # Smoke runs post-merge — only show for merged/done changes
    if smoke is not None:
        parts.append(f"S{gate_str(smoke)}")
    return " ".join(parts)


# ─── State reader ─────────────────────────────────────────────────────

class StateReader:
    """Reads orchestration state and log files."""

    def __init__(self, state_path, log_path):
        self.state_path = Path(state_path)
        self.log_path = Path(log_path)
        self._log_offset = 0
        self._first_log_read = True

    def read_state(self):
        """Load orchestration-state.json. Returns dict or None."""
        try:
            with open(self.state_path) as f:
                return json.load(f)
        except (FileNotFoundError, json.JSONDecodeError, OSError):
            return None

    def read_loop_state(self, worktree_path):
        """Read loop-state.json for iteration progress. Returns 'iter/max' or '-'."""
        if not worktree_path:
            return "-"
        loop_file = Path(worktree_path) / ".claude" / "loop-state.json"
        try:
            with open(loop_file) as f:
                ls = json.load(f)
            iteration = ls.get("iteration", 0)
            max_iter = ls.get("max_iterations", 0)
            if max_iter > 0:
                return f"{iteration}/{max_iter}"
            if iteration > 0:
                return str(iteration)
            return "-"
        except (FileNotFoundError, json.JSONDecodeError, OSError):
            return "-"

    def read_log(self):
        """Read new log lines since last call. Returns list of strings."""
        if not self.log_path.exists():
            return None  # signal "no log file"

        try:
            file_size = self.log_path.stat().st_size
        except OSError:
            return None

        # On first read, get last 200 lines
        if self._first_log_read:
            self._first_log_read = False
            try:
                with open(self.log_path) as f:
                    lines = f.readlines()
                self._log_offset = file_size
                return lines[-200:]
            except OSError:
                return None

        # File was truncated (log rotation)
        if file_size < self._log_offset:
            self._log_offset = 0

        if file_size <= self._log_offset:
            return []

        try:
            with open(self.log_path, "rb") as f:
                f.seek(self._log_offset)
                new_bytes = f.read()
            self._log_offset = file_size
            return new_bytes.decode("utf-8", errors="replace").splitlines(keepends=True)
        except OSError:
            return []

    def is_stale(self):
        """Check if state file is stale (>120s since last modification)."""
        try:
            mtime = self.state_path.stat().st_mtime
            return (datetime.now().timestamp() - mtime) > 120
        except OSError:
            return False


# ─── App ──────────────────────────────────────────────────────────────

CSS = """
#header-bar {
    height: 3;
    padding: 0 1;
    background: $surface;
    color: $text;
}

#change-table {
    height: 1fr;
    min-height: 5;
}

#log-panel {
    height: 12;
    border-top: solid $primary;
}

#log-panel.fullscreen {
    height: 1fr;
}

#change-table.hidden {
    display: none;
}

#header-bar.hidden {
    display: none;
}
"""


class OrchestratorTUI(App):
    """Live terminal dashboard for wt-orchestrate."""

    TITLE = "wt-orchestrate"
    CSS = CSS

    BINDINGS = [
        Binding("q", "quit", "Quit"),
        Binding("r", "refresh", "Refresh"),
        Binding("a", "approve", "Approve"),
        Binding("l", "toggle_log", "Toggle Log"),
    ]

    def __init__(self, state_path, log_path):
        super().__init__()
        self.reader = StateReader(state_path, log_path)
        self._log_fullscreen = False
        self._current_state = None

    def compose(self) -> ComposeResult:
        yield Header()
        with Vertical():
            yield Static("Loading...", id="header-bar")
            yield DataTable(id="change-table")
            yield RichLog(id="log-panel", highlight=True, markup=True)
        yield Footer()

    def on_mount(self) -> None:
        # Set up table columns
        table = self.query_one("#change-table", DataTable)
        table.add_columns("Name", "Status", "Iter", "Tokens", "Gates")
        table.cursor_type = "row"

        # Initial data load
        self._refresh_data()

        # Set up auto-refresh timer (3s)
        self.set_interval(3.0, self._refresh_data)

    def _refresh_data(self) -> None:
        """Re-read state and log, update display."""
        state = self.reader.read_state()
        self._current_state = state
        if state:
            self._update_header(state)
            self._update_table(state)
            self._update_footer(state)

        new_lines = self.reader.read_log()
        self._update_log(new_lines)

    def _update_footer(self, state) -> None:
        """Update footer to show/hide approve based on checkpoint status."""
        is_checkpoint = state.get("status") == "checkpoint" if state else False
        # Rebuild the subtitle to hint approval availability
        if is_checkpoint:
            self.sub_title = "CHECKPOINT — press [a] to approve"
        else:
            self.sub_title = ""

    def _update_header(self, state) -> None:
        """Update the header bar with orchestration status."""
        header = self.query_one("#header-bar", Static)

        orch_status = state.get("status", "unknown")
        color, icon = STATUS_DISPLAY.get(orch_status, ("white", "?"))
        plan_version = state.get("plan_version", "?")
        replan_cycle = state.get("replan_cycle", 0)

        # Progress counts
        changes = state.get("changes", [])
        total = len(changes)
        done = sum(1 for c in changes if c.get("status") in ("done", "merged"))

        # Cumulative tokens: current cycle + previous cycles
        current_tokens = sum(c.get("tokens_used", 0) or 0 for c in changes)
        prev_tokens = state.get("prev_total_tokens", 0) or 0
        # During replan transition, current cycle tokens are 0 briefly — show prev total
        if current_tokens == 0 and prev_tokens > 0:
            total_tokens = prev_tokens
        else:
            total_tokens = current_tokens + prev_tokens

        # Time tracking
        active_secs = state.get("active_seconds", 0) or 0
        time_limit = state.get("time_limit_secs", 0) or 0

        # Build status line
        status_text = f"[{color}]{icon} {orch_status.upper()}[/]"

        # Stale detection
        if orch_status == "running" and self.reader.is_stale():
            status_text += " [red](stale — process may have crashed)[/]"

        # Plan version with replan
        plan_text = f"Plan v{plan_version}"
        if replan_cycle and replan_cycle > 0:
            plan_text += f" (replan #{replan_cycle})"

        # Time info
        time_text = f"Active: {format_duration(active_secs)}"
        if time_limit > 0:
            remaining = time_limit - active_secs
            if remaining > 0:
                time_text += f" / {format_duration(time_limit)} limit ({format_duration(remaining)} rem)"
            else:
                time_text += f" / {format_duration(time_limit)} limit [red](exceeded)[/]"

        # Compose header
        line1 = f"  {status_text}  {plan_text}  {done}/{total} done  Tokens: {format_tokens(total_tokens)}"
        line2 = f"  {time_text}"

        # Extra note for time_limit status
        if orch_status == "time_limit":
            line2 += "  [yellow]Run 'wt-orchestrate start' to continue[/]"

        header.update(f"{line1}\n{line2}")

    def _update_table(self, state) -> None:
        """Repopulate the change table, preserving cursor position."""
        table = self.query_one("#change-table", DataTable)

        # Preserve cursor row before clearing
        try:
            saved_row = table.cursor_coordinate.row
        except Exception:
            saved_row = 0

        table.clear()

        for change in state.get("changes", []):
            name = change.get("name", "?")
            status = change.get("status", "?")

            # Show depends_on for blocked/pending changes
            deps = change.get("depends_on", [])
            if deps and status in ("pending", "dispatched"):
                dep_text = ", ".join(d[:12] for d in deps[:2])
                name_display = f"{name[:22]} [dim](→{dep_text})[/]"
            else:
                name_display = name
            if len(name) > 25:
                name = name[:24] + "…"
            color, icon = STATUS_DISPLAY.get(status, ("white", "?"))
            status_cell = f"[{color}]{icon} {status}[/]"

            # Iteration from loop-state
            wt_path = change.get("worktree_path")
            iteration = self.reader.read_loop_state(wt_path) if status == "running" else "-"

            tokens = format_tokens(change.get("tokens_used"))

            # Gates (only show for non-pending)
            if status in ("pending", "dispatched"):
                gates = "[dim]-[/]"
            else:
                gates = format_gates(change)

            table.add_row(name_display, status_cell, iteration, tokens, gates)

        # Restore cursor position (clamp to valid range)
        if table.row_count > 0:
            from textual.coordinate import Coordinate
            restored_row = min(saved_row, table.row_count - 1)
            table.cursor_coordinate = Coordinate(restored_row, 0)

    def _update_log(self, new_lines) -> None:
        """Append new log lines to the RichLog widget."""
        log_widget = self.query_one("#log-panel", RichLog)

        if new_lines is None:
            # No log file
            if log_widget.line_count == 0:
                log_widget.write("[dim]No log file yet[/]")
            return

        for line in new_lines:
            line = line.rstrip()
            if not line:
                continue
            # Color by log level and special markers
            if "========== REPLAN CYCLE" in line:
                log_widget.write(f"[bold cyan]{line}[/]")
            elif "[ERROR]" in line:
                log_widget.write(f"[red bold]{line}[/]")
            elif "[WARN]" in line:
                log_widget.write(f"[yellow]{line}[/]")
            else:
                log_widget.write(line)

    # ─── Actions ──────────────────────────────────────────────────────

    def action_refresh(self) -> None:
        """Force immediate refresh."""
        self._refresh_data()
        self.notify("Refreshed", timeout=1)

    def action_approve(self) -> None:
        """Approve a checkpoint."""
        state = self._current_state
        if not state:
            self.notify("No state loaded", severity="warning", timeout=2)
            return

        if state.get("status") != "checkpoint":
            self.notify("Not at checkpoint", severity="warning", timeout=2)
            return

        try:
            # Read current state
            with open(self.reader.state_path) as f:
                data = json.load(f)

            # Mark latest checkpoint approved
            checkpoints = data.get("checkpoints", [])
            if checkpoints:
                checkpoints[-1]["approved"] = True
                checkpoints[-1]["approved_at"] = datetime.now(timezone.utc).isoformat()

            # Atomic write: temp file + rename
            state_dir = self.reader.state_path.parent
            fd, tmp_path = tempfile.mkstemp(dir=state_dir, suffix=".tmp")
            try:
                with os.fdopen(fd, "w") as f:
                    json.dump(data, f, indent=2)
                os.rename(tmp_path, self.reader.state_path)
            except Exception:
                os.unlink(tmp_path)
                raise

            self.notify("Checkpoint approved!", severity="information", timeout=3)
            self._refresh_data()

        except Exception as e:
            self.notify(f"Approve failed: {e}", severity="error", timeout=5)

    def action_toggle_log(self) -> None:
        """Toggle between split and full-screen log view."""
        self._log_fullscreen = not self._log_fullscreen

        table = self.query_one("#change-table", DataTable)
        header_bar = self.query_one("#header-bar", Static)
        log_panel = self.query_one("#log-panel", RichLog)

        if self._log_fullscreen:
            table.add_class("hidden")
            header_bar.add_class("hidden")
            log_panel.add_class("fullscreen")
        else:
            table.remove_class("hidden")
            header_bar.remove_class("hidden")
            log_panel.remove_class("fullscreen")


# ─── Entry point ──────────────────────────────────────────────────────

def main():
    if len(sys.argv) < 3:
        print("Usage: orchestrator_tui.py <state-file> <log-file>", file=sys.stderr)
        sys.exit(1)

    state_file = sys.argv[1]
    log_file = sys.argv[2]

    if not Path(state_file).exists():
        print(f"No orchestration state found at: {state_file}", file=sys.stderr)
        print("Run 'wt-orchestrate plan' first.", file=sys.stderr)
        sys.exit(1)

    app = OrchestratorTUI(state_file, log_file)
    app.run()


if __name__ == "__main__":
    main()
