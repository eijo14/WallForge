"""Comprehensive cross-platform and backend capability tests for WallForge.

Tests platform resolution, setters (Windows, macOS, Linux DEs, Unavailable),
graceful degradation, and environment detection without requiring host OS.
"""

import os
from pathlib import Path
import platform
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import MagicMock, patch

from wallpaper_engine.core.paths import PathManager
from wallpaper_engine.setters.base import WallpaperSetter
from wallpaper_engine.setters.detector import (
    detect_environment_name,
    get_all_registered_setters,
    get_available_setters,
    get_best_setter,
)
from wallpaper_engine.setters.extended import (
    CinnamonWallpaperSetter,
    MATEWallpaperSetter,
    SwayWallpaperSetter,
    XFCEWallpaperSetter,
)
from wallpaper_engine.setters.generic import GenericLinuxWallpaperSetter
from wallpaper_engine.setters.gnome import GNOMEWallpaperSetter
from wallpaper_engine.setters.hyprland import HyprlandWallpaperSetter
from wallpaper_engine.setters.kde import KDEPlasmaWallpaperSetter
from wallpaper_engine.setters.macos import MacOSWallpaperSetter
from wallpaper_engine.setters.unavailable import UnavailableWallpaperSetter
from wallpaper_engine.setters.windows import WindowsWallpaperSetter


