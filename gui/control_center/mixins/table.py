"""
Table Mixin - Table rendering and row updates
"""

import json
import math
import os
from pathlib import Path

from PySide6.QtWidgets import QWidget, QHBoxLayout, QLabel, QPushButton, QTableWidgetItem
from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QFont

__all__ = ["TableMixin"]

# Column indices for the 6-column layout
COL_NAME = 0
COL_PID = 1
COL_STATUS = 2
COL_SKILL = 3
COL_CTX = 4
COL_EXTRA = 5
NUM_COLS = 6


# Known IDE process names (from PPID chain detection in wt-status)
_IDE_EDITOR_TYPES = {"zed", "Zed", "code", "Code", "cursor", "Cursor", "windsurf", "Windsurf"}


def _is_ide_editor_type(editor_type: str) -> bool:
    """Return True if editor_type matches a known IDE process name."""
    return bool(editor_type) and editor_type in _IDE_EDITOR_TYPES


class TableMixin:
    """Mixin for table rendering functionality"""

    def _get_agents(self, wt: dict) -> list:
        """Get agents list from worktree data, with fallback."""
        return wt.get("agents", [])

    def _agent_rows_count(self, wt: dict) -> int:
        """How many rows this worktree needs (at least 1, or one per agent)."""
        agents = self._get_agents(wt)
        return max(1, len(agents))

    def _is_worktree_active(self, wt: dict) -> bool:
        """Check if worktree is active (has agents or editor open)."""
        agents = self._get_agents(wt)
        if len(agents) > 0:
            return True
        # Editor open counts as "active" for filtering purposes
        return wt.get("editor_open", False)

    def refresh_table_display(self):
        """Render the worktree table with project headers and team worktrees"""
        if not hasattr(self, 'worktrees'):
            return

        # Sort worktrees by project, main repo first (is_main_repo=True sorts before False), then change_id
        sorted_wts = sorted(self.worktrees, key=lambda w: (w.get("project", ""), not w.get("is_main_repo", False), w.get("change_id", "")))
        self.worktrees = sorted_wts

        # Filter: show only worktrees with agents or editor open
        filter_active = getattr(self, 'filter_active', False)

        # Group by project (respecting filter)
        projects = {}
        for wt in self.worktrees:
            if filter_active:
                if not self._is_worktree_active(wt):
                    continue
            proj = wt.get("project", "")
            if proj not in projects:
                projects[proj] = []
            projects[proj].append(wt)

        # Calculate total rows: header + worktree rows (with multi-agent) + team worktrees per project
        total_rows = 0
        project_team_wts = {}  # Cache team worktrees per project

        for proj_name in projects.keys():
            total_rows += 1  # Project header row
            for wt in projects[proj_name]:
                total_rows += self._agent_rows_count(wt)
            # Check if THIS project has team enabled (skip team rows when filter active)
            team_enabled = self.get_project_team_enabled(proj_name)
            if team_enabled and not filter_active:
                team_wts = self._get_team_worktrees_for_project(proj_name)
                project_team_wts[proj_name] = team_wts
                total_rows += len(team_wts)

        self.table.setRowCount(total_rows)

        # Clear all cell widgets and spans from previous render
        for r in range(total_rows):
            if self.table.cellWidget(r, 0):
                self.table.removeCellWidget(r, 0)
            # Also clear Extra column widgets
            if self.table.cellWidget(r, COL_EXTRA):
                self.table.removeCellWidget(r, COL_EXTRA)
            if self.table.columnSpan(r, 0) > 1:
                self.table.setSpan(r, 0, 1, 1)

        # Track row mapping: row_index -> worktree data
        self.row_to_worktree = {}
        self.row_to_agent = {}
        self.row_to_team_worktree = {}
        self.row_to_project = {}
        self.running_rows = set()

        row = 0
        for proj_name in sorted(projects.keys()):
            proj_wts = projects[proj_name]
            proj_filter = self.team_filter_state.get(proj_name, 0)
            proj_unread = self.chat_unread.get(proj_name, 0)

            # 1. Project header row
            header_widget = self._create_project_header(proj_name, proj_filter, proj_unread)
            self.table.setCellWidget(row, 0, header_widget)
            self.table.setSpan(row, 0, 1, NUM_COLS)
            self.row_to_project[row] = proj_name
            # Make header row not selectable
            for col in range(NUM_COLS):
                item = QTableWidgetItem("")
                item.setFlags(item.flags() & ~Qt.ItemIsSelectable)
                self.table.setItem(row, col, item)
            row += 1

            # 2. Local worktree rows (with multi-agent support)
            for wt in proj_wts:
                agents = self._get_agents(wt)
                if len(agents) <= 1:
                    # Single agent or no agents — one row
                    agent = agents[0] if agents else {}
                    self._render_worktree_row(row, wt, agent, is_primary=True, agent_index=0)
                    self.row_to_worktree[row] = wt
                    self.row_to_agent[row] = agent
                    row += 1
                else:
                    # Multiple agents — one row per agent
                    for i, agent in enumerate(agents):
                        is_primary = (i == 0)
                        self._render_worktree_row(row, wt, agent, is_primary=is_primary, agent_index=i)
                        self.row_to_worktree[row] = wt
                        self.row_to_agent[row] = agent
                        row += 1

            # 3. Team worktree rows (if enabled, not hidden, and filter not active)
            if self.get_project_team_enabled(proj_name) and proj_filter != 2 and not filter_active:
                team_wts = project_team_wts.get(proj_name, [])
                for team_wt in team_wts:
                    self._render_team_worktree_row(row, team_wt)
                    self.row_to_team_worktree[row] = team_wt
                    row += 1

        # Adjust window height to fit content
        self.adjust_height_to_content()

    def get_memory_status(self, project: str) -> dict:
        """Get memory status from feature cache.
        Returns {"available": bool, "count": int}. No subprocess — reads cache only."""
        return getattr(self, '_feature_cache', {}).get(project, {}).get(
            "memory", {"available": False, "count": 0}
        )

    def get_openspec_status(self, project: str) -> dict:
        """Get OpenSpec status from feature cache.
        Returns {"installed": bool, "changes_active": int, ...}. No subprocess — reads cache only."""
        return getattr(self, '_feature_cache', {}).get(project, {}).get(
            "openspec", {"installed": False, "changes_active": 0, "skills_present": False, "cli_available": False}
        )

    def _create_project_header(self, project: str, filter_state: int, unread: int) -> QWidget:
        """Create a project header widget with team filter, chat, and memory buttons"""
        widget = QWidget()
        layout = QHBoxLayout(widget)
        layout.setContentsMargins(5, 2, 5, 2)
        layout.setSpacing(4)

        # Project name
        label = QLabel(project)
        label.setStyleSheet(f"font-weight: bold; color: {self.get_color('text_primary')};")
        layout.addWidget(label)

        layout.addStretch()

        # Memory [M] button (reads from FeatureWorker cache)
        mem_status = self.get_memory_status(project)
        mem_btn = QPushButton("M")
        mem_btn.setFixedSize(22, 22)
        has_cache = project in getattr(self, '_feature_cache', {})
        if not has_cache:
            mem_color = self.get_color("status_idle")
            mem_tooltip = "Memory: checking..."
        elif mem_status["available"] and mem_status["count"] > 0:
            mem_color = self.get_color("status_compacting")  # purple
            mem_tooltip = f"Memory: {mem_status['count']} memories"
        elif mem_status["available"]:
            mem_color = self.get_color("status_idle")
            mem_tooltip = "Memory: no memories yet"
        else:
            mem_color = self.get_color("status_idle")
            mem_tooltip = "Memory: not installed"
        mem_btn.setStyleSheet(f"QPushButton {{ background-color: {mem_color}; color: white; border-radius: 4px; font-weight: bold; font-size: 11px; }}")
        mem_btn.setToolTip(mem_tooltip)
        mem_btn.clicked.connect(lambda checked, p=project: self.show_memory_browse_dialog(p))
        layout.addWidget(mem_btn)

        # OpenSpec [O] button (reads from FeatureWorker cache)
        os_status = self.get_openspec_status(project)
        os_btn = QPushButton("O")
        os_btn.setFixedSize(22, 22)
        if not has_cache:
            os_color = self.get_color("status_idle")
            os_tooltip = "OpenSpec: checking..."
        elif os_status.get("installed"):
            os_color = self.get_color("status_running")  # green
            n = os_status.get("changes_active", 0)
            os_tooltip = f"OpenSpec: {n} active change{'s' if n != 1 else ''}"
        else:
            os_color = self.get_color("status_idle")
            os_tooltip = "OpenSpec: not initialized"
        os_btn.setStyleSheet(f"QPushButton {{ background-color: {os_color}; color: white; border-radius: 4px; font-weight: bold; font-size: 11px; }}")
        os_btn.setToolTip(os_tooltip)
        os_btn.clicked.connect(lambda checked, p=project: self.show_project_header_context_menu_at_button(p, os_btn))
        layout.addWidget(os_btn)

        # Team filter button - show for projects with team enabled
        project_team_enabled = self.get_project_team_enabled(project)
        has_team_data = self._project_has_team_data(project)
        if project_team_enabled and has_team_data:
            filter_text = "\U0001f465" if filter_state == 0 else "\U0001f464" if filter_state == 1 else "  "
            filter_tooltip = {
                0: "All Team - click to show My Machines only",
                1: "My Machines - click to hide team",
                2: "Team hidden - click to show all"
            }.get(filter_state, "")
            filter_btn = QPushButton(filter_text)
            filter_btn.setFixedSize(26, 22)
            filter_btn.setToolTip(filter_tooltip)
            filter_btn.clicked.connect(lambda checked, p=project: self.toggle_project_team_filter(p))
            layout.addWidget(filter_btn)

        # Chat button - show for team-enabled projects
        if project_team_enabled and has_team_data:
            chat_text = "\U0001f4ac*" if unread > 0 else "\U0001f4ac"
            chat_btn = QPushButton(chat_text)
            chat_btn.setFixedSize(32, 22)
            if unread > 0:
                # Fast blink effect using chat_blink_state
                if self.chat_blink_state:
                    chat_color = self.get_color("status_waiting")  # Orange
                else:
                    chat_color = self.get_color("button_primary")  # Blue
                chat_btn.setStyleSheet(f"QPushButton {{ background-color: {chat_color}; color: white; border-radius: 4px; font-weight: bold; }}")
                chat_btn.setToolTip(f"Chat ({unread} unread)")
            else:
                chat_btn.setStyleSheet(f"QPushButton {{ background-color: {self.get_color('button_primary')}; color: white; border-radius: 4px; }}")
                chat_btn.setToolTip("Team Chat")
            chat_btn.clicked.connect(lambda checked, p=project: self.show_chat_dialog(p))
            layout.addWidget(chat_btn)

        return widget

    def _set_row_background(self, row: int, color: QColor):
        """Set background color on all columns of a row.

        CellWidgets are kept transparent so the item background shows through.
        Alpha-transparent colors are replaced with bg_dialog to prevent
        rendering artifacts on Linux X11 frameless windows.
        """
        if color.alpha() < 255:
            color = QColor(self.get_color("bg_dialog"))
        for col in range(self.table.columnCount()):
            item = self.table.item(row, col)
            if item:
                item.setBackground(color)

    def _render_worktree_row(self, row: int, wt: dict, agent: dict, is_primary: bool = True, agent_index: int = 0):
        """Render a single worktree/agent row.

        Args:
            row: Table row index
            wt: Worktree data dict
            agent: Agent data dict (may be empty for idle worktrees)
            is_primary: True for the first (or only) row of a worktree
            agent_index: Index of this agent in the worktree's agents list (for Ctx% matching)
        """
        # Name column: show branch label on primary row, empty on secondary
        if is_primary:
            change_label = wt.get("change_id", "")
            if wt.get("is_main_repo"):
                change_label = f"\u2605 {change_label}"  # ★ prefix
            self.table.setItem(row, COL_NAME, QTableWidgetItem(change_label))
        else:
            self.table.setItem(row, COL_NAME, QTableWidgetItem(""))

        # PID column (⚠ prefix for orphans)
        pid = agent.get("pid")
        status = agent.get("status", "idle")
        pid_text = f"\u26a0 {pid}" if pid and status == "orphan" else (str(pid) if pid else "")
        self.table.setItem(row, COL_PID, QTableWidgetItem(pid_text))

        # Promote idle to "idle (IDE)" when editor is open and no agents
        editor_open = wt.get("editor_open", True)  # default True for backward compat
        if status == "idle" and editor_open:
            status = "idle (IDE)"
        elif status == "orphan" and editor_open:
            status = "orphan (IDE)"

        # Status with icon
        icon, color = self.get_status_icon(status)
        status_item = QTableWidgetItem(f"{icon} {status}")
        status_item.setForeground(color)
        self.table.setItem(row, COL_STATUS, status_item)

        # Determine row background and text color
        key = f"{wt.get('project', '')}:{wt.get('change_id', '')}"
        if status == "running":
            row_bg = "transparent"
            row_text = self.get_color("row_running_text")
            self.running_rows.add(row)
        elif status == "waiting":
            editor_type = agent.get("editor_type") or wt.get("editor_type") or ""
            in_terminal = editor_type and not _is_ide_editor_type(editor_type)
            if in_terminal:
                # Terminal-based agent: dim — expected state, not needing attention
                row_bg = self.get_color("row_idle")
                row_text = self.get_color("text_muted")
            elif key not in self.needs_attention:
                row_bg = self.get_color("row_waiting")
                row_text = self.get_color("row_waiting_text")
            else:
                row_bg = "transparent"
                row_text = None
        elif status in ("orphan", "orphan (IDE)"):
            row_bg = self.get_color("row_orphan")
            row_text = self.get_color("row_orphan_text")
        elif status == "idle (IDE)":
            row_bg = self.get_color("row_idle_ide")
            row_text = self.get_color("row_idle_ide_text")
        elif not editor_open and not self._is_worktree_active(wt):
            # Dim worktrees with no editor and no agents
            row_bg = self.get_color("row_idle")
            row_text = self.get_color("text_muted")
        else:
            row_bg = self.get_color("row_idle")
            row_text = self.get_color("row_idle_text")

        # Skill (dimmed if not freshly invoked)
        skill = agent.get("skill")
        skill_item = QTableWidgetItem(skill if skill else "")
        skill_fresh = agent.get("skill_fresh")
        if skill and skill_fresh == "last":
            skill_item.setForeground(QColor(self.get_color("text_muted")))
        self.table.setItem(row, COL_SKILL, skill_item)

        # Context usage % — per agent (each has its own session file)
        wt_path = wt.get("path", "")
        ctx_pct = self.get_context_usage(wt_path, agent_index)
        ctx_item = QTableWidgetItem(f"{ctx_pct}%" if ctx_pct > 0 else "")
        if ctx_pct >= 80:
            ctx_item.setForeground(QColor(self.get_color("ctx_high")))
        elif ctx_pct >= 50:
            ctx_item.setForeground(QColor(self.get_color("ctx_medium")))
        self.table.setItem(row, COL_CTX, ctx_item)

        # Extra column (Ralph indicator) — only on primary row
        if is_primary:
            self._render_extra_column(row, wt)
        else:
            self.table.setCellWidget(row, COL_EXTRA, None)
            self.table.setItem(row, COL_EXTRA, QTableWidgetItem(""))

        # Apply colors to cells
        if status != "running":
            self._set_row_background(row, QColor(row_bg))
        if row_text:
            for col in range(self.table.columnCount()):
                item = self.table.item(row, col)
                if item:
                    item.setForeground(QColor(row_text))

    def _render_extra_column(self, row: int, wt: dict):
        """Render the Extra column (Ralph indicator) for a worktree row."""
        wt_path = wt.get("path", "")

        # Ralph status
        ralph_status = self.get_ralph_status(wt_path)
        if ralph_status:
            integrations_widget = QWidget()
            integrations_widget.setStyleSheet("background: transparent;")
            integrations_layout = QHBoxLayout(integrations_widget)
            integrations_layout.setContentsMargins(2, 0, 2, 0)
            integrations_layout.setSpacing(2)

            ralph_btn = QPushButton("R")
            ralph_btn.setFixedSize(22, 22)
            if ralph_status["status"] in ("running", "starting"):
                ralph_color = self.get_color("status_running")
            elif ralph_status["status"] == "stuck":
                ralph_color = self.get_color("burn_high")
            elif ralph_status["status"] == "stalled":
                ralph_color = self.get_color("status_stalled")
            elif ralph_status["status"] == "done":
                ralph_color = self.get_color("status_done")
            else:
                ralph_color = self.get_color("status_idle")
            ralph_btn.setStyleSheet(f"QPushButton {{ background-color: {ralph_color}; color: white; border-radius: 4px; font-weight: bold; font-size: 11px; }}")
            tooltip = f"Ralph Loop: {ralph_status['status']}\n"
            tooltip += f"Iteration: {ralph_status['iteration']}/{ralph_status['max_iterations']}\n"
            # Elapsed time since start
            started_at = ralph_status.get("started_at", "")
            if started_at:
                try:
                    from datetime import datetime, timezone
                    start_dt = datetime.fromisoformat(started_at.replace("Z", "+00:00"))
                    now = datetime.now(timezone.utc)
                    elapsed = now - start_dt
                    elapsed_mins = int(elapsed.total_seconds() // 60)
                    elapsed_hours = elapsed_mins // 60
                    if elapsed_hours > 0:
                        tooltip += f"Elapsed: {elapsed_hours}h {elapsed_mins % 60}m\n"
                    else:
                        tooltip += f"Elapsed: {elapsed_mins}m\n"
                except Exception:
                    pass
            # Current iteration elapsed time
            iterations = ralph_status.get("iterations", [])
            if iterations and ralph_status["status"] in ("running", "starting"):
                last_iter = iterations[-1]
                iter_started = last_iter.get("started", "")
                if iter_started and not last_iter.get("ended"):
                    try:
                        iter_dt = datetime.fromisoformat(iter_started.replace("Z", "+00:00"))
                        iter_elapsed = int((now - iter_dt).total_seconds() // 60)
                        tooltip += f"Current iter: {iter_elapsed}m\n"
                    except Exception:
                        pass
            # Last commit timestamp
            last_commit_ts = ralph_status.get("last_commit_ts")
            if last_commit_ts:
                try:
                    ts = last_commit_ts.split("T")[1].split("+")[0][:5]
                    tooltip += f"Last commit: {ts}\n"
                except Exception:
                    pass
            # Stall threshold and iteration timeout
            stall_th = ralph_status.get("stall_threshold")
            iter_timeout = ralph_status.get("iteration_timeout_min")
            if stall_th is not None or iter_timeout is not None:
                settings_parts = []
                if stall_th is not None:
                    settings_parts.append(f"stall={stall_th}")
                if iter_timeout is not None:
                    settings_parts.append(f"timeout={iter_timeout}m")
                tooltip += f"Settings: {', '.join(settings_parts)}\n"
            if ralph_status.get("task"):
                tooltip += f"Task: {ralph_status['task'][:60]}"
            ralph_btn.setToolTip(tooltip)
            ralph_btn.clicked.connect(lambda checked, path=wt_path: self.focus_ralph_terminal(path))
            integrations_layout.addWidget(ralph_btn)
            integrations_layout.addStretch()

            self.table.setItem(row, COL_EXTRA, QTableWidgetItem(""))
            self.table.setCellWidget(row, COL_EXTRA, integrations_widget)
        else:
            self.table.setItem(row, COL_EXTRA, QTableWidgetItem(""))
            self.table.setCellWidget(row, COL_EXTRA, None)

    def _render_team_worktree_row(self, row: int, team_wt: dict):
        """Render a single team worktree row"""
        muted_color = QColor(self.get_color("text_muted"))
        my_machine_color = QColor(self.get_color("text_secondary"))
        text_color = my_machine_color if team_wt["is_my_machine"] else muted_color

        # Build tooltip
        tooltip = f"{team_wt['member_full']}\n"
        tooltip += f"Change: {team_wt['change_id']}\n"
        tooltip += f"Status: {team_wt['agent_status']}"
        activity = team_wt.get("activity")
        if activity:
            skill = activity.get("skill", "")
            skill_args = activity.get("skill_args", "")
            if skill:
                tooltip += f"\nSkill: {skill}"
                if skill_args:
                    tooltip += f" {skill_args}"
            broadcast = activity.get("broadcast")
            if broadcast:
                tooltip += f"\nBroadcast: {broadcast}"
        if team_wt.get("last_seen"):
            tooltip += f"\nLast seen: {self._format_relative_time(team_wt['last_seen'])}"

        # Name column: "member: change_id"
        prefix = "\u26a1 " if team_wt["is_my_machine"] else ""
        name_item = QTableWidgetItem(f"{prefix}{team_wt['member']}: {team_wt['change_id']}")
        name_item.setForeground(text_color)
        name_item.setFont(QFont(name_item.font().family(), -1, -1, True))  # Italic
        name_item.setToolTip(tooltip)
        self.table.setItem(row, COL_NAME, name_item)

        # Empty PID for team rows
        self.table.setItem(row, COL_PID, QTableWidgetItem(""))

        # Status icon only
        status = team_wt["agent_status"]
        icon, color = self.get_status_icon(status)
        status_item = QTableWidgetItem(f"{icon}")
        status_item.setForeground(color)
        status_item.setToolTip(tooltip)
        self.table.setItem(row, COL_STATUS, status_item)

        # Communication activity indicators in Skill column
        activity = team_wt.get("activity")
        comm_indicators = ""
        comm_tooltip = ""
        if activity:
            updated_at = activity.get("updated_at", "")
            broadcast = activity.get("broadcast")
            if broadcast and updated_at and self._is_recent(updated_at, 60):
                comm_indicators += "\U0001f4e1"  # 📡
                comm_tooltip += f"Broadcast: {broadcast}\n"

        # Check for recent directed messages
        last_activity = team_wt.get("last_activity", "")
        if last_activity and self._is_recent(last_activity, 60):
            # last_activity is the git commit time — if it's very fresh, may indicate message
            pass  # Directed message detection requires reading outbox, deferred to MCP

        skill_item = QTableWidgetItem(comm_indicators)
        if comm_tooltip:
            skill_item.setToolTip(comm_tooltip.strip())
        self.table.setItem(row, COL_SKILL, skill_item)

        # Empty cells for Ctx%, Extra
        for col in range(COL_CTX, NUM_COLS):
            empty_item = QTableWidgetItem("")
            empty_item.setToolTip(tooltip)
            self.table.setItem(row, col, empty_item)

    def get_context_usage(self, wt_path: str, agent_index: int = 0) -> int:
        """Get context usage percentage for a specific agent from Claude session files.

        Args:
            wt_path: Worktree path
            agent_index: Which agent (0=freshest session, 1=2nd freshest, etc.)
        """
        try:
            # Convert path to Claude's project directory format
            # e.g., /home/tg/code2/foo -> -home-tg-code2-foo
            proj_dir_name = wt_path.replace('/', '-').lstrip('-')
            session_dir = Path.home() / ".claude" / "projects" / f"-{proj_dir_name}"

            if not session_dir.exists():
                return 0

            # Find session files sorted by mtime (freshest first)
            session_files = sorted(session_dir.glob("*.jsonl"), key=lambda f: f.stat().st_mtime, reverse=True)
            if not session_files or agent_index >= len(session_files):
                return 0

            newest = session_files[agent_index]

            # Read last N lines to find one with usage info
            with open(newest, 'rb') as f:
                f.seek(0, 2)
                size = f.tell()
                if size == 0:
                    return 0

                # Read last 50KB (should contain several messages)
                read_size = min(size, 50000)
                f.seek(size - read_size)
                content = f.read().decode('utf-8', errors='ignore')

            # Parse lines from end, looking for usage info
            lines = content.strip().split('\n')
            for line in reversed(lines):
                try:
                    data = json.loads(line)
                    usage = data.get('message', {}).get('usage', {})
                    cache_read = usage.get('cache_read_input_tokens', 0)
                    cache_creation = usage.get('cache_creation_input_tokens', 0)
                    if cache_read > 0 or cache_creation > 0:
                        total_context = cache_read + cache_creation
                        # Opus 4.5 has 200k context
                        max_context = 200000
                        percentage = int((total_context / max_context) * 100)
                        return min(percentage, 100)
                except (json.JSONDecodeError, KeyError):
                    continue

            return 0

        except Exception:
            return 0

    def get_ralph_status(self, wt_path: str) -> dict:
        """Get Ralph loop status for worktree

        Returns:
            dict with keys: active, status, iteration, max_iterations
            or empty dict if no loop
        """
        if not wt_path:
            return {}

        loop_state_file = Path(wt_path) / ".wt" / "loop-state.json"
        if not loop_state_file.exists():
            return {}

        try:
            with open(loop_state_file) as f:
                state = json.load(f)

            status = state.get("status", "unknown")

            # Check if process is still alive when status says running
            if status in ("running", "starting"):
                pid = state.get("terminal_pid")
                if pid:
                    try:
                        # Check if process exists (signal 0 = just check)
                        os.kill(int(pid), 0)
                    except (ProcessLookupError, ValueError):
                        # Process died - update state to stopped
                        status = "stopped"
                        state["status"] = "stopped"
                        with open(loop_state_file, 'w') as f:
                            json.dump(state, f, indent=2)

            # Only show if loop is active or recently finished
            if status in ("running", "starting", "stuck", "stalled", "done", "stopped"):
                iterations = state.get("iterations", [])
                last_commit_ts = None
                for it in reversed(iterations):
                    if it.get("commits"):
                        last_commit_ts = it.get("ended")
                        break

                return {
                    "active": status in ("running", "starting"),
                    "status": status,
                    "iteration": state.get("current_iteration", 0),
                    "max_iterations": state.get("max_iterations", 10),
                    "task": state.get("task", ""),
                    "started_at": state.get("started_at", ""),
                    "iterations": iterations,
                    "last_commit_ts": last_commit_ts,
                    "stall_threshold": state.get("stall_threshold"),
                    "iteration_timeout_min": state.get("iteration_timeout_min"),
                }
        except Exception:
            pass

        return {}

    def _update_chat_button_colors(self):
        """Update chat button colors for blink effect without rebuilding table"""
        # Determine the blink color
        if self.chat_blink_state:
            chat_color = self.get_color("status_waiting")  # Orange
        else:
            chat_color = self.get_color("button_primary")  # Blue

        # Find all project header rows and update chat buttons
        for row in range(self.table.rowCount()):
            # Check if this is a header row (has cell widget spanning columns)
            widget = self.table.cellWidget(row, 0)
            if widget and self.table.columnSpan(row, 0) > 1:
                # This is a header row, find chat button
                layout = widget.layout()
                if layout:
                    for i in range(layout.count()):
                        item = layout.itemAt(i)
                        if item and item.widget():
                            btn = item.widget()
                            # Chat button has message bubble emoji
                            if isinstance(btn, QPushButton) and "\U0001f4ac" in btn.text():
                                if "*" in btn.text():  # Has unread - apply blink
                                    btn.setStyleSheet(f"QPushButton {{ background-color: {chat_color}; color: white; border-radius: 4px; font-weight: bold; }}")

    def update_pulse(self):
        """Update pulse animation for running rows"""
        if not self.running_rows:
            return

        # Update phase (complete cycle every ~1 second)
        self.pulse_phase = (self.pulse_phase + 0.1) % (2 * math.pi)

        # Calculate opacity: oscillate between 0.2 and 0.5
        opacity = 0.2 + 0.15 * (1 + math.sin(self.pulse_phase))

        # Blend green with background to get an opaque color
        # (alpha-transparent colors cause rendering artifacts on Linux X11 frameless windows)
        bg = QColor(self.get_color("bg_dialog"))
        green = QColor(34, 197, 94)
        r = int(bg.red() * (1 - opacity) + green.red() * opacity)
        g = int(bg.green() * (1 - opacity) + green.green() * opacity)
        b = int(bg.blue() * (1 - opacity) + green.blue() * opacity)
        blended = QColor(r, g, b)

        for row in self.running_rows:
            if row < self.table.rowCount():
                self._set_row_background(row, blended)

    def _is_recent(self, iso_timestamp: str, seconds: int = 60) -> bool:
        """Check if an ISO timestamp is within the last N seconds"""
        if not iso_timestamp:
            return False
        try:
            from datetime import datetime, timezone
            ts = iso_timestamp.replace("Z", "+00:00")
            dt = datetime.fromisoformat(ts)
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            now = datetime.now(timezone.utc)
            elapsed = (now - dt).total_seconds()
            return elapsed <= seconds
        except Exception:
            return False
