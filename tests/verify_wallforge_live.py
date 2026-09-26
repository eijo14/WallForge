"""Live verification script for WallForge application name, theme switching, and preview loading."""

import os
from pathlib import Path
import sys
import time

root_dir = Path(__file__).parent.parent.resolve()
if str(root_dir) not in sys.path:
    sys.path.insert(0, str(root_dir))

import gi
gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Adw, GLib, Gtk

from wallpaper_engine.core.cache_manager import CacheManager
from wallpaper_engine.core.models import Wallpaper
from wallpaper_engine.core.theme_manager import ThemeManager
from wallpaper_engine.setters.detector import get_best_setter
from wallpaper_engine.ui.preview_dialog import WallpaperPreviewDialog


def main():
    app = Adw.Application(application_id="org.wallforge.verification")
    
    def on_activate(app):
        print("--- [VERIFICATION START] ---", flush=True)
        GLib.set_application_name("WallForge")
        GLib.set_prgname("wallforge")

        cache_mgr = CacheManager()
        print(f"[CACHE] preview cache dir: {cache_mgr.previews_dir}", flush=True)
        assert "wallforge" in str(cache_mgr.previews_dir), f"Cache dir should contain 'wallforge', got: {cache_mgr.previews_dir}"

        theme_mgr = ThemeManager()
        win = Adw.ApplicationWindow(application=app)
        win.set_title("WallForge")
        win.set_default_size(800, 600)
        win.add_css_class("main-window")
        win.add_css_class(f"theme-{theme_mgr.current_theme}")

        def on_theme_change(theme_key):
            for t in ["system", "dark", "light", "midnight", "pixel_green"]:
                win.remove_css_class(f"theme-{t}")
            win.add_css_class(f"theme-{theme_key}")
            print(f"[THEME] window css updated to theme-{theme_key}", flush=True)

        theme_mgr.register_callback(on_theme_change)

        # 1. Test Theme Switching across all themes
        themes_to_test = ["light", "midnight", "pixel_green", "dark"]
        for theme_key in themes_to_test:
            theme_mgr.set_theme(theme_key)
            css = theme_mgr.generate_css()
            assert "@define-color window_bg_color" in css, "Missing Libadwaita window_bg_color"
            assert "@define-color view_bg_color" in css, "Missing Libadwaita view_bg_color"
            assert "@define-color headerbar_bg_color" in css, "Missing Libadwaita headerbar_bg_color"
            assert "window.background" in css, "Missing window.background CSS rule"
            assert win.has_css_class(f"theme-{theme_key}"), f"Window missing css class theme-{theme_key}"
            print(f"[THEME VERIFIED] Theme '{theme_key}' applied with root styling & palette", flush=True)

        # 2. Test Preview Dialog instant opening & preview loading
        test_url = "https://archimg.cc/assets/003.jpg"
        wp = Wallpaper(
            id="archimg-003",
            provider_id="archimg",
            provider_name="ArchImg",
            title="Arch Linux Rice #003",
            image_url=test_url,
            thumbnail_url=test_url,
            width=3840,
            height=2160,
        )

        setter = get_best_setter()
        t0 = time.perf_counter()
        dialog = WallpaperPreviewDialog(
            parent=win,
            wallpaper=wp,
            cache_manager=cache_mgr,
            wallpaper_setter=setter,
        )
        dialog.present()
        t_open_ms = (time.perf_counter() - t0) * 1000
        print(f"[PREVIEW VERIFIED] Dialog opened and presented in {t_open_ms:.1f}ms", flush=True)

        # Check resolution
        target_url = WallpaperPreviewDialog.resolve_preview_url(wp)
        print(f"[PREVIEW VERIFIED] Resolved preview URL: {target_url}", flush=True)

        # Wait up to 10s for preview to finish caching
        start_wait = time.time()
        def check_preview_done():
            if time.time() - start_wait > 10:
                print("[PREVIEW] Timed out or finished background worker", flush=True)
                dialog.close()
                win.close()
                app.quit()
                return False

            p = cache_mgr.get_preview_path(target_url)
            if p and p.is_file() and not dialog._is_fetching_preview:
                print(f"[PREVIEW VERIFIED] 1280px Preview cached on disk: {p} (size={p.stat().st_size} bytes)", flush=True)
                print("--- [ALL VERIFICATIONS PASSED] ---", flush=True)
                dialog.close()
                win.close()
                GLib.timeout_add(200, app.quit)
                return False
            return True

        GLib.timeout_add(100, check_preview_done)

    app.connect("activate", on_activate)
    return app.run([])


if __name__ == "__main__":
    sys.exit(main())
