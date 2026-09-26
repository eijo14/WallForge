"""Unit tests for expanded Desktop Environment setters and detector."""

import os
from pathlib import Path
import unittest
from unittest.mock import patch

from wallpaper_engine.setters.detector import detect_environment_name, get_all_registered_setters
from wallpaper_engine.setters.extended import (
    CinnamonWallpaperSetter,
    MATEWallpaperSetter,
    SwayWallpaperSetter,
    XFCEWallpaperSetter,
)
from wallpaper_engine.setters.kde import KDEPlasmaWallpaperSetter


class TestExtendedSetters(unittest.TestCase):
    def test_kde_plasma_setter(self):
        setter = KDEPlasmaWallpaperSetter()
        self.assertEqual(setter.name, "KDE Plasma (plasma-apply-wallpaperimage)")

    def test_xfce_setter(self):
        setter = XFCEWallpaperSetter()
        self.assertEqual(setter.name, "XFCE (xfconf-query)")

    def test_mate_setter(self):
        setter = MATEWallpaperSetter()
        self.assertEqual(setter.name, "MATE (gsettings)")

    def test_cinnamon_setter(self):
        setter = CinnamonWallpaperSetter()
        self.assertEqual(setter.name, "Cinnamon (gsettings)")

    def test_sway_setter(self):
        setter = SwayWallpaperSetter()
        self.assertEqual(setter.name, "Sway (swaymsg / swaybg)")

    def test_detect_environment_name_hyprland(self):
        with patch.dict(os.environ, {"HYPRLAND_INSTANCE_SIGNATURE": "1"}):
            self.assertEqual(detect_environment_name(), "Hyprland")

    def test_detect_environment_name_kde(self):
        with patch.dict(os.environ, {"XDG_CURRENT_DESKTOP": "KDE", "HYPRLAND_INSTANCE_SIGNATURE": ""}, clear=True):
            self.assertEqual(detect_environment_name(), "KDE Plasma")

    def test_detect_environment_name_gnome(self):
        with patch.dict(os.environ, {"XDG_CURRENT_DESKTOP": "GNOME", "HYPRLAND_INSTANCE_SIGNATURE": ""}, clear=True):
            self.assertEqual(detect_environment_name(), "GNOME")

    def test_get_all_registered_setters(self):
        all_setters = get_all_registered_setters()
        names = [s.name for s in all_setters]
        self.assertIn("Hyprland (hyprpaper)", names)
        self.assertIn("GNOME (gsettings)", names)
        self.assertIn("KDE Plasma (plasma-apply-wallpaperimage)", names)
        self.assertIn("XFCE (xfconf-query)", names)
        self.assertIn("Cinnamon (gsettings)", names)
        self.assertIn("MATE (gsettings)", names)
        self.assertIn("Sway (swaymsg / swaybg)", names)


if __name__ == "__main__":
    unittest.main()
