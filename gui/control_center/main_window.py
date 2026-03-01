"""
Control Center Main Window - Main application window class
"""

import json
import math
import os
import subprocess
import sys
from pathlib import Path

from PySide6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QTableWidget, QHeaderView, QPushButton, QLabel,
    QMenu, QSystemTrayIcon, QApplication
)
from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QColor, QFont, QAction, QIcon, QPixmap, QPainter, QBrush, QGuiApplication

from ..widgets import DualStripeBar

from ..constants import (
    SCRIPT_DIR, CONFIG_DIR, STATE_FILE, COLOR_PROFILES,
    ICON_RUNNING, ICON_WAITING, ICON_IDLE
)
from ..config import Config
from ..utils import get_version
from ..workers import StatusWorker, UsageWorker, TeamWorker, ChatWorker, FeatureWorker
from ..logging_setup import safe_slot
from .mixins import TeamMixin, TableMixin, MenusMixin, HandlersMixin

__all__ = ["ControlCenter"]

VERSION = get_version()


class ControlCenter(QMainWindow, TeamMixin, TableMixin, MenusMixin, HandlersMixin):
    """Main control center window"""

    STATUS_ICONS = {
        "running": ("●", QColor("#22c55e")),
        "waiting": ("⚡", QColor("#f59e0b")),
        "idle": ("○", QColor("#6b7280")),
        "done": ("✓", QColor("#3b82f6")),
    }

    TRAY_COLORS = {
        "running": "#22c55e",
        "waiting": "#f59e0b",
        "idle": "#6b7280",
    }

    @property
    def POSITION_FILE(self):
        return CONFIG_DIR / "gui-position.json"

    def __init__(self):
        super().__init__()

        # Load configuration
        self.config = Config()

        self.setWindowTitle(f"Worktree Control Center [{VERSION}]")
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.Tool)
        self.setFixedWidth(self.config.control_center["window_width"])

        # For drag-to-move
        self._drag_pos = None

        # Store current data
        self.worktrees = []
        self.row_to_worktree = {}
        self.previous_statuses = {}
        self.needs_attention = set()
        self.blink_state = False
        self.pulse_phase = 0.0
        self.running_rows = set()

        # Usage display state (list of per-account dicts)
        self.usage_data = [{"available": False}]
        self.account_widgets = []
        self.wt_summary = {}

        # Team sync state
        self.team_data = {"members": [], "conflicts": [], "initialized": False}
        self.team_filter_state = {}
        self.row_to_team_worktree = {}
        self.chat_unread = {}
        self.chat_blink_state = False

        # Feature cache (memory + openspec status per project, from FeatureWorker)
        self._feature_cache = {}

        # Active filter state (show only worktrees with open editor)
        self.filter_active = False

        # Ensure opaque rendering (prevents transparency artifacts on Linux X11)
        self.setAttribute(Qt.WA_StyledBackground, True)

        # Setup UI
        self.setup_ui()
        self.setup_tray()
        self.setup_worker()
        self.setup_blink_timer()
        self.setup_pulse_timer()
        self.setup_usage_worker()
        self.setup_team_worker()
        self.setup_chat_worker()
        self.setup_feature_worker()
        self.setup_always_on_top_timer()

        # Apply color theme
        self.apply_theme()

        # Restore saved position or default to top-right
        self.restore_position()

        # Load persisted state
        self.load_state()

        # Set default transparency
        self.setWindowOpacity(self.config.control_center["opacity_default"])

        # Initial status check
        self.refresh_status()

    def get_color(self, name: str) -> str:
        """Get color from active profile"""
        profile = self.config.control_center.get("color_profile", "light")
        return COLOR_PROFILES.get(profile, COLOR_PROFILES["light"]).get(name, "#000000")

    def apply_theme(self):
        """Apply current color profile to window"""
        bg = self.get_color("bg_dialog")
        text = self.get_color("row_idle_text")
        muted = self.get_color("text_muted")

        self.setStyleSheet(f"""
            QMainWindow {{ background-color: {bg}; }}
            QWidget {{ background-color: {bg}; color: {text}; }}
            QTableWidget {{ background-color: {bg}; color: {text}; gridline-color: {muted}; }}
            QHeaderView::section {{ background-color: {bg}; color: {text}; }}
            QLabel {{ background-color: transparent; }}
            QPushButton#filterButton:checked {{ background-color: #3b82f6; color: white; border-radius: 4px; }}
        """)

        # Update usage bars if they exist
        if hasattr(self, 'account_widgets'):
            bar_bg = self.get_color("bar_background")
            bar_border = self.get_color("bar_border")
            text_color = self.get_color("text_muted")
            for w in self.account_widgets:
                w["bar_5h"].set_empty(bar_bg, bar_border)
                w["bar_7d"].set_empty(bar_bg, bar_border)
                if w.get("name_label"):
                    w["name_label"].setStyleSheet(f"color: {text_color}; font-size: 10px;")

        # Force status refresh
        if hasattr(self, 'worktrees'):
            self.refresh_status()

    def get_status_icon(self, status: str):
        """Get status icon and color from profile"""
        icons = {"running": "●", "waiting": "⚡", "idle": "○", "done": "✓", "orphan": "⚠", "idle (IDE)": "◇", "orphan (IDE)": "⚠"}
        color_keys = {"running": "status_running", "waiting": "status_waiting",
                      "idle": "status_idle", "done": "status_done",
                      "orphan": "status_orphan", "idle (IDE)": "status_idle_ide", "orphan (IDE)": "status_orphan"}
        icon = icons.get(status, "?")
        color = QColor(self.get_color(color_keys.get(status, "status_idle")))
        return icon, color

    def _format_relative_time(self, iso_timestamp: str) -> str:
        """Format ISO timestamp as relative time"""
        if not iso_timestamp:
            return "unknown"
        try:
            from datetime import datetime, timezone
            ts = iso_timestamp.replace("Z", "+00:00")
            dt = datetime.fromisoformat(ts)
            now = datetime.now(timezone.utc)
            diff = now - dt
            seconds = int(diff.total_seconds())
            if seconds < 60:
                return "just now"
            elif seconds < 3600:
                return f"{seconds // 60} min ago"
            elif seconds < 86400:
                return f"{seconds // 3600}h ago"
            else:
                return f"{seconds // 86400}d ago"
        except Exception:
            return iso_timestamp[:16] if len(iso_timestamp) > 16 else iso_timestamp

    def get_tray_color(self, status: str) -> str:
        """Get tray icon color from profile"""
        color_keys = {"running": "status_running", "waiting": "status_waiting",
                      "idle": "status_idle"}
        return self.get_color(color_keys.get(status, "status_idle"))

    def position_top_right(self):
        """Position window at top-right corner of screen"""
        screen = QGuiApplication.primaryScreen().availableGeometry()
        x = screen.right() - self.width() - 10
        y = screen.top() + 10
        self.move(x, y)

    def restore_position(self):
        """Restore saved window position or default to top-right"""
        try:
            if self.POSITION_FILE.exists():
                with open(self.POSITION_FILE) as f:
                    pos = json.load(f)
                    self.move(pos.get("x", 0), pos.get("y", 0))
                    return
        except Exception:
            pass
        self.position_top_right()

    def save_position(self):
        """Save current window position"""
        try:
            self.POSITION_FILE.parent.mkdir(parents=True, exist_ok=True)
            with open(self.POSITION_FILE, "w") as f:
                json.dump({"x": self.x(), "y": self.y()}, f)
        except Exception:
            pass

    def load_state(self):
        """Load persisted state"""
        try:
            if STATE_FILE.exists():
                with open(STATE_FILE) as f:
                    state = json.load(f)
                    self.needs_attention = set(state.get("needs_attention", []))
                    self.previous_statuses = state.get("previous_statuses", {})
        except Exception:
            pass

    def save_state(self):
        """Save state to file"""
        try:
            STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
            with open(STATE_FILE, "w") as f:
                json.dump({
                    "needs_attention": list(self.needs_attention),
                    "previous_statuses": self.previous_statuses
                }, f)
        except Exception:
            pass

    def adjust_height_to_content(self):
        """Adjust window height to fit the table content"""
        row_count = max(1, self.table.rowCount())
        row_height = self.table.rowHeight(0) if self.table.rowCount() > 0 else 22
        header_height = self.table.horizontalHeader().height()
        table_height = header_height + (row_count * row_height) + row_height // 2 + 12

        usage_rows = max(1, len(self.account_widgets))
        other_height = 125 + (usage_rows - 1) * 14
        total_height = table_height + other_height
        total_height = max(100, min(total_height, 700))

        self.setFixedHeight(total_height)

    def setup_ui(self):
        """Create the main UI"""
        central = QWidget()
        self.setCentralWidget(central)

        font = QFont()
        font.setPointSize(9)
        central.setFont(font)

        layout = QVBoxLayout(central)

        # Status label
        self.status_label = QLabel("Loading...")
        self.status_label.setTextFormat(Qt.RichText)
        self.status_label.setStyleSheet("font-weight: bold; padding: 2px 5px;")
        layout.addWidget(self.status_label)

        # Usage info — dynamic rows, one per account
        self.usage_container = QVBoxLayout()
        self.usage_container.setContentsMargins(0, 0, 0, 0)
        self.usage_container.setSpacing(1)
        layout.addLayout(self.usage_container)
        self._rebuild_usage_rows(1)

        # Team label
        self.team_label = QLabel("")
        self.team_label.setStyleSheet(f"padding: 2px 5px;")
        self.team_label.setVisible(False)
        layout.addWidget(self.team_label)

        # Table
        self.table = QTableWidget()
        self.table.setColumnCount(6)
        self.table.setHorizontalHeaderLabels(["Branch", "PID", "Status", "Skill", "Ctx%", "Extra"])
        self.table.setSelectionBehavior(QTableWidget.SelectRows)
        self.table.setSelectionMode(QTableWidget.SingleSelection)
        self.table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.table.doubleClicked.connect(self.on_double_click)
        self.table.setContextMenuPolicy(Qt.CustomContextMenu)
        self.table.customContextMenuRequested.connect(self.show_row_context_menu)
        self.table.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.table.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.table.verticalHeader().setDefaultSectionSize(22)
        self.table.verticalHeader().setVisible(False)

        header = self.table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.Stretch)
        header.setSectionResizeMode(1, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(2, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(3, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(4, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(5, QHeaderView.ResizeToContents)

        layout.addWidget(self.table)

        # Button bar
        btn_layout = QHBoxLayout()

        self.btn_new = QPushButton("+ New")
        self.btn_new.clicked.connect(self.on_new)
        btn_layout.addWidget(self.btn_new)

        self.btn_work = QPushButton("Work")
        self.btn_work.clicked.connect(self.on_work)
        btn_layout.addWidget(self.btn_work)

        self.btn_add = QPushButton("Add")
        self.btn_add.clicked.connect(self.on_add)
        self.btn_add.setToolTip("Add existing repository or worktree")
        btn_layout.addWidget(self.btn_add)

        version_label = QLabel(f"v{VERSION}")
        version_label.setStyleSheet("color: #6b7280; font-size: 10px;")
        btn_layout.addWidget(version_label)

        btn_layout.addStretch()

        # Active filter toggle button
        self.btn_filter = QPushButton("🖥️")
        self.btn_filter.setObjectName("filterButton")
        self.btn_filter.setFixedWidth(40)
        self.btn_filter.setCheckable(True)
        self.btn_filter.setToolTip("Show only active worktrees")
        self.btn_filter.clicked.connect(self.toggle_active_filter)
        btn_layout.addWidget(self.btn_filter)

        self.btn_minimize = QPushButton("−")
        self.btn_minimize.setFixedWidth(30)
        self.btn_minimize.setToolTip("Minimize to tray")
        self.btn_minimize.clicked.connect(self.hide)
        btn_layout.addWidget(self.btn_minimize)

        self.btn_menu = QPushButton("≡")
        self.btn_menu.setFixedWidth(40)
        self.btn_menu.clicked.connect(self.show_main_menu)
        btn_layout.addWidget(self.btn_menu)

        layout.addLayout(btn_layout)

        self.setContextMenuPolicy(Qt.CustomContextMenu)
        self.customContextMenuRequested.connect(self.show_context_menu)

    def setup_tray(self):
        """Setup system tray icon"""
        self.tray = QSystemTrayIcon(self)
        self.tray.setIcon(self.create_tray_icon(self.get_tray_color("idle")))
        self.tray.setToolTip("Worktree Control Center")

        tray_menu = QMenu()

        show_action = QAction("Show", self)
        show_action.triggered.connect(self.show_window)
        tray_menu.addAction(show_action)

        tray_menu.addSeparator()

        new_action = QAction("New Worktree...", self)
        new_action.triggered.connect(self.on_new)
        tray_menu.addAction(new_action)

        settings_action = QAction("Settings...", self)
        settings_action.triggered.connect(self.open_settings)
        tray_menu.addAction(settings_action)

        tray_menu.addSeparator()

        quit_action = QAction("Quit", self)
        quit_action.triggered.connect(self.quit_app)
        tray_menu.addAction(quit_action)

        self.tray.setContextMenu(tray_menu)
        self.tray.activated.connect(self.on_tray_activated)
        self.tray.show()

    def setup_worker(self):
        """Setup background status polling"""
        self.worker = StatusWorker(self.config)
        self.worker.status_updated.connect(self.update_status)
        self.worker.error_occurred.connect(self.on_error)
        self.worker.start()

    def setup_blink_timer(self):
        """Setup timers for blinking animations"""
        self.blink_timer = QTimer(self)
        self.blink_timer.timeout.connect(self.toggle_blink)
        self.blink_timer.start(self.config.control_center["blink_interval_ms"])

        self.chat_blink_timer = QTimer(self)
        self.chat_blink_timer.timeout.connect(self.toggle_chat_blink)
        self.chat_blink_timer.start(self.config.control_center["blink_interval_ms"] // 3)

    def toggle_chat_blink(self):
        """Fast blink toggle for chat icon"""
        if sum(self.chat_unread.values()) > 0:
            self.chat_blink_state = not self.chat_blink_state
            self._update_chat_button_colors()

    def setup_pulse_timer(self):
        """Setup timer for running row pulse animation"""
        self.pulse_timer = QTimer(self)
        self.pulse_timer.timeout.connect(self.update_pulse)
        self.pulse_timer.start(50)

    def setup_usage_worker(self):
        """Setup background usage data fetching"""
        self.usage_worker = UsageWorker(config=self.config)
        self.usage_worker.usage_updated.connect(self.update_usage)
        self.usage_worker.start()

    def setup_team_worker(self):
        """Setup background team sync"""
        self.team_worker = TeamWorker(self.config)
        self.team_worker.team_updated.connect(self.update_team)
        self.team_worker.error_occurred.connect(self.on_team_error)
        self.team_worker.start()

    def setup_chat_worker(self):
        """Setup background chat polling"""
        self.chat_worker = ChatWorker(self.config)
        self.chat_worker.unread_count_changed.connect(self.update_chat_badge)
        self.chat_worker.start()

    def setup_feature_worker(self):
        """Setup background feature status polling (memory + openspec)"""
        self.feature_worker = FeatureWorker()
        self.feature_worker.features_updated.connect(self.on_features_updated)
        self.feature_worker.start()

    @safe_slot
    def on_features_updated(self, data: dict):
        """Handle feature status update from FeatureWorker"""
        self._feature_cache = data
        self.refresh_table_display()

    def refresh_feature_cache(self):
        """Force an immediate feature cache refresh"""
        if hasattr(self, 'feature_worker'):
            self.feature_worker.refresh_now()

    @safe_slot
    def update_chat_badge(self, unread_count: int):
        """Update chat button with unread count"""
        project = self.get_active_project()
        old_count = self.chat_unread.get(project, 0) if project else 0

        if project:
            self.chat_unread[project] = unread_count

        if project and old_count != unread_count:
            self.refresh_table_display()

    def get_active_project(self):
        """Get project from visible worktrees, fallback to default"""
        if self.worktrees:
            return self.worktrees[0].get("project")
        try:
            config_path = CONFIG_DIR / "projects.json"
            if config_path.exists():
                with open(config_path) as f:
                    data = json.load(f)
                    return data.get("default")
        except Exception:
            pass
        return None

    @safe_slot
    def update_usage(self, data: list):
        """Handle usage data update from worker (list of per-account dicts)"""
        self.usage_data = data if data else [{"available": False}]
        self.update_usage_bars()

    def _rebuild_usage_rows(self, count):
        """Create/destroy usage rows to match account count."""
        # Remove old widgets
        for w in self.account_widgets:
            for key in ("name_label", "label_5h", "bar_5h", "label_7d", "bar_7d"):
                widget = w.get(key)
                if widget:
                    widget.setParent(None)
                    widget.deleteLater()
        # Remove old layouts
        while self.usage_container.count():
            item = self.usage_container.takeAt(0)
            if item.layout():
                # clear child items from the sub-layout
                sub = item.layout()
                while sub.count():
                    sub.takeAt(0)

        self.account_widgets = []
        show_names = count > 1
        label_width = 90
        text_color = self.get_color("text_muted")

        for _ in range(max(count, 1)):
            row_layout = QHBoxLayout()
            row_layout.setContentsMargins(5, 0, 5, 1)
            row_layout.setSpacing(3)

            name_label = None
            if show_names:
                name_label = QLabel("")
                name_label.setFixedWidth(60)
                name_label.setStyleSheet(f"color: {text_color}; font-size: 10px;")
                row_layout.addWidget(name_label)

            label_5h = QLabel("-- \u00b7 --/5h")
            label_5h.setFixedWidth(label_width)
            row_layout.addWidget(label_5h)
            bar_5h = DualStripeBar()
            row_layout.addWidget(bar_5h, 1)

            # Small spacer between 5h and 7d
            row_layout.addSpacing(10)

            label_7d = QLabel("-- \u00b7 --/7d")
            label_7d.setFixedWidth(label_width)
            row_layout.addWidget(label_7d)
            bar_7d = DualStripeBar()
            row_layout.addWidget(bar_7d, 1)

            self.usage_container.addLayout(row_layout)
            self.account_widgets.append({
                "name_label": name_label,
                "label_5h": label_5h,
                "bar_5h": bar_5h,
                "label_7d": label_7d,
                "bar_7d": bar_7d,
            })

    def update_usage_bars(self):
        """Update the compact dual-stripe bars and combined labels for all accounts"""
        data_list = self.usage_data if isinstance(self.usage_data, list) else [self.usage_data]

        # Rebuild rows if count changed
        if len(data_list) != len(self.account_widgets):
            self._rebuild_usage_rows(len(data_list))

        bg = self.get_color("bar_background")
        border = self.get_color("bar_border")

        for i, account_data in enumerate(data_list):
            if i >= len(self.account_widgets):
                break
            w = self.account_widgets[i]

            # Set account name
            if w.get("name_label"):
                w["name_label"].setText(account_data.get("name", "")[:10])

            if not account_data.get("available"):
                w["bar_5h"].set_empty(bg, border)
                w["bar_7d"].set_empty(bg, border)
                w["label_5h"].setText("-- \u00b7 --/5h")
                w["label_7d"].setText("-- \u00b7 --/7d")
                w["label_5h"].setToolTip(
                    account_data.get("name", "") + "\nAdd account session key for usage data"
                    if account_data.get("name") else ""
                )
                w["label_7d"].setToolTip("")
                continue

            is_estimated = account_data.get("is_estimated", False)

            if is_estimated:
                w["bar_5h"].set_empty(bg, border)
                w["bar_7d"].set_empty(bg, border)
                w["label_5h"].setText("-- \u00b7 --/5h")
                w["label_7d"].setText("-- \u00b7 --/7d")
                session_tokens = account_data.get("session_tokens", 0)
                weekly_tokens = account_data.get("weekly_tokens", 0)
                w["label_5h"].setToolTip(
                    f"~{session_tokens/1000:.0f}k tokens in last 5h\n"
                    "Add account session key for exact usage %"
                )
                w["label_7d"].setToolTip(
                    f"~{weekly_tokens/1000:.0f}k tokens in last 7d\n"
                    "Add account session key for exact usage %"
                )
                continue

            # API data: show combined labels and dual-stripe bars
            session_pct = account_data.get("session_pct", 0)
            session_reset = account_data.get("session_reset")
            session_remaining = self.calc_time_remaining(session_reset)
            session_time_pct = self.calc_time_elapsed_pct(session_reset, 5)

            time_5h = session_remaining or "5h"
            w["label_5h"].setText(f"{time_5h} \u00b7 {session_pct:.0f}%")

            name_prefix = f"{account_data.get('name', '')}: " if account_data.get("name") else ""
            w["label_5h"].setToolTip(
                f"{name_prefix}5h window: {session_time_pct:.0f}% elapsed, {session_pct:.0f}% used"
            )

            time_color = self.get_color("bar_time")
            usage_5h_color = self._burn_rate_color(session_pct, session_time_pct)
            w["bar_5h"].set_colors(time_color, usage_5h_color, bg, border)
            w["bar_5h"].set_values(session_time_pct, session_pct)

            if account_data.get("has_weekly", True):
                weekly_pct = account_data.get("weekly_pct", 0)
                weekly_reset = account_data.get("weekly_reset")
                weekly_remaining = self.calc_time_remaining(weekly_reset)
                weekly_time_pct = self.calc_time_elapsed_pct(weekly_reset, 168)

                time_7d = weekly_remaining or "7d"
                w["label_7d"].setText(f"{time_7d} \u00b7 {weekly_pct:.0f}%")
                w["label_7d"].setToolTip(
                    f"{name_prefix}7d window: {weekly_time_pct:.0f}% elapsed, {weekly_pct:.0f}% used"
                )
                usage_7d_color = self._burn_rate_color(weekly_pct, weekly_time_pct)
                w["bar_7d"].set_colors(time_color, usage_7d_color, bg, border)
                w["bar_7d"].set_values(weekly_time_pct, weekly_pct)
            else:
                w["label_7d"].setText("-")
                w["label_7d"].setToolTip(f"{name_prefix}No weekly limit")
                w["bar_7d"].set_empty(bg, border)

    def calc_time_remaining(self, reset_time_str):
        """Calculate time remaining until reset"""
        try:
            from datetime import datetime, timezone
            if not reset_time_str:
                return None

            reset_time = datetime.fromisoformat(reset_time_str.replace('Z', '+00:00'))
            now = datetime.now(timezone.utc)
            remaining = reset_time - now

            if remaining.total_seconds() <= 0:
                return None

            hours = int(remaining.total_seconds() // 3600)
            minutes = int((remaining.total_seconds() % 3600) // 60)

            if hours >= 24:
                days = hours // 24
                hours = hours % 24
                return f"{days}d {hours}h"
            elif hours > 0:
                return f"{hours}h {minutes}m"
            else:
                return f"{minutes}m"
        except Exception:
            return None

    def update_combined_status(self):
        """Update status line with worktree info only"""
        total = self.wt_summary.get("total", 0)
        running = self.wt_summary.get("running", 0)
        waiting = self.wt_summary.get("waiting", 0)
        idle = self.wt_summary.get("idle", 0)

        parts = [f"Worktrees: {total}"]
        if running > 0:
            parts.append(f"<span style='color: {self.get_color('status_running')};'>●{running} running</span>")
        if waiting > 0:
            parts.append(f"<span style='color: {self.get_color('status_waiting')};'>⚡{waiting} waiting</span>")
        if idle > 0:
            parts.append(f"○{idle} idle")

        self.status_label.setText(" | ".join(parts))

    def calc_time_elapsed_pct(self, reset_time_str, window_hours):
        """How far through the time window are we? 0% = just reset, 100% = about to reset."""
        try:
            from datetime import datetime, timezone, timedelta
            if not reset_time_str:
                return 0
            reset = datetime.fromisoformat(reset_time_str.replace('Z', '+00:00'))
            now = datetime.now(timezone.utc)
            window = timedelta(hours=window_hours)
            window_start = reset - window
            elapsed = (now - window_start).total_seconds()
            return min(max(elapsed / window.total_seconds() * 100, 0), 100)
        except Exception:
            return 0

    def _burn_rate_color(self, usage_pct, time_pct=None):
        """Return burn-rate-relative color string for usage stripe.

        Binary: green if under budget, red if at/over budget.
        """
        if time_pct is not None:
            if usage_pct < time_pct:
                return self.get_color("burn_low")
            else:
                return self.get_color("burn_high")
        else:
            if usage_pct < 80:
                return self.get_color("burn_low")
            else:
                return self.get_color("burn_high")

    def toggle_blink(self):
        """Toggle blink state and update rows that need attention"""
        self.blink_state = not self.blink_state

        if not self.needs_attention:
            return

        for row, wt in self.row_to_worktree.items():
            key = f"{wt.get('project', '')}:{wt.get('change_id', '')}"
            if key in self.needs_attention:
                bg_color = self.get_color("row_waiting_blink") if self.blink_state else "transparent"
                self._set_row_background(row, QColor(bg_color))

    def create_tray_icon(self, color: str) -> QIcon:
        """Create a colored circle icon for system tray"""
        size = 22
        pixmap = QPixmap(size, size)
        pixmap.fill(Qt.transparent)

        painter = QPainter(pixmap)
        painter.setRenderHint(QPainter.Antialiasing)
        painter.setBrush(QBrush(QColor(color)))
        painter.setPen(Qt.NoPen)
        painter.drawEllipse(2, 2, size - 4, size - 4)
        painter.end()

        return QIcon(pixmap)

    def update_tray_icon(self, running: int, waiting: int):
        """Update tray icon color based on status"""
        if running > 0:
            color = self.get_tray_color("running")
        elif waiting > 0:
            color = self.get_tray_color("waiting")
        else:
            color = self.get_tray_color("idle")

        self.tray.setIcon(self.create_tray_icon(color))

    def refresh_status(self):
        """Force a status refresh"""
        try:
            result = subprocess.run(
                [str(SCRIPT_DIR / "wt-status"), "--json"],
                capture_output=True,
                text=True,
                timeout=30
            )
            if result.returncode == 0:
                data = json.loads(result.stdout)
                self.update_status(data)
        except Exception as e:
            self.on_error(str(e))

    @safe_slot
    def update_status(self, data: dict):
        """Update the UI with new status data"""
        new_worktrees = data.get("worktrees", [])
        summary = data.get("summary", {})

        self.check_status_changes(new_worktrees)
        self.worktrees = new_worktrees

        # Update FeatureWorker with current project→repo mapping
        if hasattr(self, 'feature_worker'):
            projects = {}
            for wt in new_worktrees:
                proj = wt.get("project", "")
                if proj and proj not in projects:
                    projects[proj] = wt.get("path", "")
            self.feature_worker.set_projects(projects)

        self.wt_summary = summary
        self.update_combined_status()

        total = summary.get("total", 0)
        running = summary.get("running", 0)
        waiting = summary.get("waiting", 0)

        self.update_tray_icon(running, waiting)
        tooltip_parts = [f"wt: {total}", f"●{running}"]
        tooltip_parts.extend([f"⚡{waiting}", f"○{summary.get('idle', 0)}"])
        self.tray.setToolTip(" | ".join(tooltip_parts))

        self.refresh_table_display()

    def check_status_changes(self, new_worktrees: list):
        """Check for agent status changes and show notifications"""
        for wt in new_worktrees:
            key = f"{wt.get('project', '')}:{wt.get('change_id', '')}"
            agents = wt.get("agents", [])
            # Aggregate status: if any agent is running, worktree is running
            if any(a.get("status") == "running" for a in agents):
                new_status = "running"
            elif any(a.get("status") == "waiting" for a in agents):
                new_status = "waiting"
            else:
                new_status = "idle"
            old_status = self.previous_statuses.get(key)

            if old_status == "running" and new_status == "waiting":
                if self.config.notifications["enabled"]:
                    self.tray.showMessage(
                        "Agent Finished",
                        f"{wt.get('project', '')} / {wt.get('change_id', '')} - needs attention",
                        QSystemTrayIcon.Information,
                        5000
                    )
                self.needs_attention.add(key)

            if new_status == "running" and key in self.needs_attention:
                self.needs_attention.discard(key)

            self.previous_statuses[key] = new_status

        self.save_state()

    def on_error(self, message: str):
        """Handle errors from worker"""
        self.status_label.setText(f"Error: {message}")

    def mousePressEvent(self, event):
        """Start drag on mouse press"""
        if event.button() == Qt.LeftButton:
            self._drag_pos = event.globalPosition().toPoint() - self.frameGeometry().topLeft()
            event.accept()

    def mouseMoveEvent(self, event):
        """Move window during drag"""
        if event.buttons() == Qt.LeftButton and self._drag_pos is not None:
            self.move(event.globalPosition().toPoint() - self._drag_pos)
            event.accept()

    def mouseReleaseEvent(self, event):
        """End drag on mouse release"""
        self._drag_pos = None
        self.save_position()

    def on_tray_activated(self, reason):
        """Handle tray icon activation"""
        if reason == QSystemTrayIcon.Trigger:
            self.show_window()

    def show_window(self):
        """Show and raise the window, ensuring always-on-top on macOS"""
        # Reapply window flags to ensure always-on-top
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.Tool)
        self.show()
        self.raise_()
        self.activateWindow()
        # Re-apply macOS native window setup after show
        if sys.platform == "darwin":
            QTimer.singleShot(50, self._setup_macos_always_on_top)
        # Use timer to ensure focus after dialog closes (macOS needs this)
        QTimer.singleShot(100, self._ensure_focus)

    def _ensure_focus(self):
        """Ensure window has focus (called after short delay)"""
        self.raise_()
        self.activateWindow()

    def setup_always_on_top_timer(self):
        """Setup native always-on-top for macOS using window level"""
        import sys
        if sys.platform == "darwin":
            # Schedule initial setup after Qt creates native window
            QTimer.singleShot(100, self._setup_macos_always_on_top)
            # Event-driven: re-enforce level when app activation changes
            from PySide6.QtWidgets import QApplication
            QApplication.instance().applicationStateChanged.connect(
                self._on_app_state_changed
            )
            # Backup: periodic level check every 5s
            self._level_enforce_timer = QTimer(self)
            self._level_enforce_timer.timeout.connect(self._enforce_native_level)
            self._level_enforce_timer.start(5000)

    def _get_ns_window(self):
        """Get the NSWindow for this Qt window"""
        try:
            from ctypes import c_void_p
            import objc
            win_id = self.winId()
            if win_id:
                ns_view = objc.objc_object(c_void_p=c_void_p(int(win_id)))
                if ns_view and hasattr(ns_view, 'window'):
                    return ns_view.window()
        except Exception as e:
            if not getattr(self, '_ns_window_warn_shown', False):
                print(f"[AlwaysOnTop] Cannot access NSWindow: {e}")
                print("[AlwaysOnTop] Install pyobjc-framework-Cocoa for macOS always-on-top support")
                self._ns_window_warn_shown = True
        return None

    def _setup_macos_always_on_top(self):
        """Configure NSWindow for always-on-top behavior"""
        ns_window = self._get_ns_window()
        if not ns_window:
            return

        try:
            # NSWindowCollectionBehavior flags
            NSWindowCollectionBehaviorCanJoinAllSpaces = 1 << 0
            NSWindowCollectionBehaviorStationary = 1 << 4
            NSWindowCollectionBehaviorIgnoresCycle = 1 << 6

            # Set collection behavior - appear on all spaces, stationary
            # Note: fullscreen Spaces are a macOS platform limitation —
            # no window level or behavior flag can penetrate them
            behavior = (NSWindowCollectionBehaviorCanJoinAllSpaces |
                       NSWindowCollectionBehaviorStationary |
                       NSWindowCollectionBehaviorIgnoresCycle)
            ns_window.setCollectionBehavior_(behavior)

            # NSStatusWindowLevel (25): above normal (0) and floating (3) windows,
            # but below popup menus (101) so QMenu/QDialog appear correctly above CC
            ns_window.setLevel_(25)  # NSStatusWindowLevel
            ns_window.setHidesOnDeactivate_(False)

            print(f"[AlwaysOnTop] Setup complete: level={ns_window.level()}, behavior={behavior}")
        except Exception as e:
            print(f"[AlwaysOnTop] Setup error: {e}")

    def _enforce_native_level(self):
        """Check and correct NSWindow level if Qt6 has reset it"""
        ns_window = self._get_ns_window()
        if ns_window and ns_window.level() != 25:
            ns_window.setLevel_(25)

    def _on_app_state_changed(self, state):
        """Re-enforce native level when app activation state changes"""
        if sys.platform == "darwin":
            QTimer.singleShot(50, self._enforce_native_level)

    def toggle_active_filter(self):
        """Toggle the active worktree filter (show only active worktrees)."""
        self.filter_active = self.btn_filter.isChecked()
        self.refresh_table_display()

    def closeEvent(self, event):
        """Minimize to tray instead of closing"""
        event.ignore()
        self.hide()
        self.tray.showMessage(
            "Worktree Control Center",
            "Minimized to tray. Right-click to quit.",
            QSystemTrayIcon.Information,
            2000
        )

    def enterEvent(self, event):
        """Mouse entered window - make fully opaque"""
        self.setWindowOpacity(self.config.control_center["opacity_hover"])
        super().enterEvent(event)

    def leaveEvent(self, event):
        """Mouse left window - make semi-transparent"""
        self.setWindowOpacity(self.config.control_center["opacity_default"])
        super().leaveEvent(event)

    def apply_config_changes(self):
        """Apply config changes after settings dialog"""
        cc = self.config.control_center

        self.setWindowOpacity(cc["opacity_default"])
        self.setFixedWidth(cc["window_width"])

        if not hasattr(self, '_old_workers'):
            self._old_workers = []

        old_worker = self.worker
        old_worker.stop()
        self.worker = StatusWorker(self.config)
        self.worker.status_updated.connect(self.update_status)
        self.worker.error_occurred.connect(self.on_error)
        self.worker.start()
        old_worker.finished.connect(lambda w=old_worker: self._cleanup_old_worker(w))
        self._old_workers.append(old_worker)

        self.blink_timer.setInterval(cc["blink_interval_ms"])

        if hasattr(self, 'team_worker'):
            old_team = self.team_worker
            old_team.stop()
            self.team_worker = TeamWorker(self.config)
            self.team_worker.team_updated.connect(self.update_team)
            self.team_worker.error_occurred.connect(self.on_team_error)
            self.team_worker.start()
            old_team.finished.connect(lambda w=old_team: self._cleanup_old_worker(w))
            self._old_workers.append(old_team)

        if hasattr(self, 'chat_worker'):
            old_chat = self.chat_worker
            old_chat.stop()
            self.chat_worker = ChatWorker(self.config)
            self.chat_worker.unread_count_changed.connect(self.update_chat_badge)
            self.chat_worker.start()
            old_chat.finished.connect(lambda w=old_chat: self._cleanup_old_worker(w))
            self._old_workers.append(old_chat)

        if hasattr(self, 'feature_worker'):
            old_feature = self.feature_worker
            old_feature.stop()
            self.feature_worker = FeatureWorker()
            self.feature_worker.features_updated.connect(self.on_features_updated)
            self.feature_worker.start()
            old_feature.finished.connect(lambda w=old_feature: self._cleanup_old_worker(w))
            self._old_workers.append(old_feature)

        self.refresh_status()
        self.update_usage_bars()
        self.update_team_display()

    def _cleanup_old_worker(self, worker):
        """Remove finished worker from old workers list"""
        if hasattr(self, '_old_workers') and worker in self._old_workers:
            self._old_workers.remove(worker)

    def restart_app(self):
        """Restart the application"""
        self.save_position()
        self._stop_all_workers()
        self._wait_all_workers()
        subprocess.Popen([sys.executable] + sys.argv)
        QApplication.quit()

    def _stop_all_workers(self):
        """Signal all worker threads to stop"""
        self.worker.stop()
        if hasattr(self, 'usage_worker'):
            self.usage_worker.stop()
        if hasattr(self, 'team_worker'):
            self.team_worker.stop()
        if hasattr(self, 'chat_worker'):
            self.chat_worker.stop()
        if hasattr(self, 'feature_worker'):
            self.feature_worker.stop()

    def _wait_all_workers(self, timeout_ms=2000):
        """Wait for all worker threads to finish, terminate stragglers"""
        workers = [self.worker]
        for attr in ('usage_worker', 'team_worker', 'chat_worker', 'feature_worker'):
            if hasattr(self, attr):
                workers.append(getattr(self, attr))
        for w in workers:
            if not w.wait(timeout_ms):
                w.terminate()
                w.wait(500)

    def quit_app(self):
        """Actually quit the application"""
        self.save_position()
        self._stop_all_workers()
        self._wait_all_workers()
        QApplication.quit()
