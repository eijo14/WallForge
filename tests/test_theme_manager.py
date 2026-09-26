"""Unit tests for ThemeManager (Modern Pixel design tokens, themes, and CSS generation)."""

import json
from pathlib import Path
import shutil
import tempfile
import unittest

from wallpaper_engine.core.theme_manager import THEMES, ACCENT_COLORS, ThemeManager


class TestThemeManager(unittest.TestCase):
    def setUp(self):
        self.temp_dir = Path(tempfile.mkdtemp(prefix="wp_theme_test_"))
        self.mgr = ThemeManager(config_dir=self.temp_dir)

    def tearDown(self):
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_themes_definition(self):
        expected_themes = ["dark", "light", "midnight", "pixel_green"]
        for t in expected_themes:
            self.assertIn(t, THEMES)
            tokens = THEMES[t]
            self.assertIn("bg", tokens)
            self.assertIn("surface", tokens)
            self.assertIn("border", tokens)
            self.assertIn("accent", tokens)
            self.assertIn("font_mono", tokens)

    def test_default_theme_is_dark(self):
        self.assertEqual(self.mgr.current_theme, "dark")
        self.assertEqual(self.mgr.animation_mode, "minimal")

    def test_generate_css_contains_design_tokens(self):
        css = self.mgr.generate_css()
        self.assertIn(".pixel-sidebar", css)
        self.assertIn(".pixel-nav-btn", css)
        self.assertIn(".pixel-header", css)
        self.assertIn(".wallpaper-card", css)
        self.assertIn(".provider-badge", css)
        self.assertIn(".filter-chip", css)

    def test_theme_switching(self):
        self.mgr.set_theme("pixel_green")
        self.assertEqual(self.mgr.current_theme, "pixel_green")
        css = self.mgr.generate_css()
        self.assertIn("#22c55e", css)  # Phosphor green accent

        self.mgr.set_theme("midnight")
        self.assertEqual(self.mgr.current_theme, "midnight")
        css_midnight = self.mgr.generate_css()
        self.assertIn("#6366f1", css_midnight)  # Indigo/midnight accent

    def test_accent_switching(self):
        self.mgr.set_accent("amber")
        self.assertEqual(self.mgr.current_accent, "amber")
        css = self.mgr.generate_css()
        self.assertIn(ACCENT_COLORS["amber"], css)

    def test_animation_modes(self):
        self.mgr.set_animation_mode("off")
        self.assertEqual(self.mgr.get_transition_speed_ms(), 0)
        self.mgr.set_animation_mode("minimal")
        self.assertEqual(self.mgr.get_transition_speed_ms(), 120)
        self.mgr.set_animation_mode("full")
        self.assertEqual(self.mgr.get_transition_speed_ms(), 180)

    def test_persistence(self):
        self.mgr.set_theme("midnight")
        self.mgr.set_accent("magenta")
        self.mgr.set_animation_mode("full")

        # Reload new instance from same directory
        mgr2 = ThemeManager(config_dir=self.temp_dir)
        self.assertEqual(mgr2.current_theme, "midnight")
        self.assertEqual(mgr2.current_accent, "magenta")
        self.assertEqual(mgr2.animation_mode, "full")


if __name__ == "__main__":
    unittest.main()
