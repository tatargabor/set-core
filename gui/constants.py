"""
GUI Constants - Colors, paths, and default configuration
"""

import os
from pathlib import Path

__all__ = [
    "SCRIPT_DIR",
    "CONFIG_DIR",
    "CONFIG_FILE",
    "STATE_FILE",
    "CLAUDE_SESSION_FILE",
    "COLOR_PROFILES",
    "DEFAULT_CONFIG",
    "ICON_RUNNING",
    "ICON_WAITING",
    "ICON_IDLE",
    "ICON_ORPHAN",
    "ICON_IDLE_IDE",
]

# Find bin directory relative to this script
SCRIPT_DIR = Path(__file__).parent.parent / "bin"

# Config file paths - support WT_CONFIG_DIR override for testing
_config_override = os.environ.get("WT_CONFIG_DIR")
CONFIG_DIR = Path(_config_override) if _config_override else Path.home() / ".config" / "wt-tools"
CONFIG_FILE = CONFIG_DIR / "gui-config.json"
STATE_FILE = CONFIG_DIR / "gui-state.json"
CLAUDE_SESSION_FILE = CONFIG_DIR / "claude-session.json"

# Status icons for team display
ICON_RUNNING = "●"
ICON_WAITING = "⚡"
ICON_IDLE = "○"
ICON_ORPHAN = "⚠"
ICON_IDLE_IDE = "◇"

