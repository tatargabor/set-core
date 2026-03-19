"""
Handlers Mixin - Event handlers and actions
"""

import json
import logging
import os
import subprocess
import webbrowser
from pathlib import Path

from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QLabel, QPushButton,
    QApplication, QTextEdit, QFileDialog,
)
from PySide6.QtCore import Qt
from PySide6.QtGui import QColor

from ...constants import SCRIPT_DIR, CONFIG_DIR
from ...dialogs import (
    WorkDialog, NewWorktreeDialog, CommandOutputDialog, MergeDialog,
    show_warning, show_information, show_question,
    get_text, get_item, get_existing_directory,
)
from ...logging_setup import log_exceptions
from ...dialogs.memory_dialog import MemoryBrowseDialog, RememberNoteDialog
from ...platform import get_platform

__all__ = ["HandlersMixin"]

logger = logging.getLogger("set-control.handlers")


class HandlersMixin:
    """Mixin for event handlers"""

    def run_command_dialog(self, title: str, cmd: list, cwd: str = None):
        """Run a command and show output in a dialog"""
        self.hide()
        dialog = CommandOutputDialog(self, title, cmd, cwd)
        dialog.exec()
        self.show_window()

    def open_in_terminal(self, path: str):
        """Open terminal in the given path"""
        try:
            import platform
            system = platform.system()
            if system == "Linux":
                subprocess.Popen(["x-terminal-emulator", "--working-directory", path])
            elif system == "Darwin":
                subprocess.Popen(["open", "-a", "Terminal", path])
            elif system == "Windows":
                subprocess.Popen(["cmd", "/c", "start", "cmd", "/k", f"cd /d {path}"])
        except Exception as e:
            show_warning(self, "Error", f"Failed to open terminal: {e}")

    def open_in_file_manager(self, path: str):
        """Open file manager at the given path"""
        platform = get_platform()
        if not platform.open_file(path):
            show_warning(self, "Error", "Failed to open file manager")

    def copy_to_clipboard(self, text: str):
        """Copy text to clipboard"""
        QApplication.clipboard().setText(text)

    def git_merge(self, path: str, project: str, change_id: str):
        """Merge worktree branch - ask for target branch"""
        logger.info("git_merge: project=%s change=%s path=%s", project, change_id, path)
        # Get available branches
        branches = ["master", "main"]
        try:
            result = subprocess.run(
                ["git", "-C", path, "branch", "-r", "--format=%(refname:short)"],
                capture_output=True, text=True, timeout=5
            )
            if result.returncode == 0:
                for line in result.stdout.strip().split('\n'):
                    line = line.strip()
                    if line and not line.startswith('origin/HEAD'):
                        branch = line.replace('origin/', '')
                        if branch not in branches and not branch.startswith('change/'):
                            branches.append(branch)
        except Exception:
            pass

        # Check for uncommitted changes
        has_changes = False
        try:
            result = subprocess.run(
                ["git", "-C", path, "status", "--porcelain"],
                capture_output=True, text=True, timeout=5
            )
            has_changes = bool(result.stdout.strip())
        except Exception:
            pass

        # Show merge dialog
        self.hide()
        dialog = MergeDialog(self, f"change/{change_id}", branches, has_changes)
        if dialog.exec() == QDialog.Accepted:
            target = dialog.get_target()
            stash = dialog.should_stash()

            if stash and has_changes:
                # Stash changes first
                stash_cmd = ["git", "-C", path, "stash", "push", "-m", f"Auto-stash before merge to {target}"]
                stash_dialog = CommandOutputDialog(self, "Stashing changes", stash_cmd)
                stash_dialog.exec()

            cmd = [str(SCRIPT_DIR / "set-merge"), "-p", project, change_id, "--to", target]
            if dialog.should_keep_branch():
                cmd.append("--no-delete")
            if not dialog.should_push():
                cmd.append("--no-push")
            merge_dialog = CommandOutputDialog(self, f"Merge to {target}", cmd)
            merge_dialog.exec()

            if stash and has_changes:
                # Pop stash after merge
                pop_cmd = ["git", "-C", path, "stash", "pop"]
                pop_dialog = CommandOutputDialog(self, "Restoring stashed changes", pop_cmd)
                pop_dialog.exec()
        self.show_window()

    def git_merge_from(self, path: str, current_branch: str):
        """Merge another branch into current worktree"""
        logger.info("git_merge_from: branch=%s path=%s", current_branch, path)
        # Get available branches to merge from (change/* branches and main branches)
        branches = []
        try:
            result = subprocess.run(
                ["git", "-C", path, "branch", "-r", "--format=%(refname:short)"],
                capture_output=True, text=True, timeout=5
            )
            if result.returncode == 0:
                for line in result.stdout.strip().split('\n'):
                    line = line.strip()
                    if line and not line.startswith('origin/HEAD'):
                        branch = line.replace('origin/', '')
                        # Skip current branch
                        if branch != current_branch and f"origin/{branch}" != current_branch:
                            branches.append(branch)
        except Exception:
            pass

        # Sort: change/* branches first, then others
        change_branches = sorted([b for b in branches if b.startswith('change/')])
        other_branches = sorted([b for b in branches if not b.startswith('change/')])
        branches = change_branches + other_branches

        if not branches:
            show_information(self, "Merge From", "No other branches found to merge from.")
            return

        # Ask user which branch to merge from
        self.hide()
        source, ok = get_item(
            self, "Merge From",
            f"Merge into {current_branch} from:",
            branches, 0, False
        )
        if ok and source:
            # First fetch, then merge
            cmd = ["git", "-C", path, "fetch", "origin", source]
            self.run_command_dialog(f"Fetching {source}", cmd)

            cmd = ["git", "-C", path, "merge", f"origin/{source}", "--no-edit"]
            dialog = CommandOutputDialog(self, f"Merge from {source}", cmd)
            dialog.exec()
        self.show_window()

    def git_push(self, path: str):
        """Git push in worktree"""
        logger.info("git_push: path=%s", path)
        # Check if upstream is set
        result = subprocess.run(
            ["git", "-C", path, "rev-parse", "--abbrev-ref", "--symbolic-full-name", "@{u}"],
            capture_output=True, text=True
        )
        if result.returncode != 0:
            # No upstream - get current branch and set upstream
            branch_result = subprocess.run(
                ["git", "-C", path, "rev-parse", "--abbrev-ref", "HEAD"],
                capture_output=True, text=True
            )
            branch = branch_result.stdout.strip()
            cmd = ["git", "-C", path, "push", "--set-upstream", "origin", branch]
        else:
            cmd = ["git", "-C", path, "push"]
        self.run_command_dialog("Git Push", cmd)

    def git_pull(self, path: str):
        """Git pull in worktree"""
        logger.info("git_pull: path=%s", path)
        cmd = ["git", "-C", path, "pull"]
        self.run_command_dialog("Git Pull", cmd)

    def git_fetch(self, path: str):
        """Git fetch in worktree"""
        logger.info("git_fetch: path=%s", path)
        cmd = ["git", "-C", path, "fetch"]
        self.run_command_dialog("Git Fetch", cmd)

    def create_worktree(self, values: dict):
        """Create worktree with given values"""
        logger.info("create_worktree: project=%s change=%s", values.get("project", ""), values.get("change_id", ""))
        project = values["project"]
        change_id = values["change_id"]
        local_path = values.get("local_path")

        if not change_id:
            show_warning(self, "Error", "Change ID is required")
            return

        # Get project path to run set-new from correct directory
        cwd = None
        project_path = local_path  # Use local path if provided

        if not project_path:
            # Try to get from config
            try:
                config_path = CONFIG_DIR / "projects.json"
                if config_path.exists():
                    with open(config_path) as f:
                        data = json.load(f)
                        project_path = data.get("projects", {}).get(project, {}).get("path")
            except Exception:
                pass

        if project_path:
            cwd = str(Path(project_path).parent)

        if local_path:
            cmd = [str(SCRIPT_DIR / "set-new"), change_id]
            cwd = local_path  # Run from the local repo
        else:
            cmd = [str(SCRIPT_DIR / "set-new"), "-p", project, change_id]

        self.run_command_dialog(f"New Worktree: {change_id}", cmd, cwd=cwd)

    def focus_ralph_terminal(self, wt_path: str):
        """Focus the Ralph terminal window, or open log if terminal is closed"""
        loop_state_file = Path(wt_path) / ".set" / "loop-state.json"
        if not loop_state_file.exists():
            return

        try:
            with open(loop_state_file) as f:
                state = json.load(f)

            plat = get_platform()

            # Primary: use Ralph loop PID + PPID chain to find terminal window
            ralph_pid = state.get("pid")
            if ralph_pid:
                result = plat.find_window_by_pid(int(ralph_pid))
                if result:
                    window_id, proc_name = result
                    plat.focus_window(window_id, app_name=proc_name)
                    return

            # Fallback: title-based search
            worktree_name = state.get("worktree_name", "")
            if worktree_name:
                window_id = plat.find_window_by_title(f"Ralph: {worktree_name}")
                if window_id:
                    plat.focus_window(window_id)
                    return

            # Terminal not found - open log file instead
            self.view_ralph_log(wt_path)
        except Exception:
            pass

    def view_ralph_log(self, wt_path: str):
        """Open Ralph log file in a viewer"""
        log_file = Path(wt_path) / ".claude" / "ralph-loop.log"
        if log_file.exists():
            # Try to open with system default application
            platform = get_platform()
            if not platform.open_file(str(log_file)):
                # Fallback: show in a dialog
                try:
                    content = log_file.read_text()[-50000:]  # Last 50k chars
                    self.hide()
                    dialog = QDialog(self)
                    dialog.setWindowTitle("Ralph Loop Log")
                    dialog.setWindowFlags(dialog.windowFlags() | Qt.WindowStaysOnTopHint)
                    dialog.resize(800, 600)
                    layout = QVBoxLayout(dialog)
                    text = QTextEdit()
                    text.setPlainText(content)
                    text.setReadOnly(True)
                    text.moveCursor(text.textCursor().End)
                    layout.addWidget(text)
                    dialog.exec()
                    self.show()
                except Exception:
                    pass
        else:
            show_information(self, "No Log", "No Ralph log file found.")

    def stop_ralph_loop(self, wt_path: str):
        """Stop Ralph loop for a worktree"""
        loop_state_file = Path(wt_path) / ".set" / "loop-state.json"
        if loop_state_file.exists():
            try:
                with open(loop_state_file) as f:
                    state = json.load(f)
                state["status"] = "stopped"
                with open(loop_state_file, 'w') as f:
                    json.dump(state, f, indent=2)

                # Also try to kill terminal process
                pid_file = Path(wt_path) / ".claude" / "ralph-terminal.pid"
                if pid_file.exists():
                    with open(pid_file) as f:
                        pid = f.read().strip()
                    subprocess.run(["kill", pid], check=False, capture_output=True)
                    pid_file.unlink(missing_ok=True)
            except Exception:
                pass

    def _auto_scan_chrome(self):
        """Auto-scan Chrome sessions on startup (silent — no dialogs)."""
        from ...workers.chrome_cookies import is_pycookiecheat_available, ChromeScanWorker
        from ...workers.usage import load_accounts

        if not is_pycookiecheat_available():
            logger.info("auto-scan: pycookiecheat not available")
            return

        if hasattr(self, '_chrome_scan_worker') and self._chrome_scan_worker.isRunning():
            logger.debug("auto-scan: scan already in progress")
            return

        existing = load_accounts()
        self._chrome_scan_worker = ChromeScanWorker(force_refresh=False, existing_accounts=existing)
        self._chrome_scan_worker.scan_finished.connect(self._on_auto_scan_finished)
        self._chrome_scan_worker.scan_error.connect(self._on_auto_scan_error)
        self._chrome_scan_worker.start()

    @log_exceptions
    def _on_auto_scan_finished(self, sessions):
        """Handle auto-scan results (silent)."""
        from ...workers.chrome_cookies import merge_scan_results
        from ...workers.usage import load_accounts, save_accounts

        if not sessions:
            logger.info("auto-scan: no sessions found")
            return

        logger.info("auto-scan: found %d sessions", len(sessions))
        try:
            existing = load_accounts()
            merged = merge_scan_results(sessions, existing)
            save_accounts(merged)
        except Exception as e:
            logger.warning("auto-scan: save failed: %s", e)
            return

        self._restart_usage_worker()

    @log_exceptions
    def _on_auto_scan_error(self, error_msg):
        """Handle auto-scan error (silent)."""
        logger.warning("auto-scan: scan failed: %s", error_msg)

    def on_scan_chrome_sessions(self):
        """Scan Chrome profiles for Claude session cookies and update accounts."""
        from ...workers.chrome_cookies import is_pycookiecheat_available, ChromeScanWorker
        from ...workers.usage import load_accounts

        if not is_pycookiecheat_available():
            show_warning(
                self, "Missing Dependency",
                "pycookiecheat is not installed.\n\n"
                "Install it with:\n"
                "  pip install pycookiecheat"
            )
            return

        if hasattr(self, '_chrome_scan_worker') and self._chrome_scan_worker.isRunning():
            logger.debug("manual-scan: scan already in progress")
            return

        existing = load_accounts()
        self._chrome_scan_worker = ChromeScanWorker(force_refresh=True, existing_accounts=existing)
        self._chrome_scan_worker.scan_finished.connect(self._on_manual_scan_finished)
        self._chrome_scan_worker.scan_error.connect(self._on_manual_scan_error)
        self._chrome_scan_worker.start()

    @log_exceptions
    def _on_manual_scan_finished(self, sessions):
        """Handle manual scan results (show dialog)."""
        from ...workers.chrome_cookies import merge_scan_results
        from ...workers.usage import load_accounts, save_accounts

        if not sessions:
            show_information(
                self, "Scan Chrome Sessions",
                "No Chrome profiles with Claude sessions found."
            )
            return

        names = [s["name"] for s in sessions]
        try:
            existing = load_accounts()
            merged = merge_scan_results(sessions, existing)
            save_accounts(merged)
        except Exception as e:
            show_warning(self, "Error", f"Failed to save accounts: {e}")
            return

        self._restart_usage_worker()
        show_information(
            self, "Scan Chrome Sessions",
            f"Found {len(sessions)} account(s):\n" + "\n".join(f"  - {n}" for n in names)
        )

    @log_exceptions
    def _on_manual_scan_error(self, error_msg):
        """Handle manual scan error (show dialog)."""
        show_warning(self, "Scan Error", f"Failed to scan Chrome sessions: {error_msg}")

    def show_add_account(self):
        """Show dialog to add a new Claude account"""
        from ...workers.usage import load_accounts, save_accounts

        self.hide()
        name, ok = get_text(
            self, "Add Account",
            "Account name (e.g. Personal, Work):",
        )
        if not ok or not name.strip():
            self.show_window()
            return

        key, ok2 = get_text(
            self, "Add Account",
            f"Session key for '{name.strip()}':\n"
            "(F12 → Application → Cookies → claude.ai → sessionKey)",
        )
        if ok2 and key.strip():
            accounts = load_accounts()
            accounts.append({"name": name.strip(), "sessionKey": key.strip(), "source": "manual"})
            try:
                save_accounts(accounts)
            except Exception as e:
                show_warning(self, "Error", f"Failed to save account: {e}")
                self.show_window()
                return
            self._restart_usage_worker()
        self.show_window()

    def show_remove_account(self):
        """Show dialog to remove a Claude account"""
        from ...workers.usage import load_accounts, save_accounts
        from ...dialogs.helpers import get_item

        accounts = load_accounts()
        if len(accounts) <= 1:
            return

        names = [a["name"] for a in accounts]
        self.hide()
        chosen, ok = get_item(
            self, "Remove Account",
            "Select account to remove:",
            names, 0, False,
        )
        if ok and chosen:
            accounts = [a for a in accounts if a["name"] != chosen]
            try:
                save_accounts(accounts)
            except Exception as e:
                show_warning(self, "Error", f"Failed to remove account: {e}")
                self.show_window()
                return
            self._restart_usage_worker()
        self.show_window()

    def show_claude_usage(self):
        """Open Claude usage page in default browser"""
        webbrowser.open("https://claude.ai/settings/usage")

    def _restart_usage_worker(self):
        """Restart usage worker to pick up new session key"""
        from ...workers import UsageWorker
        self.usage_worker.stop()
        self.usage_worker.wait(500)
        self.usage_worker = UsageWorker(config=self.config)
        self.usage_worker.usage_updated.connect(self.update_usage)
        self.usage_worker.start()

    def get_selected_worktree(self):
        """Get currently selected worktree data (skips header rows)"""
        row = self.table.currentRow()
        if row >= 0 and hasattr(self, 'row_to_worktree'):
            return self.row_to_worktree.get(row)
        return None

    def get_selected_agent(self):
        """Get the agent data for the currently selected row."""
        row = self.table.currentRow()
        if row >= 0 and hasattr(self, 'row_to_agent'):
            return self.row_to_agent.get(row, {})
        return {}

    @log_exceptions
    def on_double_click(self, _index=None):
        """Handle double-click on row - focus IDE window if open, otherwise open via set-work"""
        wt = self.get_selected_worktree()
        if not wt:
            logger.debug("on_double_click: no worktree selected")
            return

        project = wt.get('project', '')
        change_id = wt.get('change_id', '')
        wt_path = wt.get("path", "")
        logger.info("on_double_click: project=%s change=%s path=%s", project, change_id, wt_path)

        key = f"{project}:{change_id}"
        if key in self.needs_attention:
            self.needs_attention.discard(key)
            self.save_state()
        # Clear row background
        row = self.table.currentRow()
        self._set_row_background(row, QColor("transparent"))

        # Check if window exists for this worktree
        if wt_path:
            plat = get_platform()

            # Primary: title-based search (reliable for multi-window IDEs like Zed)
            # Never use exact match — Zed appends " — filename" to the title
            wt_basename = Path(wt_path).name
            app_name = self._get_editor_app_name()
            title_wid = plat.find_window_by_title(wt_basename, app_name=app_name)
            if title_wid:
                logger.info("on_double_click: found window by title=%r, focusing", title_wid)
                plat.focus_window(title_wid, app_name=app_name)
                return

            # Fallback: per-agent window_id, then worktree-level
            agent = self.get_selected_agent()
            window_id = agent.get("window_id") or wt.get("window_id")
            editor_type = agent.get("editor_type") or wt.get("editor_type") or ""
            if window_id:
                logger.info("on_double_click: focusing window_id=%s editor=%s", window_id, editor_type)
                plat.focus_window(str(window_id), app_name=editor_type)
                return

        # No window found — open via editor CLI
        if wt_path:
            cmd = self._get_editor_open_command(wt_path)
        else:
            cmd = [str(SCRIPT_DIR / "set-work"), "-p", wt["project"], wt["change_id"]]
        logger.info("on_double_click: opening editor cmd=%s", cmd)
        subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

    def _get_editor_open_command(self, wt_path: str) -> list:
        """Get the editor CLI command to open a worktree directory.

        Reads from set-core config. Returns a command list for subprocess.
        Falls back to opening with the default editor (zed or code).
        """
        # Editor commands for opening a directory
        # Zed on Linux needs -n to open a new window; on macOS it does this automatically
        ide_commands = {
            "zed": ["zed", "-n"],
            "vscode": ["code"],
            "cursor": ["cursor"],
            "windsurf": ["windsurf"],
        }
        terminal_commands = {
            "kitty": ["kitty", "--directory"],
            "alacritty": ["alacritty", "--working-directory"],
            "wezterm": ["wezterm", "start", "--cwd"],
            "gnome-terminal": ["gnome-terminal", "--working-directory"],
            "konsole": ["konsole", "--workdir"],
            "iterm2": ["open", "-a", "iTerm"],
            "terminal-app": ["open", "-a", "Terminal"],
        }
        import shutil
        import os

        def _find_binary(name):
            """Find binary, also searching Homebrew paths not in GUI app PATH."""
            found = shutil.which(name)
            if found:
                return found
            for extra in ["/opt/homebrew/bin", "/usr/local/bin"]:
                candidate = os.path.join(extra, name)
                if os.path.isfile(candidate) and os.access(candidate, os.X_OK):
                    return candidate
            return name  # fallback to bare name

        try:
            config_path = CONFIG_DIR / "config.json"
            if config_path.exists():
                with open(config_path) as f:
                    data = json.load(f)
                name = data.get("editor", {}).get("name", "auto")
                if name != "auto":
                    if name in ide_commands:
                        cmd = ide_commands[name]
                        binary = _find_binary(cmd[0])
                        return [binary] + cmd[1:] + [wt_path]
                    if name in terminal_commands:
                        cmd = terminal_commands[name]
                        binary = _find_binary(cmd[0])
                        return [binary] + cmd[1:] + [wt_path]
        except Exception:
            pass
        # Default: try zed, then code
        zed = _find_binary("zed")
        if os.path.isabs(zed):
            return [zed, "-n", wt_path]
        code = _find_binary("code")
        if os.path.isabs(code):
            return [code, wt_path]
        return ["xdg-open", wt_path]

    def _get_editor_app_name(self) -> str:
        """Get the editor application name for window matching.

        Reads from set-core config, defaults to 'Zed'.
        """
        # Map config names to macOS/System Events process names
        editor_process_names = {
            "zed": "Zed",
            "vscode": "Code",
            "cursor": "Cursor",
            "windsurf": "Windsurf",
        }
        try:
            config_path = CONFIG_DIR / "config.json"
            if config_path.exists():
                with open(config_path) as f:
                    data = json.load(f)
                name = data.get("editor", {}).get("name", "auto")
                if name != "auto" and name in editor_process_names:
                    return editor_process_names[name]
        except Exception:
            pass
        return "Zed"

    @log_exceptions
    def on_focus(self):
        """Focus the selected worktree's editor window, or open it if not found"""
        wt = self.get_selected_worktree()
        if not wt:
            return

        wt_path = wt.get("path", "")
        if not wt_path:
            return

        logger.info("on_focus: project=%s change=%s", wt.get("project", ""), wt.get("change_id", ""))
        plat = get_platform()

        # Known IDE process names (from PPID chain detection)
        _IDE_TYPES = {"zed", "Zed", "code", "Code", "cursor", "Cursor", "windsurf", "Windsurf"}

        # Per-agent window info (preferred), with worktree-level fallback
        agent = self.get_selected_agent()
        editor_type = agent.get("editor_type") or wt.get("editor_type") or ""
        window_id = agent.get("window_id") or wt.get("window_id")

        # If editor_type is a terminal (not IDE), skip title search — go straight to window_id
        if editor_type and editor_type not in _IDE_TYPES and window_id:
            logger.info("on_focus: terminal editor=%s window_id=%s", editor_type, window_id)
            plat.focus_window(str(window_id), app_name=editor_type)
            return

        # Primary: title-based search (reliable for multi-window IDEs like Zed)
        # Never use exact match — Zed appends " — filename" to the title
        wt_basename = Path(wt_path).name
        app_name = self._get_editor_app_name()
        title_wid = plat.find_window_by_title(wt_basename, app_name=app_name)
        if title_wid:
            logger.info("on_focus: found window by title=%r, focusing", title_wid)
            plat.focus_window(title_wid, app_name=app_name)
            return

        # Fallback: window_id from status data (PPID chain detection)
        if window_id:
            logger.info("on_focus: focusing window_id=%s editor=%s", window_id, editor_type)
            plat.focus_window(str(window_id), app_name=editor_type)
            return

        # No window found — open via editor CLI
        cmd = self._get_editor_open_command(wt_path)
        logger.info("on_focus: opening editor cmd=%s", cmd)
        subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

    @log_exceptions
    def on_close_editor(self):
        """Close the selected worktree's editor window (silent no-op if not found)"""
        wt = self.get_selected_worktree()
        if not wt:
            return

        wt_path = wt.get("path", "")
        if not wt_path:
            return

        logger.info("on_close_editor: project=%s change=%s", wt.get("project", ""), wt.get("change_id", ""))
        plat = get_platform()

        # Primary: title-based search (reliable for multi-window IDEs like Zed)
        wt_basename = Path(wt_path).name
        app_name = self._get_editor_app_name()
        title_wid = plat.find_window_by_title(wt_basename, app_name=app_name)
        if title_wid:
            logger.info("on_close_editor: closing window title=%r", title_wid)
            plat.close_window(title_wid, app_name=app_name)
            return

        # Fallback: per-agent window_id, then worktree-level
        agent = self.get_selected_agent()
        window_id = agent.get("window_id") or wt.get("window_id")
        editor_type = agent.get("editor_type") or wt.get("editor_type") or ""
        if window_id:
            logger.info("on_close_editor: closing window_id=%s", window_id)
            plat.close_window(str(window_id), app_name=editor_type)

    @log_exceptions
    def on_new(self, preset_project: str = None):
        """Create a new worktree using the NewWorktreeDialog"""
        logger.info("on_new: preset_project=%s", preset_project)
        self.hide()
        dialog = NewWorktreeDialog(self, preset_project)
        result = dialog.exec()
        self.show_window()

        if result == QDialog.Accepted:
            self.create_worktree(dialog.get_values())

    @log_exceptions
    def on_work(self):
        """Show dialog to select and open a worktree"""
        logger.info("on_work")
        self.hide()

        # Get currently open worktrees
        open_wts = [f"{wt.get('project', '')}:{wt.get('change_id', '')}" for wt in self.worktrees]

        dialog = WorkDialog(self, open_wts)
        result = dialog.exec()

        if result == QDialog.Accepted:
            selection = dialog.get_selection()
            if selection:
                # Run set-work in background without dialog
                cmd = [str(SCRIPT_DIR / "set-work"), "-p", selection["project"], selection["change_id"]]
                subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        self.show_window()

    @log_exceptions
    def on_add(self):
        """Add an existing git repository or worktree using folder browser"""
        logger.info("on_add")
        self.hide()

        folder = get_existing_directory(
            self,
            "Select Git Repository",
            str(Path.home()),
            QFileDialog.ShowDirsOnly
        )

        if folder:
            cmd = [str(SCRIPT_DIR / "wt-add"), folder]
            dialog = CommandOutputDialog(self, "Adding repository", cmd)
            dialog.exec()
            self.refresh_status()

        self.show()

    @log_exceptions
    def on_close(self):
        """Close the selected worktree"""
        wt = self.get_selected_worktree()
        if not wt:
            return
        logger.info("on_close: project=%s change=%s", wt.get("project", ""), wt.get("change_id", ""))

        from PySide6.QtWidgets import QMessageBox
        reply = show_question(
            self, "Close Worktree",
            f"Close worktree '{wt['change_id']}'?",
            QMessageBox.Yes | QMessageBox.No
        )
        if reply == QMessageBox.Yes:
            cmd = [str(SCRIPT_DIR / "set-close"), "-p", wt["project"], wt["change_id"], "--force"]
            self.run_command_dialog(f"Closing {wt['change_id']}", cmd)
            self.refresh_status()

    def show_memory_browse_dialog(self, project: str):
        """Open the memory browse dialog for a project"""
        self.hide()
        dialog = MemoryBrowseDialog(self, project)
        dialog.exec()
        self.show()

    def show_remember_note_dialog(self, project: str):
        """Open the remember note dialog for a project"""
        self.hide()
        dialog = RememberNoteDialog(self, project)
        dialog.exec()
        self.show()
