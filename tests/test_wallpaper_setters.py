"""Tests for desktop wallpaper setters (Hyprland, GNOME, Generic)."""

from pathlib import Path
import shutil
import tempfile
import unittest
from unittest.mock import MagicMock, call, patch

from wallpaper_engine.setters.gnome import GNOMEWallpaperSetter
from wallpaper_engine.setters.hyprland import HyprlandWallpaperSetter


class TestWallpaperSetters(unittest.TestCase):
    def setUp(self):
        self.temp_dir = Path(tempfile.mkdtemp(prefix="wp_setters_test_"))
        self.hypr_config_dir = self.temp_dir / "hypr"
        self.test_image1 = self.temp_dir / "image1.jpg"
        self.test_image2 = self.temp_dir / "image2.jpg"
        self.test_image1.write_text("fake image 1")
        self.test_image2.write_text("fake image 2")

    def tearDown(self):
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    @patch("subprocess.run")
    @patch("subprocess.Popen")
    def test_hyprland_safe_memory_and_commands(self, mock_popen, mock_run):
        setter = HyprlandWallpaperSetter(hypr_config_dir=self.hypr_config_dir)

        # Mock pgrep and hyprctl calls
        mock_proc_ok = MagicMock()
        mock_proc_ok.returncode = 0
        mock_run.return_value = mock_proc_ok

        # 1. Apply image 1
        ok1, msg1 = setter.apply_wallpaper(self.test_image1)
        self.assertTrue(ok1)
        self.assertEqual(setter.active_wallpaper, self.test_image1)

        # Verify preload and wallpaper were called with image 1
        abs1 = str(self.test_image1.resolve())
        mock_run.assert_any_call(
            ["hyprctl", "hyprpaper", "preload", abs1],
            capture_output=True,
            text=True,
            check=False,
            timeout=5,
        )
        mock_run.assert_any_call(
            ["hyprctl", "hyprpaper", "wallpaper", f",{abs1}"],
            capture_output=True,
            text=True,
            check=False,
            timeout=5,
        )

        # Verify config was persisted
        conf_file = self.hypr_config_dir / "hyprpaper.conf"
        self.assertTrue(conf_file.is_file())
        conf_text = conf_file.read_text()
        self.assertIn(f"preload = {abs1}", conf_text)
        self.assertIn(f"wallpaper = ,{abs1}", conf_text)

        # 2. Apply image 2 (must unload image 1, but NEVER 'unload all')
        abs2 = str(self.test_image2.resolve())
        ok2, msg2 = setter.apply_wallpaper(self.test_image2)
        self.assertTrue(ok2)
        self.assertEqual(setter.active_wallpaper, self.test_image2)

        # Verify unload was specifically called for old image 1
        mock_run.assert_any_call(
            ["hyprctl", "hyprpaper", "unload", abs1],
            capture_output=True,
            check=False,
            timeout=5,
        )

        # Verify 'unload all' was NEVER called
        for call_args in mock_run.call_args_list:
            cmd = call_args[0][0]
            if len(cmd) >= 4 and cmd[0] == "hyprctl" and cmd[1] == "hyprpaper":
                self.assertNotEqual(cmd[2:], ["unload", "all"])

        # Verify backup was created
        backup_file = self.hypr_config_dir / "hyprpaper.conf.bak"
        self.assertTrue(backup_file.is_file())

    @patch("subprocess.run")
    def test_gnome_setter(self, mock_run):
        mock_proc_ok = MagicMock()
        mock_proc_ok.returncode = 0
        mock_run.return_value = mock_proc_ok

        setter = GNOMEWallpaperSetter()
        ok, msg = setter.apply_wallpaper(self.test_image1)
        self.assertTrue(ok)

        uri = self.test_image1.resolve().as_uri()
        mock_run.assert_any_call(
            ["gsettings", "set", "org.gnome.desktop.background", "picture-uri", uri],
            check=True,
            capture_output=True,
            timeout=5,
        )
        mock_run.assert_any_call(
            ["gsettings", "set", "org.gnome.desktop.background", "picture-uri-dark", uri],
            check=False,
            capture_output=True,
            timeout=5,
        )


if __name__ == "__main__":
    unittest.main()