# Color profiles for theming
COLOR_PROFILES = {
    "light": {
        # Status colors
        "status_running": "#22c55e",
        "status_waiting": "#f59e0b",
        "status_compacting": "#a855f7",  # purple - context summarizing
        "status_idle": "#6b7280",
        "status_done": "#3b82f6",
        "status_stalled": "#f59e0b",  # orange - Ralph loop stalled
        # Burn rate colors
        "burn_low": "#22c55e",
        "burn_medium": "#f59e0b",
        "burn_high": "#ef4444",
        # UI element colors
        "bar_background": "#e5e7eb",
        "bar_border": "#cccccc",
        "bar_time": "#d1d5db",
        "border": "#d1d5db",
        # Text colors
        "text_primary": "#1f2937",  # dark gray for light backgrounds
        "text_muted": "#6b7280",
        "text_secondary": "#60a5fa",  # blue - team "my machine" rows
        "text_warning": "#b45309",
        # Button colors
        "button_primary": "#3b82f6",
        "button_primary_text": "#ffffff",
        # Context usage colors
        "ctx_high": "#ef4444",
        "ctx_medium": "#f59e0b",
        # Background
        "bg_dialog": "#f0f0f0",
        # Row background colors by status
        "row_running": "#dcfce7",         # light green - actively working
        "row_running_text": "#166534",    # dark green text
        "row_waiting": "#fef3c7",         # light yellow
        "row_waiting_text": "#92400e",    # dark amber text
        "row_waiting_blink": "#fecaca",   # pale red
        "row_compacting": "#f3e8ff",      # light purple
        "row_compacting_text": "#6b21a8", # dark purple text
        "row_idle": "transparent",
        "row_idle_text": "#1f2937",       # dark gray (not pure black)
        # Idle IDE colors (editor open, no agent)
        "status_idle_ide": "#64748b",
        "row_idle_ide": "#f1f5f9",
        "row_idle_ide_text": "#475569",
        # Orphan agent colors (dead process, gray/muted)
        "status_orphan": "#9ca3af",
        "row_orphan": "#e5e7eb",
        "row_orphan_text": "#6b7280",
    },
    "dark": {
        "status_running": "#4ade80",
        "status_waiting": "#fbbf24",
        "status_compacting": "#c084fc",  # light purple
        "status_idle": "#9ca3af",
        "status_done": "#60a5fa",
        "status_stalled": "#fbbf24",  # orange - Ralph loop stalled
        "burn_low": "#4ade80",
        "burn_medium": "#fbbf24",
        "burn_high": "#f87171",
        "bar_background": "#374151",
        "bar_border": "#4b5563",
        "bar_time": "#4b5563",
        "border": "#4b5563",
        "text_primary": "#f9fafb",  # near white for dark backgrounds
        "text_muted": "#9ca3af",
        "text_secondary": "#60a5fa",  # blue - team "my machine" rows
        "text_warning": "#fbbf24",
        "button_primary": "#3b82f6",
        "button_primary_text": "#ffffff",
        "ctx_high": "#f87171",
        "ctx_medium": "#fbbf24",
        "bg_dialog": "#1f2937",
        "row_running": "#166534",         # dark green
        "row_running_text": "#bbf7d0",    # light green text
        "row_waiting": "#78350f",         # dark amber
        "row_waiting_text": "#fef3c7",    # light amber text
        "row_waiting_blink": "#7f1d1d",
        "row_compacting": "#4c1d95",      # dark purple
        "row_compacting_text": "#e9d5ff", # light purple text
        "row_idle": "transparent",
        "row_idle_text": "#e5e7eb",
        # Idle IDE colors (editor open, no agent)
        "status_idle_ide": "#94a3b8",
        "row_idle_ide": "#1e293b",
        "row_idle_ide_text": "#cbd5e1",
        # Orphan agent colors
        "status_orphan": "#6b7280",
        "row_orphan": "#374151",
        "row_orphan_text": "#9ca3af",
    },
    "gray": {
        # Status colors - balanced visibility
        "status_running": "#34d399",
        "status_waiting": "#fbbf24",
        "status_compacting": "#a78bfa",  # purple
        "status_idle": "#9ca3af",
        "status_done": "#60a5fa",
        "status_stalled": "#fbbf24",  # orange - Ralph loop stalled
        # Burn rate colors
        "burn_low": "#34d399",
        "burn_medium": "#fbbf24",
        "burn_high": "#f87171",
        # UI element colors
        "bar_background": "#4b5563",
        "bar_border": "#6b7280",
        "bar_time": "#6b7280",
        "border": "#6b7280",
        # Text colors
        "text_primary": "#f3f4f6",  # light gray for gray backgrounds
        "text_muted": "#9ca3af",
        "text_secondary": "#60a5fa",  # blue - team "my machine" rows
        "text_warning": "#fbbf24",
        # Button colors
        "button_primary": "#3b82f6",
        "button_primary_text": "#ffffff",
        # Context usage colors
        "ctx_high": "#f87171",
        "ctx_medium": "#fbbf24",
        # Background - medium gray
        "bg_dialog": "#374151",
        # Row background colors by status
        "row_running": "#065f46",         # muted green
        "row_running_text": "#a7f3d0",    # light green text
        "row_waiting": "#92400e",         # muted amber
        "row_waiting_text": "#fef3c7",    # light amber text
        "row_waiting_blink": "#991b1b",
        "row_compacting": "#5b21b6",      # muted purple
        "row_compacting_text": "#ddd6fe", # light purple text
        "row_idle": "transparent",
        "row_idle_text": "#e5e7eb",
        # Idle IDE colors (editor open, no agent)
        "status_idle_ide": "#94a3b8",
        "row_idle_ide": "#1e293b",
        "row_idle_ide_text": "#cbd5e1",
        # Orphan agent colors
        "status_orphan": "#6b7280",
        "row_orphan": "#4b5563",
        "row_orphan_text": "#9ca3af",
    },
    "high_contrast": {
        "status_running": "#00ff00",
        "status_waiting": "#ffff00",
        "status_compacting": "#ff00ff",  # magenta
        "status_idle": "#888888",
        "status_done": "#00aaff",
        "status_stalled": "#ffaa00",  # orange - Ralph loop stalled
        "burn_low": "#00ff00",
        "burn_medium": "#ffff00",
        "burn_high": "#ff0000",
        "bar_background": "#333333",
        "bar_border": "#ffffff",
        "bar_time": "#888888",
        "border": "#ffffff",
        "text_primary": "#ffffff",  # white for high contrast dark backgrounds
        "text_muted": "#aaaaaa",
        "text_secondary": "#00aaff",  # bright blue - team "my machine" rows
        "text_warning": "#ffaa00",
        "button_primary": "#0066cc",
        "button_primary_text": "#ffffff",
        "ctx_high": "#ff0000",
        "ctx_medium": "#ffaa00",
        "bg_dialog": "#222222",
        "row_running": "#004400",         # dark green
        "row_running_text": "#00ff00",    # bright green text
        "row_waiting": "#666600",         # dark yellow
        "row_waiting_text": "#ffff00",    # bright yellow text
        "row_waiting_blink": "#660000",
        "row_compacting": "#440044",      # dark magenta
        "row_compacting_text": "#ff00ff", # bright magenta text
        "row_idle": "transparent",
        "row_idle_text": "#ffffff",
        # Idle IDE colors (editor open, no agent)
        "status_idle_ide": "#6699cc",
        "row_idle_ide": "#1a1a2e",
        "row_idle_ide_text": "#88bbdd",
        # Orphan agent colors
        "status_orphan": "#888888",
        "row_orphan": "#333333",
        "row_orphan_text": "#aaaaaa",
    },
}

# Default configuration
DEFAULT_CONFIG = {
    "control_center": {
        "opacity_default": 1.0,
        "opacity_hover": 1.0,
        "window_width": 500,
        "refresh_interval_ms": 2000,
        "blink_interval_ms": 500,
        "color_profile": "gray",
    },
    "git": {
        "branch_prefix": "change/",
        "fetch_timeout_s": 10,
    },
    "ralph": {
        "terminal_fullscreen": False,
        "default_max_iterations": 10,
    },
    "notifications": {
        "enabled": True,
        "sound": False,
    },
    "team": {
        "enabled": False,
        "sync_interval_ms": 120000,
        "auto_sync": True,
    },
    "usage": {
        "estimated_5h_limit": 500000,
        "estimated_weekly_limit": 5000000,
        "show_estimated_indicator": True,
    },
}
