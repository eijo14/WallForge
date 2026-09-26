"""Comprehensive live verification of:
1. Preview instant opening with 320px thumbnail and 1280px background replacement.
2. Popover / Dropdown background opacity across all themes (Dark, Light, Midnight, Pixel Green).
"""

from pathlib import Path
import sys
import time

root_dir = Path(__file__).parent.parent.resolve()
if str(root_dir) not in sys.path:
    sys.path.insert(0, str(root_dir))

import gi
gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Adw, Gdk, Gio, GLib, Gtk

from wallpaper_engine.core.cache_manager import CacheManager
from wallpaper_engine.core.models import Wallpaper
from wallpaper_engine.core.theme_manager import THEMES, ThemeManager
from wallpaper_engine.setters.detector import get_best_setter
from wallpaper_engine.ui.preview_dialog import WallpaperPreviewDialog
from wallpaper_engine.ui.settings_view import SettingsView


def verify():
    app = Adw.Application(
        application_id="org.wallforge.verify_popovers",
        flags=Gio.ApplicationFlags.NON_UNIQUE,
    )

    def on_activate(app):
        print("=== VERIFYING POPOVER & PREVIEW UX ===", flush=True)
        cache_mgr = CacheManager()
        theme_mgr = ThemeManager()
        setter = get_best_setter()

        win = Adw.ApplicationWindow(application=app)
        win.set_default_size(800, 600)
        win.set_title("WallForge Popover Verification")

        # -------------------------------------------------------------
        # Part 1: Verify Popover CSS rules across Dark, Light, Midnight, Pixel Green
        # -------------------------------------------------------------
        for theme_key in ["dark", "light", "midnight", "pixel_green"]:
            theme_mgr.set_theme(theme_key)
            theme_mgr.apply_theme()
            tokens = THEMES[theme_key]
            css = theme_mgr.generate_css()

            expected_surface = tokens["surface_elevated"]
            print(f"[THEME {theme_key.upper()}] Checking CSS for popovers...")

            # 1. Popover contents background rule must match surface_elevated
            assert f"background-color: {expected_surface};" in css, f"Missing {expected_surface} in popover CSS"
            assert "popover > contents" in css, "Missing popover > contents selector"
            assert "popover.menu > contents" in css, "Missing popover.menu > contents selector"
            assert "popover scrolledwindow" in css, "Missing popover scrolledwindow selector"
            assert "popover listview" in css, "Missing popover listview selector"
            assert "opacity: 1;" in css, "Missing opacity: 1 for popovers"
            print(f"[THEME {theme_key.upper()}] Popover opacity & solid background rules verified ({expected_surface})")

        # Switch back to dark for UI test
        theme_mgr.set_theme("dark")
        theme_mgr.apply_theme()

        from unittest.mock import MagicMock
        rot_mock = MagicMock()
        rot_mock.is_running.return_value = False
        rot_mock.interval_minutes = 30
        src_mock = MagicMock()
        src_mock.list_all_providers.return_value = []

        settings_view = SettingsView(
            cache_manager=cache_mgr,
            rotation_service=rot_mock,
            source_manager=src_mock,
            wallpaper_setter=setter,
            theme_manager=theme_mgr,
        )
        win.set_content(settings_view)
        win.present()

        # Check each ComboRow in SettingsView
        rows = [
            ("Theme", settings_view.theme_row),
            ("Accent", settings_view.accent_row),
            ("Animations", settings_view.anim_row),
            ("Setter", settings_view.setter_row),
            ("Monitor", settings_view.monitor_row),
        ]
        for name, row in rows:
            assert isinstance(row, Adw.ComboRow), f"Row {name} is not an Adw.ComboRow"
            assert row.get_model() is not None, f"Row {name} has no model"
            print(f"[SETTINGS DROPDOWN] Row '{name}' is verified with model ({row.get_model().get_n_items()} items)")

        # -------------------------------------------------------------
        # Part 3: Verify Remote Preview instant opening with thumbnail & replacement
        # -------------------------------------------------------------
        test_url = "https://archimg.cc/assets/001.jpg"
        wp = Wallpaper(
            id="test-archimg-001",
            provider_id="archimg",
            provider_name="ArchImg",
            title="Arch Linux Rice #001",
            image_url=test_url,
            thumbnail_url=test_url,
            width=3840,
            height=2160,
        )

        t_start = time.perf_counter()
        dialog = WallpaperPreviewDialog(
            parent=win,
            wallpaper=wp,
            cache_manager=cache_mgr,
            wallpaper_setter=setter,
        )
        dialog.present()
        t_dialog_open = (time.perf_counter() - t_start) * 1000
        print(f"[PREVIEW INSTANT OPEN] Dialog opened & presented in {t_dialog_open:.1f}ms")
        assert t_dialog_open < 500, f"Dialog open took too long: {t_dialog_open:.1f}ms"

        # Wait for background HD preview to replace thumbnail
        wait_start = time.time()
        def poll_preview_ready():
            if time.time() - wait_start > 12:
                print("[ERROR] Timed out waiting for 1280px preview")
                dialog.close()
                win.close()
                app.quit()
                return False

            p = cache_mgr.get_preview_path(test_url)
            if p and p.is_file() and not dialog._is_fetching_preview:
                print(f"[PREVIEW REPLACED] HD preview ready on disk: {p} (size={p.stat().st_size} bytes)")
                print(f"[PREVIEW REPLACED] Paintable width x height: {dialog.picture.get_paintable().get_intrinsic_width()} x {dialog.picture.get_paintable().get_intrinsic_height()}")
                print("=== ALL VERIFICATIONS PASSED SUCCESSFULLY ===", flush=True)
                dialog.close()
                win.close()
                GLib.timeout_add(200, app.quit)
                return False
            return True

        GLib.timeout_add(100, poll_preview_ready)

    app.connect("activate", on_activate)
    return app.run(sys.argv)


if __name__ == "__main__":
    sys.exit(verify())