class TestPathManager(unittest.TestCase):
    """Verify platform-aware directory resolution across Windows, macOS, and Linux."""

    def test_windows_paths(self):
        with patch("platform.system", return_value="Windows"), \
             patch.dict(os.environ, {
                 "LOCALAPPDATA": "C:\\Users\\Test\\AppData\\Local",
                 "APPDATA": "C:\\Users\\Test\\AppData\\Roaming",
                 "USERPROFILE": "C:\\Users\\Test",
             }):
            pm = PathManager()
            self.assertEqual(pm.cache_dir.parts[-2:], ("wallforge", "Cache"))
            self.assertEqual(pm.config_dir.parts[-2:], ("wallforge", "Config"))
            self.assertEqual(pm.data_dir.parts[-2:], ("wallforge", "Data"))
            self.assertEqual(pm.thumbs_dir.parts[-3:], ("wallforge", "Cache", "thumbs"))
            self.assertEqual(pm.wallpapers_dir.parts[-3:], ("wallforge", "Data", "wallpapers"))
            self.assertTrue(str(pm.pictures_dir).endswith("Pictures"))

    def test_macos_paths(self):
        fake_home = Path("/Users/testuser")
        with patch("platform.system", return_value="Darwin"), \
             patch("pathlib.Path.home", return_value=fake_home):
            pm = PathManager()
            self.assertEqual(pm.cache_dir, fake_home / "Library" / "Caches" / "wallforge")
            self.assertEqual(pm.config_dir, fake_home / "Library" / "Application Support" / "wallforge")
            self.assertEqual(pm.data_dir, fake_home / "Library" / "Application Support" / "wallforge" / "Data")
            self.assertEqual(pm.pictures_dir, fake_home / "Pictures")

    def test_linux_paths_xdg(self):
        with patch("platform.system", return_value="Linux"), \
             patch.dict(os.environ, {
                 "XDG_CACHE_HOME": "/tmp/custom_cache",
                 "XDG_CONFIG_HOME": "/tmp/custom_config",
                 "XDG_DATA_HOME": "/tmp/custom_data",
             }):
            pm = PathManager()
            self.assertEqual(pm.cache_dir, Path("/tmp/custom_cache/wallforge"))
            self.assertEqual(pm.config_dir, Path("/tmp/custom_config/wallforge"))
            self.assertEqual(pm.data_dir, Path("/tmp/custom_data/wallforge"))

    def test_overrides_and_ensure_directories(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp = Path(tmp_dir)
            c = tmp / "cache"
            d = tmp / "data"
            cfg = tmp / "config"
            pm = PathManager(
                override_cache_dir=c,
                override_data_dir=d,
                override_config_dir=cfg,
            )
            self.assertEqual(pm.cache_dir, c)
            self.assertEqual(pm.data_dir, d)
            self.assertEqual(pm.config_dir, cfg)
            pm.ensure_directories()
            self.assertTrue(pm.cache_dir.is_dir())
            self.assertTrue(pm.thumbs_dir.is_dir())
            self.assertTrue(pm.previews_dir.is_dir())
            self.assertTrue(pm.wallpapers_dir.is_dir())


class TestWindowsWallpaperSetter(unittest.TestCase):
    """Test native Windows wallpaper backend with mocked ctypes and registry."""

    def setUp(self):
        self.setter = WindowsWallpaperSetter()

    def test_metadata_and_capabilities(self):
        self.assertEqual(self.setter.backend_id, "windows")
        self.assertEqual(self.setter.platform_name, "Windows")
        caps = self.setter.capabilities()
        self.assertIn("can_set", caps)
        self.assertIn("can_clear", caps)
        self.assertIn("can_get", caps)
        self.assertIn("multi_monitor", caps)
        self.assertTrue(caps["multi_monitor"])

    def test_availability(self):
        with patch("platform.system", return_value="Windows"):
            self.assertTrue(self.setter.is_available())
        with patch("platform.system", return_value="Linux"):
            self.assertFalse(self.setter.is_available())
        with patch("platform.system", return_value="Darwin"):
            self.assertFalse(self.setter.is_available())

    def test_apply_wallpaper_success(self):
        with tempfile.NamedTemporaryFile(suffix=".jpg", delete=False) as f:
            test_img = Path(f.name)
        try:
            mock_ctypes = MagicMock()
            mock_ctypes.windll.user32.SystemParametersInfoW.return_value = 1

            with patch("platform.system", return_value="Windows"), \
                 patch.dict("sys.modules", {"ctypes": mock_ctypes}):
                ok, msg = self.setter.apply_wallpaper(test_img, mode="fill")
                self.assertTrue(ok)
                self.assertIn("SystemParametersInfoW", msg)
                self.assertEqual(self.setter.get_active_wallpaper(), test_img.resolve())

                # Verify SPI constants called: SPI_SETDESKWALLPAPER=20, flags=3
                mock_ctypes.windll.user32.SystemParametersInfoW.assert_called_once_with(
                    20,
                    0,
                    str(test_img.resolve()),
                    3,
                )
        finally:
            if test_img.exists():
                test_img.unlink()

    def test_apply_wallpaper_failure_when_not_windows(self):
        with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as f:
            test_img = Path(f.name)
        try:
            with patch("platform.system", return_value="Linux"):
                ok, msg = self.setter.apply_wallpaper(test_img)
                self.assertFalse(ok)
                self.assertIn("only available on Windows", msg)
        finally:
            if test_img.exists():
                test_img.unlink()

    def test_apply_nonexistent_file(self):
        ok, msg = self.setter.apply_wallpaper(Path("/nonexistent/wp.jpg"))
        self.assertFalse(ok)
        self.assertIn("does not exist", msg)


class TestMacOSWallpaperSetter(unittest.TestCase):
    """Test native macOS wallpaper backend with mocked osascript."""

    def setUp(self):
        self.setter = MacOSWallpaperSetter()

    def test_metadata_and_capabilities(self):
        self.assertEqual(self.setter.backend_id, "macos")
        self.assertEqual(self.setter.platform_name, "macOS")
        caps = self.setter.capabilities()
        self.assertTrue(caps["multi_monitor"])

    def test_availability(self):
        with patch("platform.system", return_value="Darwin"), \
             patch("shutil.which", return_value="/usr/bin/osascript"):
            self.assertTrue(self.setter.is_available())
        with patch("platform.system", return_value="Linux"):
            self.assertFalse(self.setter.is_available())

    def test_apply_wallpaper_success(self):
        with tempfile.NamedTemporaryFile(suffix=".jpg", delete=False) as f:
            test_img = Path(f.name)
        try:
            mock_proc = MagicMock()
            mock_proc.returncode = 0
            mock_proc.stdout = ""
            mock_proc.stderr = ""

            with patch("platform.system", return_value="Darwin"), \
                 patch("shutil.which", return_value="/usr/bin/osascript"), \
                 patch("subprocess.run", return_value=mock_proc) as mock_sub:
                ok, msg = self.setter.apply_wallpaper(test_img)
                self.assertTrue(ok)
                self.assertIn("AppleScript", msg)
                self.assertEqual(self.setter.get_active_wallpaper(), test_img.resolve())

                # Verify osascript called with positional argv argument (no AppleScript interpolation)
                mock_sub.assert_called_once()
                cmd = mock_sub.call_args[0][0]
                self.assertEqual(cmd[0], "osascript")
                self.assertEqual(cmd[1], "-e")
                self.assertIn("on run argv", cmd[2])
                self.assertIn("tell every desktop", cmd[2])
                self.assertNotIn(str(test_img.resolve()), cmd[2])  # Must NOT be interpolated into script
                self.assertEqual(cmd[3], str(test_img.resolve()))  # Must be passed as positional argv
        finally:
            if test_img.exists():
                test_img.unlink()

    def test_apply_wallpaper_failure(self):
        with tempfile.NamedTemporaryFile(suffix=".jpg", delete=False) as f:
            test_img = Path(f.name)
        try:
            mock_proc = MagicMock()
            mock_proc.returncode = 1
            mock_proc.stderr = "execution error: Application isn't running"

            with patch("platform.system", return_value="Darwin"), \
                 patch("shutil.which", return_value="/usr/bin/osascript"), \
                 patch("subprocess.run", return_value=mock_proc):
                ok, msg = self.setter.apply_wallpaper(test_img)
                self.assertFalse(ok)
                self.assertIn("AppleScript error", msg)
        finally:
            if test_img.exists():
                test_img.unlink()


class TestUnavailableWallpaperSetter(unittest.TestCase):
    """Test the graceful degradation fallback backend."""

    def setUp(self):
        self.setter = UnavailableWallpaperSetter()

    def test_contract(self):
        self.assertEqual(self.setter.backend_id, "unavailable")
        self.assertEqual(self.setter.platform_name, "Unavailable")
        self.assertFalse(self.setter.is_available())
        self.assertFalse(self.setter.is_supported())

        ok, msg = self.setter.apply_wallpaper(Path("/tmp/some_img.png"))
        self.assertFalse(ok)
        self.assertIn("unavailable on this system", msg)

        clear_ok, clear_msg = self.setter.clear_wallpaper()
        self.assertFalse(clear_ok)
        self.assertIn("unavailable on this system", clear_msg)

        self.assertIsNone(self.setter.get_current_wallpaper())

        caps = self.setter.capabilities()
        self.assertFalse(caps["can_set"])
        self.assertFalse(caps["can_clear"])
        self.assertFalse(caps["can_get"])
        self.assertIn("reason", caps)


class TestEnvironmentDetector(unittest.TestCase):
    """Test OS and Desktop Environment detection across platforms."""

    def test_detect_environment_name_windows(self):
        with patch("platform.system", return_value="Windows"), \
             patch("platform.release", return_value="11"):
            self.assertEqual(detect_environment_name(), "Windows 11")

    def test_detect_environment_name_macos(self):
        with patch("platform.system", return_value="Darwin"), \
             patch("platform.mac_ver", return_value=("14.4.1", ("", "", ""), "")):
            self.assertEqual(detect_environment_name(), "macOS 14.4.1")

    def test_detect_environment_name_hyprland(self):
        with patch("platform.system", return_value="Linux"), \
             patch.dict(os.environ, {"HYPRLAND_INSTANCE_SIGNATURE": "12345"}):
            self.assertEqual(detect_environment_name(), "Hyprland")

    def test_detect_environment_name_gnome(self):
        with patch("platform.system", return_value="Linux"), \
             patch.dict(os.environ, {"XDG_CURRENT_DESKTOP": "ubuntu:GNOME"}, clear=True):
            self.assertEqual(detect_environment_name(), "GNOME")

    def test_detect_environment_name_kde(self):
        with patch("platform.system", return_value="Linux"), \
             patch.dict(os.environ, {"XDG_CURRENT_DESKTOP": "KDE"}, clear=True):
            self.assertEqual(detect_environment_name(), "KDE Plasma")

    def test_detect_environment_name_generic_linux(self):
        with patch("platform.system", return_value="Linux"), \
             patch.dict(os.environ, {}, clear=True):
            self.assertEqual(detect_environment_name(), "Generic Linux (X11 / Wayland)")

    def test_get_all_registered_setters(self):
        setters = get_all_registered_setters()
        backend_ids = [s.backend_id for s in setters]
        self.assertIn("windows", backend_ids)
        self.assertIn("macos", backend_ids)
        self.assertIn("hyprland", backend_ids)
        self.assertIn("gnome", backend_ids)
        self.assertIn("kde", backend_ids)
        self.assertIn("xfce", backend_ids)
        self.assertIn("cinnamon", backend_ids)
        self.assertIn("mate", backend_ids)
        self.assertIn("sway", backend_ids)
        self.assertIn("generic", backend_ids)
        self.assertIn("unavailable", backend_ids)

    def test_get_best_setter_windows(self):
        with patch("platform.system", return_value="Windows"), \
             patch.object(WindowsWallpaperSetter, "is_available", return_value=True):
            setter = get_best_setter()
            self.assertIsInstance(setter, WindowsWallpaperSetter)

    def test_get_best_setter_macos(self):
        with patch("platform.system", return_value="Darwin"), \
             patch.object(MacOSWallpaperSetter, "is_available", return_value=True):
            setter = get_best_setter()
            self.assertIsInstance(setter, MacOSWallpaperSetter)

    def test_get_best_setter_fallback_unavailable(self):
        # When on an unsupported platform where no setter is available
        with patch("platform.system", return_value="FreeBSD"), \
             patch.dict(os.environ, {}, clear=True), \
             patch("shutil.which", return_value=None):
            setter = get_best_setter()
            self.assertIsInstance(setter, UnavailableWallpaperSetter)
            self.assertFalse(setter.is_available())


class TestSetterContractIntegrity(unittest.TestCase):
    """Verify that every single backend fully complies with WallpaperBackend API."""

    def test_all_backends_have_required_interface(self):
        all_setters = get_all_registered_setters()
        for setter in all_setters:
            self.assertIsInstance(setter, WallpaperSetter)
            self.assertIsInstance(setter.name, str)
            self.assertIsInstance(setter.backend_id, str)
            self.assertIsInstance(setter.platform_name, str)
            self.assertIsInstance(setter.is_available(), bool)
            self.assertIsInstance(setter.is_supported(), bool)
            self.assertEqual(setter.is_available(), setter.is_supported())

            # capabilities()
            caps = setter.capabilities()
            self.assertIsInstance(caps, dict)
            self.assertIn("can_set", caps)
            self.assertIn("can_clear", caps)
            self.assertIn("can_get", caps)
            self.assertIn("multi_monitor", caps)

            # Check clear_wallpaper
            c_ok, c_msg = setter.clear_wallpaper()
            self.assertIsInstance(c_ok, bool)
            self.assertIsInstance(c_msg, str)

            # Check set_wallpaper is alias for apply_wallpaper
            self.assertTrue(callable(setter.set_wallpaper))
            self.assertTrue(callable(setter.apply_wallpaper))


class TestGracefulDegradationUI(unittest.TestCase):
    """Test UI graceful degradation when wallpaper setter is unavailable."""

    def test_rotation_service_graceful_degradation(self):
        from wallpaper_engine.core.cache_manager import CacheManager
        from wallpaper_engine.core.rotation_service import RotationService
        from wallpaper_engine.core.search_service import SearchAggregator
        from wallpaper_engine.core.source_manager import SourceManager

        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp = Path(tmp_dir)
            cm = CacheManager(base_cache_dir=tmp / "cache", base_data_dir=tmp / "data")
            sm = SourceManager(config_dir=tmp / "config")
            sa = SearchAggregator(sm, cm)
            unavail = UnavailableWallpaperSetter()
            rot = RotationService(sm, sa, cm, unavail)

            # rotate_now must return False immediately without error
            result = rot.rotate_now()
            self.assertFalse(result)

    def test_preview_dialog_graceful_degradation_if_display(self):
        import gi
        gi.require_version("Gtk", "4.0")
        gi.require_version("Adw", "1")
        from gi.repository import Adw, Gdk, Gtk
        from wallpaper_engine.core.cache_manager import CacheManager
        from wallpaper_engine.core.models import Wallpaper
        from wallpaper_engine.ui.preview_dialog import WallpaperPreviewDialog

        display = Gdk.Display.get_default()
        if not display:
            return  # Skip display-dependent UI test if headless

        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp = Path(tmp_dir)
            cm = CacheManager(base_cache_dir=tmp / "cache", base_data_dir=tmp / "data")
            unavail = UnavailableWallpaperSetter()
            wp = Wallpaper(
                id="test-unavail",
                provider_id="test",
                provider_name="Test",
                title="Test Degrade",
                thumbnail_url="https://example.com/test.jpg",
                image_url="https://example.com/test.jpg",
            )
            dialog = WallpaperPreviewDialog(
                parent=None,
                wallpaper=wp,
                cache_manager=cm,
                wallpaper_setter=unavail,
                is_favorite=False,
            )
            try:
                # Apply button must be disabled with explanatory tooltip
                self.assertFalse(dialog.apply_btn.get_sensitive())
                self.assertIn("unavailable", dialog.apply_btn.get_tooltip_text().lower())

                # Other controls must remain enabled
                self.assertTrue(dialog.download_btn.get_sensitive())
                self.assertTrue(dialog.close_btn.get_sensitive())
            finally:
                dialog.close()


if __name__ == "__main__":
    unittest.main()

