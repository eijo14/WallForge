"""Script to verify the exact preview execution trace with a real remote undownloaded wallpaper."""

import os
from pathlib import Path
import sys
import time

import gi
gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Adw, GLib, Gtk

from wallpaper_engine.core.cache_manager import CacheManager
from wallpaper_engine.core.models import Wallpaper
from wallpaper_engine.setters.generic import GenericLinuxWallpaperSetter
from wallpaper_engine.ui.preview_dialog import WallpaperPreviewDialog
from wallpaper_engine.ui.wallpaper_card import WallpaperCard


def main():
    app = Adw.Application(application_id="org.test.verify_preview")
    
    def on_activate(app):
        cache_manager = CacheManager()
        setter = GenericLinuxWallpaperSetter()

        # Real undownloaded wallpaper from archimg.cc
        test_url = "https://archimg.cc/assets/002.jpg"

        # Ensure it is NOT cached beforehand
        prev_path = cache_manager.get_preview_path(test_url)
        if prev_path and prev_path.is_file():
            prev_path.unlink()
        wp_path = cache_manager.get_wallpaper_path(test_url)
        if wp_path and wp_path.is_file():
            wp_path.unlink()

        wp = Wallpaper(
            id="archimg-002",
            provider_id="archimg",
            provider_name="ArchImg",
            title="Arch Linux Rice #002",
            image_url=test_url,
            thumbnail_url=test_url,
            width=3840,
            height=2160,
        )

        parent_window = Adw.ApplicationWindow(application=app)
        parent_window.set_default_size(400, 300)

        opened_dialog = None

        def open_preview(wallpaper):
            nonlocal opened_dialog
            print("[PREVIEW DEBUG] opening PreviewDialog", flush=True)
            print(f"[PREVIEW DEBUG] wallpaper.id = {wallpaper.id}", flush=True)
            print(f"[PREVIEW DEBUG] wallpaper.title = {wallpaper.title}", flush=True)
            print(f"[PREVIEW DEBUG] wallpaper.image_url = {wallpaper.image_url}", flush=True)
            print(f"[PREVIEW DEBUG] wallpaper.thumbnail_url = {wallpaper.thumbnail_url}", flush=True)
            local_p = cache_manager.get_wallpaper_path(wallpaper.image_url) if wallpaper.image_url else None
            print(f"[PREVIEW DEBUG] wallpaper.local_path = {local_p}", flush=True)

            opened_dialog = WallpaperPreviewDialog(
                parent_window,
                wallpaper,
                cache_manager,
                setter,
            )
            opened_dialog.present()
            print("[PREVIEW DEBUG] PreviewDialog presented", flush=True)

        card = WallpaperCard(
            wp,
            cache_manager,
            on_click=open_preview,
        )

        # Trigger card click
        card._on_card_clicked(None, 1, 0, 0)

        # Poll until preview worker completes
        start_time = time.time()
        def check_done():
            if time.time() - start_time > 15:
                print("[ERROR] Timed out waiting for preview", flush=True)
                app.quit()
                return False
            
            p = cache_manager.get_preview_path(test_url)
            if p and p.is_file() and not opened_dialog._is_fetching_preview:
                print(f"[PREVIEW DEBUG] Verification complete! Preview file on disk: {p}", flush=True)
                GLib.timeout_add(500, app.quit)
                return False
            return True

        GLib.timeout_add(100, check_done)

    app.connect("activate", on_activate)
    return app.run([])


if __name__ == "__main__":
    sys.exit(main())
