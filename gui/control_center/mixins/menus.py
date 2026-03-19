"""
Menus Mixin - Context menus and actions
"""

import logging
import os
import signal
import subprocess
from pathlib import Path

from PySide6.QtWidgets import (
    QMenu, QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QGroupBox, QFormLayout, QSpinBox, QComboBox,
    QTextEdit, QDialogButtonBox
)
from PySide6.QtCore import Qt

from ...constants import SCRIPT_DIR
from ...dialogs import (
    SettingsDialog, WorkDialog, NewWorktreeDialog, WorktreeConfigDialog,
    CommandOutputDialog, MergeDialog, TeamSettingsDialog, ChatDialog,
    show_warning, show_information,
)
from ...utils import get_main_repo_path

__all__ = ["MenusMixin"]

logger = logging.getLogger("set-control.menus")


class MenusMixin:
    """Mixin for menu functionality"""

    def show_main_menu(self):
        """Show main menu from menu button"""
        menu = QMenu(self)

        settings_action = menu.addAction("Settings...")
        settings_action.triggered.connect(self.open_settings)

        add_account_action = menu.addAction("Add Account...")
        add_account_action.triggered.connect(self.show_add_account)

        scan_chrome_action = menu.addAction("Scan Chrome Sessions")
        scan_chrome_action.triggered.connect(self.on_scan_chrome_sessions)

        # Only show remove if >1 account
        from ...workers.usage import load_accounts
        accounts = load_accounts()
        if len(accounts) > 1:
            remove_account_action = menu.addAction("Remove Account...")
            remove_account_action.triggered.connect(self.show_remove_account)

        usage_action = menu.addAction("Usage (Browser)")
        usage_action.triggered.connect(self.show_claude_usage)

        menu.addSeparator()

        minimize_action = menu.addAction("Minimize to Tray")
        minimize_action.triggered.connect(self.hide)

        menu.addSeparator()

        restart_action = menu.addAction("Restart")
        restart_action.triggered.connect(self.restart_app)

        quit_action = menu.addAction("Quit")
        quit_action.triggered.connect(self.quit_app)

        btn_pos = self.btn_menu.mapToGlobal(self.btn_menu.rect().bottomLeft())
        menu.exec(btn_pos)

    def open_settings(self):
        """Open settings dialog"""
        self.hide()
        dialog = SettingsDialog(self, self.config, self.get_active_project())
        result = dialog.exec()
        self.show()
        if result == QDialog.Accepted:
            try:
                self.apply_config_changes()
            except Exception as e:
                import traceback
                import sys
                print(f"Error in apply_config_changes: {e}", file=sys.stderr)
                traceback.print_exc()

    def open_team_settings(self, project: str = None):
        """Open team settings dialog for specific project"""
        if project is None:
            project = self.get_active_project()
        if not project:
            show_warning(self, "Team Settings", "No project selected.")
            return
        # Get remote_url for this project (used as config key)
        remote_url = self._get_project_remote_url(project)
        self.hide()
        dialog = TeamSettingsDialog(self, self.config, project, remote_url)
        result = dialog.exec()
        self.show()
        if result == QDialog.Accepted:
            try:
                self.apply_config_changes()
            except Exception as e:
                import traceback
                import sys
                print(f"Error in apply_config_changes: {e}", file=sys.stderr)
                traceback.print_exc()

    def show_context_menu(self, pos):
        """Show right-click context menu"""
        menu = QMenu(self)

        new_action = menu.addAction("+ New Worktree")
        new_action.triggered.connect(self.on_new)

        work_action = menu.addAction("Work...")
        work_action.triggered.connect(self.on_work)

        menu.addSeparator()

        refresh_action = menu.addAction("↻ Refresh")
        refresh_action.triggered.connect(self.refresh_status)

        menu.addSeparator()

        minimize_action = menu.addAction("Minimize to Tray")
        minimize_action.triggered.connect(self.hide)

        menu.addSeparator()

        restart_action = menu.addAction("Restart")
        restart_action.triggered.connect(self.restart_app)

        quit_action = menu.addAction("Quit")
        quit_action.triggered.connect(self.quit_app)

        menu.exec(self.mapToGlobal(pos))

    def show_row_context_menu(self, pos):
        """Show context menu for worktree row"""
        # Get the row at click position
        row = self.table.rowAt(pos.y())
        if row < 0:
            return

        # Check if this is a team worktree row
        team_wt = self.row_to_team_worktree.get(row)
        if team_wt is not None:
            self.show_team_row_context_menu(pos, row, team_wt)
            return

        # Check if this is a project header row
        project = getattr(self, 'row_to_project', {}).get(row)
        if project is not None:
            self.show_project_header_context_menu(pos, project)
            return

        # Get worktree data for this row (skip non-mapped rows)
        wt = self.row_to_worktree.get(row)
        if wt is None:
            return

        logger.info("context_menu: project=%s change=%s", wt.get("project", ""), wt.get("change_id", ""))
        # Select the row
        self.table.selectRow(row)

        menu = QMenu(self)
        wt_path = wt.get("path", "")
        project = wt.get("project", "")
        change_id = wt.get("change_id", "")
        branch = wt.get("branch", f"change/{change_id}")
        is_main_repo = wt.get("is_main_repo", False)

        # Top-level actions
        focus_action = menu.addAction("Focus Window")
        focus_action.triggered.connect(self.on_focus)

        close_editor_action = menu.addAction("Close Editor")
        close_editor_action.triggered.connect(self.on_close_editor)

        terminal_action = menu.addAction("Open in Terminal")
        terminal_action.triggered.connect(lambda: self.open_in_terminal(wt_path))

        filemanager_action = menu.addAction("Open in File Manager")
        filemanager_action.triggered.connect(lambda: self.open_in_file_manager(wt_path))

        copy_action = menu.addAction("Copy Path")
        copy_action.triggered.connect(lambda: self.copy_to_clipboard(wt_path))

        # Install Hooks action (when hooks not installed)
        if not wt.get("hooks_installed", True):
            menu.addSeparator()
            install_hooks_action = menu.addAction("Install Hooks")
            install_hooks_action.triggered.connect(lambda checked, p=wt_path: self._install_hooks(p))

        # Kill orphan action (only for orphan agents)
        agent = self._get_agent_for_row(row, wt)
        if agent and agent.get("status") == "orphan":
            orphan_pid = agent.get("pid")
            if orphan_pid:
                menu.addSeparator()
                kill_action = menu.addAction("\u26a0 Kill Orphan Process")
                kill_action.triggered.connect(lambda checked, p=orphan_pid: self._kill_orphan_process(p))

        menu.addSeparator()

        # New worktree for same project
        new_from_action = menu.addAction("+ New Worktree...")
        new_from_action.triggered.connect(lambda: self.on_new(preset_project=project))

        menu.addSeparator()

        # Git submenu
        git_menu = menu.addMenu("Git")
        if not is_main_repo:
            merge_action = git_menu.addAction("Merge to...")
            merge_action.triggered.connect(lambda: self.git_merge(wt_path, project, change_id))
        merge_from_action = git_menu.addAction("Merge from...")
        merge_from_action.triggered.connect(lambda: self.git_merge_from(wt_path, branch))
        push_action = git_menu.addAction("Push")
        push_action.triggered.connect(lambda: self.git_push(wt_path))
        pull_action = git_menu.addAction("Pull")
        pull_action.triggered.connect(lambda: self.git_pull(wt_path))
        fetch_action = git_menu.addAction("Fetch")
        fetch_action.triggered.connect(lambda: self.git_fetch(wt_path))

        # Project submenu (project-level settings)
        project_menu = menu.addMenu("Project")
        chat_action = project_menu.addAction("Team Chat...")
        chat_action.triggered.connect(self.show_chat_dialog)
        generate_key_action = project_menu.addAction("Generate Chat Key...")
        generate_key_action.triggered.connect(lambda: self.generate_chat_key_for_project(project))
        project_menu.addSeparator()
        team_settings_action = project_menu.addAction("Team Settings...")
        team_settings_action.triggered.connect(lambda: self.open_team_settings(project))

        # Check if set-control is already initialized
        main_repo = get_main_repo_path(wt_path)
        wt_control_initialized = main_repo and Path(main_repo, ".set-control").exists()

        if wt_control_initialized:
            init_control_action = project_menu.addAction("set-control (initialized)")
            init_control_action.setEnabled(False)
        else:
            init_control_action = project_menu.addAction("Initialize set-control...")
            init_control_action.triggered.connect(lambda: self.init_wt_control_for_project(project))

        # Ralph Loop submenu
        ralph_status = self.get_ralph_status(wt_path)
        ralph_menu = menu.addMenu("Ralph Loop")

        if ralph_status and ralph_status.get("active"):
            # Loop is running
            view_terminal_action = ralph_menu.addAction("View Terminal")
            view_terminal_action.triggered.connect(lambda: self.focus_ralph_terminal(wt_path))

            status_text = f"Status: {ralph_status['status']} ({ralph_status['iteration']}/{ralph_status['max_iterations']})"
            status_action = ralph_menu.addAction(status_text)
            status_action.setEnabled(False)

            ralph_menu.addSeparator()

            stop_action = ralph_menu.addAction("Stop Loop")
            stop_action.triggered.connect(lambda: self.stop_ralph_loop(wt_path))
        else:
            # No loop running
            start_action = ralph_menu.addAction("Start Loop...")
            start_action.triggered.connect(lambda: self.start_ralph_loop_dialog(wt_path))

            if ralph_status and ralph_status.get("status") in ("done", "stuck", "stopped"):
                history_text = f"Last: {ralph_status['status']} ({ralph_status['iteration']}/{ralph_status['max_iterations']})"
                history_action = ralph_menu.addAction(history_text)
                history_action.setEnabled(False)

                # Show View Log for finished loops (terminal is likely closed)
                view_log_action = ralph_menu.addAction("View Log")
                view_log_action.triggered.connect(lambda: self.view_ralph_log(wt_path))

        if not is_main_repo:
            # Worktree submenu (not applicable to main repo)
            wt_menu = menu.addMenu("Worktree")
            close_action = wt_menu.addAction("Close")
            close_action.triggered.connect(self.on_close)

            menu.addSeparator()

            # Worktree Config
            config_action = menu.addAction("Worktree Config...")
            config_action.triggered.connect(lambda: self.show_worktree_config(wt_path))

        menu.exec(self.table.viewport().mapToGlobal(pos))

    def show_project_header_context_menu_at_button(self, project: str, button):
        """Open project header context menu positioned below a button widget."""
        global_pos = button.mapToGlobal(button.rect().bottomLeft())
        self.show_project_header_context_menu(global_pos, project, use_global_pos=True)

    def show_project_header_context_menu(self, pos, project: str, use_global_pos: bool = False):
        """Show context menu for project header row"""
        menu = QMenu(self)

        # Memory submenu
        memory_menu = menu.addMenu("Memory")
        mem_status = self.get_memory_status(project)

        if mem_status["available"]:
            status_text = f"Status: available ({mem_status['count']} memories)"
        else:
            status_text = "Status: not installed"
        status_action = memory_menu.addAction(status_text)
        status_action.setEnabled(False)

        memory_menu.addSeparator()

        browse_action = memory_menu.addAction("Browse Memories...")
        browse_action.setEnabled(mem_status["available"])
        browse_action.triggered.connect(lambda: self.show_memory_browse_dialog(project))

        remember_action = memory_menu.addAction("Remember Note...")
        remember_action.setEnabled(mem_status["available"])
        remember_action.triggered.connect(lambda: self.show_remember_note_dialog(project))

        # OpenSpec submenu
        openspec_menu = menu.addMenu("OpenSpec")
        os_status = self.get_openspec_status(project)

        if os_status.get("installed"):
            n = os_status.get("changes_active", 0)
            os_status_text = f"Installed ({n} active change{'s' if n != 1 else ''})"
            os_status_action = openspec_menu.addAction(os_status_text)
            os_status_action.setEnabled(False)

            openspec_menu.addSeparator()

            update_action = openspec_menu.addAction("Update Skills...")
            update_action.triggered.connect(lambda: self._run_openspec_action("update", project))
        else:
            os_status_action = openspec_menu.addAction("Not initialized")
            os_status_action.setEnabled(False)

            openspec_menu.addSeparator()

            init_action_os = openspec_menu.addAction("Initialize OpenSpec...")
            init_action_os.triggered.connect(lambda: self._run_openspec_action("init", project))

        menu.addSeparator()

        # Standard project actions
        new_action = menu.addAction("+ New Worktree...")
        new_action.triggered.connect(lambda: self.on_new(preset_project=project))

        # Team actions (if team enabled)
        project_team_enabled = self.get_project_team_enabled(project)
        has_team_data = self._project_has_team_data(project)
        if project_team_enabled and has_team_data:
            chat_action = menu.addAction("Team Chat...")
            chat_action.triggered.connect(lambda: self.show_chat_dialog(project))

            team_settings_action = menu.addAction("Team Settings...")
            team_settings_action.triggered.connect(lambda: self.open_team_settings(project))

        # set-control init
        first_wt = self._get_first_worktree_for_project(project)
        if first_wt:
            wt_path = first_wt.get("path", "")
            main_repo = get_main_repo_path(wt_path)
            wt_control_initialized = main_repo and Path(main_repo, ".set-control").exists()
            if wt_control_initialized:
                init_action = menu.addAction("set-control (initialized)")
                init_action.setEnabled(False)
            else:
                init_action = menu.addAction("Initialize set-control...")
                init_action.triggered.connect(lambda: self.init_wt_control_for_project(project))

        if use_global_pos:
            menu.exec(pos)
        else:
            menu.exec(self.table.viewport().mapToGlobal(pos))

    def _get_first_worktree_for_project(self, project: str):
        """Get the first (main) worktree for a project"""
        for wt in getattr(self, 'worktrees', []):
            if wt.get("project") == project:
                return wt
        return None

    def _run_openspec_action(self, action: str, project: str):
        """Run wt-openspec init or update via CommandOutputDialog, then refresh cache."""
        first_wt = self._get_first_worktree_for_project(project)
        if not first_wt:
            return
        wt_path = first_wt.get("path", "")
        main_repo = get_main_repo_path(wt_path)
        if not main_repo:
            main_repo = wt_path

        cmd = [str(SCRIPT_DIR / "wt-openspec"), action]
        self.run_command_dialog(f"OpenSpec {action}", cmd, cwd=main_repo)

        self.refresh_feature_cache()

    def show_team_row_context_menu(self, pos, row: int, team_wt: dict):
        """Show read-only context menu for team worktree row"""
        self.table.selectRow(row)

        menu = QMenu(self)

        # View Details action
        details_action = menu.addAction("View Details...")
        details_action.triggered.connect(lambda: self.show_team_worktree_details(team_wt))

        menu.addSeparator()

        # Copy Change ID action
        copy_action = menu.addAction("Copy Change ID")
        copy_action.triggered.connect(lambda: self.copy_to_clipboard(team_wt.get("change_id", "")))

        menu.exec(self.table.viewport().mapToGlobal(pos))

    def show_team_worktree_details(self, team_wt: dict):
        """Show details dialog for team worktree"""
        self.hide()
        dialog = QDialog(self)
        dialog.setWindowTitle("Team Worktree Details")
        dialog.setWindowFlags(dialog.windowFlags() | Qt.WindowStaysOnTopHint)
        dialog.setMinimumWidth(350)

        layout = QVBoxLayout(dialog)

        # Activity info
        activity = team_wt.get('activity')
        activity_rows = ""
        if activity:
            skill = activity.get("skill", "")
            skill_args = activity.get("skill_args", "")
            if skill:
                skill_display = skill
                if skill_args:
                    skill_display += f" {skill_args}"
                activity_rows += f"<tr><td><b>Skill:</b></td><td>{skill_display}</td></tr>"
            broadcast = activity.get("broadcast")
            if broadcast:
                activity_rows += f"<tr><td><b>Broadcast:</b></td><td>{broadcast}</td></tr>"

        # Member info
        info_text = f"""
<h3>{team_wt.get('member_full', team_wt.get('member', '?'))}</h3>
<table>
<tr><td><b>Hostname:</b></td><td>{team_wt.get('member_hostname', '?')}</td></tr>
<tr><td><b>Change:</b></td><td>{team_wt.get('change_id', '?')}</td></tr>
<tr><td><b>Status:</b></td><td>{team_wt.get('agent_status', 'idle')}</td></tr>
{activity_rows}<tr><td><b>Last seen:</b></td><td>{self._format_relative_time(team_wt.get('last_seen', ''))}</td></tr>
</table>
"""
        if team_wt.get('is_my_machine'):
            info_text += "<p><i>⚡ This is your other machine</i></p>"

        label = QLabel(info_text)
        label.setTextFormat(Qt.RichText)
        label.setWordWrap(True)
        layout.addWidget(label)

        # Close button
        close_btn = QPushButton("Close")
        close_btn.clicked.connect(dialog.accept)
        layout.addWidget(close_btn)

        dialog.exec()
        self.show()

    def show_chat_dialog(self, project=None):
        """Show the chat dialog"""
        if not self.team_data.get("members"):
            show_information(self, "Chat", "No team members found. Enable team sync in Settings.")
            return

        current_project = project or self.get_active_project()

        if not current_project:
            show_information(self, "Chat", "No project found.")
            return

        self.hide()
        try:
            dialog = ChatDialog(self, self.config, self.team_data, current_project)
            dialog.exec()
        except Exception as e:
            show_warning(self, "Chat Error", f"Failed to open chat: {e}")
        finally:
            self.show()

        # Reset chat badge
        self.update_chat_badge(0)

    def show_worktree_config(self, wt_path: str):
        """Show worktree config dialog"""
        config_dir = Path(wt_path) / ".set-core"

        self.hide()
        dialog = WorktreeConfigDialog(self, wt_path, config_dir)
        dialog.exec()
        self.show()

    def start_ralph_loop_dialog(self, wt_path: str):
        """Show dialog to start a Ralph loop"""
        self.hide()

        worktree_name = Path(wt_path).name
        dialog = QDialog(self)
        dialog.setWindowTitle(f"Start Ralph Loop - {worktree_name}")
        dialog.setWindowFlags(dialog.windowFlags() | Qt.WindowStaysOnTopHint)
        dialog.setMinimumWidth(450)

        layout = QVBoxLayout(dialog)

        # Task description
        layout.addWidget(QLabel("Task Description:"))
        task_input = QTextEdit()
        task_input.setPlaceholderText("Describe what should be accomplished...")
        task_input.setMaximumHeight(100)
        layout.addWidget(task_input)

        # Check if tasks.md exists for this change
        tasks_md_exists = False
        wt = Path(wt_path)
        for tasks_file in wt.rglob("tasks.md"):
            tasks_md_exists = True
            break

        # Options
        options_group = QGroupBox("Options")
        options_layout = QFormLayout(options_group)

        max_iter_spin = QSpinBox()
        max_iter_spin.setRange(1, 50)
        default_max = self.config.get("ralph", "default_max_iterations", 10)
        max_iter_spin.setValue(default_max)
        options_layout.addRow("Max Iterations:", max_iter_spin)

        done_criteria_combo = QComboBox()
        done_criteria_combo.addItems(["tasks", "manual"])
        # Default to "tasks" if tasks.md exists, otherwise "manual"
        if not tasks_md_exists:
            done_criteria_combo.setCurrentText("manual")
        options_layout.addRow("Done Criteria:", done_criteria_combo)

        # tasks.md indicator
        tasks_md_label = QLabel()
        tasks_md_label.setObjectName("tasks_md_label")
        if tasks_md_exists:
            tasks_md_label.setText("tasks.md: found")
            tasks_md_label.setStyleSheet("color: green;")
        else:
            tasks_md_label.setText("tasks.md: not found")
            tasks_md_label.setStyleSheet("color: gray;")
        options_layout.addRow("", tasks_md_label)

        # Manual warning label (hidden by default)
        manual_warning = QLabel("Loop won't auto-stop")
        manual_warning.setObjectName("manual_warning")
        manual_warning.setStyleSheet("color: orange; font-weight: bold;")
        manual_warning.setVisible(done_criteria_combo.currentText() == "manual")
        options_layout.addRow("", manual_warning)

        def on_done_criteria_changed(text):
            manual_warning.setVisible(text == "manual")

        done_criteria_combo.currentTextChanged.connect(on_done_criteria_changed)

        # Stall threshold
        stall_threshold_spin = QSpinBox()
        stall_threshold_spin.setObjectName("stall_threshold_spin")
        stall_threshold_spin.setRange(1, 10)
        default_stall = self.config.get("ralph", "default_stall_threshold", 2)
        stall_threshold_spin.setValue(default_stall)
        options_layout.addRow("Stall Threshold:", stall_threshold_spin)

        # Iteration timeout
        iter_timeout_spin = QSpinBox()
        iter_timeout_spin.setObjectName("iter_timeout_spin")
        iter_timeout_spin.setRange(5, 120)
        iter_timeout_spin.setSuffix(" min")
        default_timeout = self.config.get("ralph", "default_iteration_timeout", 45)
        iter_timeout_spin.setValue(default_timeout)
        options_layout.addRow("Iteration Timeout:", iter_timeout_spin)

        layout.addWidget(options_group)

        # Buttons
        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(dialog.accept)
        buttons.rejected.connect(dialog.reject)
        layout.addWidget(buttons)

        if dialog.exec() == QDialog.Accepted:
            task = task_input.toPlainText().strip()
            if not task:
                show_warning(self, "Error", "Task description is required")
                self.show()
                return

            # Build command
            cmd = [
                str(SCRIPT_DIR / "set-loop"),
                "start",
                task,
                "--max", str(max_iter_spin.value()),
                "--done", done_criteria_combo.currentText(),
                "--stall-threshold", str(stall_threshold_spin.value()),
                "--iteration-timeout", str(iter_timeout_spin.value()),
            ]

            # Add fullscreen if configured
            if self.config.get("ralph", "terminal_fullscreen", False):
                cmd.append("--fullscreen")

            # Run in background
            subprocess.Popen(cmd, cwd=wt_path)

        self.show()

    def _get_agent_for_row(self, row: int, wt: dict) -> dict:
        """Get the agent dict for a specific table row.

        For multi-agent worktrees, determines which agent corresponds to the row
        by finding the row offset within the worktree's row span.
        """
        agents = wt.get("agents", [])
        if not agents:
            return {}
        if len(agents) == 1:
            return agents[0]
        # Multi-agent: find this row's index among the worktree's rows
        first_row = None
        for r, w in self.row_to_worktree.items():
            if w is wt:
                if first_row is None or r < first_row:
                    first_row = r
        if first_row is not None:
            agent_idx = row - first_row
            if 0 <= agent_idx < len(agents):
                return agents[agent_idx]
        return agents[0]

    def _kill_orphan_process(self, pid: int):
        """Send SIGTERM to an orphan claude process."""
        logger.info("kill_orphan: pid=%d", pid)
        try:
            os.kill(pid, signal.SIGTERM)
        except ProcessLookupError:
            pass  # Already dead
        except PermissionError:
            logger.error("kill_orphan: permission denied for pid=%d", pid)
            show_warning(self, "Kill Failed", f"Permission denied to kill PID {pid}.")

    def _install_hooks(self, wt_path: str):
        """Install Claude Code hooks to a worktree via wt-deploy-hooks."""
        logger.info("install_hooks: path=%s", wt_path)
        deploy_script = SCRIPT_DIR / "wt-deploy-hooks"
        try:
            result = subprocess.run(
                [str(deploy_script), wt_path],
                capture_output=True, text=True, timeout=10,
            )
            if result.returncode == 0:
                show_information(self, "Install Hooks", "Hooks installed successfully.")
            else:
                show_warning(self, "Install Hooks", f"Hook installation failed:\n{result.stderr}")
        except FileNotFoundError:
            show_warning(self, "Install Hooks", "wt-deploy-hooks script not found.")
        except subprocess.TimeoutExpired:
            show_warning(self, "Install Hooks", "Hook installation timed out.")
        self.refresh_status()
