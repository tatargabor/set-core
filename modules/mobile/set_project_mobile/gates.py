"""Mobile-specific gate executors for SET.

Provides Xcode build verification gate for iOS Capacitor projects.
"""

import logging
import subprocess
from pathlib import Path

logger = logging.getLogger(__name__)


class MobileXcodeBuildGate:
    """Gate that verifies iOS project builds successfully via xcodebuild.

    Only runs when ios/App/ directory exists and has been modified.
    """

    id = "xcode-build"
    description = "Verify iOS project builds with xcodebuild"

    def should_run(self, wt_path: str, changed_files: list) -> bool:
        """Only run if ios/App/ exists and native files were modified."""
        ios_dir = Path(wt_path) / "ios" / "App"
        if not ios_dir.is_dir():
            return False
        return any(f.startswith("ios/") for f in changed_files)

    def run(self, wt_path: str, env: dict) -> dict:
        """Run xcodebuild to verify iOS project compiles.

        Returns:
            dict with keys: passed (bool), output (str), duration_ms (int)
        """
        import time

        ios_project = Path(wt_path) / "ios" / "App"
        start = time.monotonic()

        try:
            result = subprocess.run(
                [
                    "xcodebuild",
                    "build",
                    "-project", str(ios_project / "App.xcodeproj"),
                    "-scheme", "App",
                    "-destination", "generic/platform=iOS Simulator",
                    "-quiet",
                ],
                capture_output=True,
                text=True,
                timeout=300,
                cwd=str(ios_project),
                env={**env} if env else None,
            )
            duration_ms = int((time.monotonic() - start) * 1000)

            if result.returncode == 0:
                return {
                    "passed": True,
                    "output": "Xcode build succeeded",
                    "duration_ms": duration_ms,
                }
            else:
                return {
                    "passed": False,
                    "output": result.stderr[-2000:] if result.stderr else result.stdout[-2000:],
                    "duration_ms": duration_ms,
                }
        except FileNotFoundError:
            return {
                "passed": False,
                "output": "xcodebuild not found — Xcode Command Line Tools required",
                "duration_ms": 0,
            }
        except subprocess.TimeoutExpired:
            duration_ms = int((time.monotonic() - start) * 1000)
            return {
                "passed": False,
                "output": "Xcode build timed out after 300s",
                "duration_ms": duration_ms,
            }
