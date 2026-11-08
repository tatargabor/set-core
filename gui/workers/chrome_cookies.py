"""The Control Center's door to the Chrome session scanner.

The scanner itself lives in core (`set_orch.usage.chrome_scan`) so the dashboard can run it
too. This module re-exports it under the old name and keeps the Qt worker thread.
"""

from set_orch.usage.chrome_scan import (  # noqa: F401
    is_pycookiecheat_available,
    merge_scan_results,
    scan_chrome_sessions,
)

__all__ = ["scan_chrome_sessions", "is_pycookiecheat_available", "merge_scan_results", "ChromeScanWorker"]

try:
    from PySide6.QtCore import QThread, Signal

    class ChromeScanWorker(QThread):
        """Background thread for Chrome session scanning."""
        scan_finished = Signal(list)
        scan_error = Signal(str)

        def __init__(self, force_refresh: bool = False, existing_accounts: list[dict] | None = None):
            super().__init__()
            self._force_refresh = force_refresh
            self._existing_accounts = existing_accounts

        def run(self):
            try:
                results = scan_chrome_sessions(
                    force_refresh=self._force_refresh,
                    existing_accounts=self._existing_accounts,
                )
                self.scan_finished.emit(results)
            except Exception as e:
                self.scan_error.emit(str(e))

except ImportError:
    # PySide6 not available (e.g. in tests without Qt)
    ChromeScanWorker = None  # type: ignore[assignment, misc]
