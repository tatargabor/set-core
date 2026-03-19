"""Tests for the platform abstraction layer"""

import platform
import pytest
from pathlib import Path


class TestPlatformDetection:
    """Tests for platform detection"""

    def test_get_platform_returns_interface(self):
        from gui.platform import get_platform

        plat = get_platform()
        assert plat is not None
        assert hasattr(plat, "name")
        assert hasattr(plat, "is_supported")

    def test_platform_name_matches_system(self):
        from gui.platform import get_platform, PLATFORM_NAME

        plat = get_platform()
        system = platform.system().lower()

        if system == "linux":
            assert plat.name == "linux"
        elif system == "darwin":
            assert plat.name == "darwin"
        elif system == "windows":
            assert plat.name == "windows"

    def test_platform_singleton(self):
        from gui.platform import platform_instance

        plat1 = platform_instance()
        plat2 = platform_instance()
        assert plat1 is plat2


class TestPlatformInterface:
    """Tests for the base PlatformInterface"""

    def test_is_process_running(self):
        import os
        from gui.platform import get_platform

        plat = get_platform()

        # Current process should be running
        assert plat.is_process_running(os.getpid()) is True

        # Non-existent PID (very high)
        assert plat.is_process_running(999999999) is False

    def test_get_config_dir(self):
        from gui.platform import get_platform

        plat = get_platform()
        config_dir = plat.get_config_dir()

        assert isinstance(config_dir, Path)
        assert "set-core" in str(config_dir)

    def test_get_cache_dir(self):
        from gui.platform import get_platform

        plat = get_platform()
        cache_dir = plat.get_cache_dir()

        assert isinstance(cache_dir, Path)
        assert "set-core" in str(cache_dir) or "cache" in str(cache_dir).lower()


class TestLinuxPlatform:
    """Tests specific to Linux platform"""

    @pytest.mark.skipif(platform.system() != "Linux", reason="Linux-only tests")
    def test_linux_platform_name(self):
        from gui.platform.linux import LinuxPlatform

        plat = LinuxPlatform()
        assert plat.name == "linux"
        assert plat.is_supported is True

    @pytest.mark.skipif(platform.system() != "Linux", reason="Linux-only tests")
    def test_get_process_cmdline(self):
        import os
        from gui.platform.linux import LinuxPlatform

        plat = LinuxPlatform()
        cmdline = plat.get_process_cmdline(os.getpid())

        # Should get something that contains python
        assert cmdline is not None
        assert "python" in cmdline.lower() or "pytest" in cmdline.lower()


class TestMacOSPlatform:
    """Tests specific to macOS platform"""

    @pytest.mark.skipif(platform.system() != "Darwin", reason="macOS-only tests")
    def test_macos_platform_name(self):
        from gui.platform.macos import MacOSPlatform

        plat = MacOSPlatform()
        assert plat.name == "darwin"
        assert plat.is_supported is True


class TestWindowsPlatform:
    """Tests specific to Windows platform"""

    @pytest.mark.skipif(platform.system() != "Windows", reason="Windows-only tests")
    def test_windows_platform_name(self):
        from gui.platform.windows import WindowsPlatform

        plat = WindowsPlatform()
        assert plat.name == "windows"
        assert plat.is_supported is True
