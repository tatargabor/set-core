"""
SET Control Center GUI

Modular GUI package with the following structure:
- constants.py: Colors, paths, default configuration
- config.py: Configuration manager
- utils.py: Utility functions
- widgets/: Custom widgets
- dialogs/: Dialog windows
- workers/: Background workers (QThread)
- control_center/: Main window with mixins
"""

from .constants import (
    SCRIPT_DIR,
    CONFIG_DIR,
    CONFIG_FILE,
    STATE_FILE,
    COLOR_PROFILES,
    DEFAULT_CONFIG,
)
from .config import Config
from .utils import get_version
from .control_center import ControlCenter

__all__ = [
    "SCRIPT_DIR",
    "CONFIG_DIR",
    "CONFIG_FILE",
    "STATE_FILE",
    "COLOR_PROFILES",
    "DEFAULT_CONFIG",
    "Config",
    "get_version",
    "ControlCenter",
]
