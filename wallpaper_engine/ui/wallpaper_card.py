"""Wallpaper card widget with asynchronous thumbnail loading and badge overlays."""

import concurrent.futures
from pathlib import Path
from typing import Callable, Optional
import traceback

import gi
gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Adw, Gdk, GLib, Gtk

from wallpaper_engine.core.cache_manager import CacheManager
from wallpaper_engine.core.models import Wallpaper


class WallpaperCard(Gtk.Box):
    """Card representing a single wallpaper in the grid."""

    def __init__(
        self,
        wallpaper: Wallpaper,
        cache_manager: CacheManager,
        on_click: Callable[[Wallpaper], None],
        on_favorite_toggle: Optional[Callable[[Wallpaper, bool], None]] = None,
        is_favorite: bool = False,
        executor: Optional[concurrent.futures.ThreadPoolExecutor] = None,
    ) -> None:
        super().__init__(orientation=Gtk.Orientation.VERTICAL, spacing=4)
        self.wallpaper = wallpaper
        self.cache_manager = cache_manager
        self.on_click = on_click
        self.on_favorite_toggle = on_favorite_toggle
        self.is_favorite = is_favorite
        self.executor = executor
        self._is_destroyed = False

        self.set_size_request(240, 160)
        self.set_cursor(Gdk.Cursor.new_from_name("pointer", None))

        # CSS Styling
        self.add_css_class("card")
        self.add_css_class("wallpaper-card")

        # Container for picture and overlay badges
        overlay = Gtk.Overlay()
        overlay.set_size_request(240, 135)
        overlay.set_overflow(Gtk.Overflow.HIDDEN)

        # Image widget
        self.picture = Gtk.Picture()
        self.picture.set_hexpand(True)
        self.picture.set_vexpand(True)
        self.picture.set_content_fit(Gtk.ContentFit.COVER)
        self.picture.set_size_request(240, 135)
        overlay.set_child(self.picture)
        
        # Loading skeleton/spinner
        self.loading_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        self.loading_box.set_halign(Gtk.Align.CENTER)
        self.loading_box.set_valign(Gtk.Align.CENTER)
        self.spinner = Gtk.Spinner()
        self.spinner.set_size_request(24, 24)
        self.spinner.start()
        self.loading_box.append(self.spinner)
        overlay.add_overlay(self.loading_box)

        # Top Overlay: Badges
        top_bar = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        top_bar.set_margin_top(6)
        top_bar.set_margin_start(6)
        top_bar.set_margin_end(6)
        top_bar.set_valign(Gtk.Align.START)

        # Provider badge
        prov_label = Gtk.Label(label=wallpaper.provider_name)
        prov_label.add_css_class("caption")
        prov_label.add_css_class("provider-badge")
        top_bar.append(prov_label)

        # Resolution badge if known
        if wallpaper.is_4k_or_more:
            res_label = Gtk.Label(label="4K")
            res_label.add_css_class("caption")
            res_label.add_css_class("res-badge-4k")
            top_bar.append(res_label)
        elif wallpaper.is_1080p_or_more:
            res_label = Gtk.Label(label="HD")
            res_label.add_css_class("caption")
            res_label.add_css_class("res-badge")
            top_bar.append(res_label)

        # Spacer
        spacer = Gtk.Box()
        spacer.set_hexpand(True)
        top_bar.append(spacer)

        # Favorite button
        self.fav_btn = Gtk.Button()
        self.fav_btn.set_icon_name("starred-symbolic" if self.is_favorite else "non-starred-symbolic")
        self.fav_btn.add_css_class("flat")
        self.fav_btn.add_css_class("circular")
        self.fav_btn.connect("clicked", self._on_fav_clicked)
        top_bar.append(self.fav_btn)

        overlay.add_overlay(top_bar)
        self.append(overlay)

        # Title label
        title_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL)
        title_box.set_margin_start(4)
        title_box.set_margin_end(4)
        title_box.set_margin_bottom(4)

        self.title_label = Gtk.Label(label=wallpaper.title)
        self.title_label.set_ellipsize(3)  # PANGO_ELLIPSIZE_END
        self.title_label.set_max_width_chars(25)
        self.title_label.set_halign(Gtk.Align.START)
        self.title_label.add_css_class("caption")
        title_box.append(self.title_label)

        self.append(title_box)

        # Click gesture
        gesture = Gtk.GestureClick.new()
        gesture.connect("released", self._on_card_clicked)
        self.add_controller(gesture)

        # Asynchronously load thumbnail
        self._load_thumbnail()

    def _on_card_clicked(self, gesture, n_press, x, y):
        print(f"[PREVIEW DEBUG] wallpaper card clicked", flush=True)
        print(f"[PREVIEW DEBUG] card wallpaper ID: {self.wallpaper.id}", flush=True)
        print(f"[PREVIEW DEBUG] card wallpaper title: {self.wallpaper.title}", flush=True)
        print(f"[PREVIEW DEBUG] card wallpaper image_url: {self.wallpaper.image_url}", flush=True)
        print(f"[PREVIEW DEBUG] card wallpaper thumbnail_url: {self.wallpaper.thumbnail_url}", flush=True)
        try:
            self.on_click(self.wallpaper)
        except Exception:
            traceback.print_exc()

    def _on_fav_clicked(self, btn):
        self.is_favorite = not self.is_favorite
        self.fav_btn.set_icon_name("starred-symbolic" if self.is_favorite else "non-starred-symbolic")
        if self.on_favorite_toggle:
            self.on_favorite_toggle(self.wallpaper, self.is_favorite)

    def _load_thumbnail(self):
        url = self.wallpaper.thumbnail_url or self.wallpaper.image_url
        if not url:
            return
        print(f"[DISCOVER DEBUG] thumbnail requested: {url}", flush=True)

        # Check local cache first
        local_path = self.cache_manager.get_thumbnail_path(url)
        if local_path and local_path.is_file():
            self._apply_file(local_path)
            return

        # If it's a file:// URL
        if url.startswith("file://"):
            p = Path(url[7:])
            if p.is_file():
                self._apply_file(p)
            return

        # Fetch in thread pool
        if self.executor:
            self.executor.submit(self._fetch_thumb_task, url)

    def _fetch_thumb_task(self, url: str):
        if self._is_destroyed:
            return
        try:
            path = self.cache_manager.fetch_and_cache_thumbnail(url)
            if path and path.is_file() and not self._is_destroyed:
                GLib.idle_add(self._apply_file, path)
        except Exception:
            traceback.print_exc()

    def _apply_file(self, path: Path):
        if not self._is_destroyed and path.is_file():
            try:
                from gi.repository import GdkPixbuf, Gdk
                pixbuf = GdkPixbuf.Pixbuf.new_from_file(str(path))
                texture = Gdk.Texture.new_for_pixbuf(pixbuf)
                self.picture.set_paintable(texture)
                
                if hasattr(self, 'loading_box'):
                    self.loading_box.set_visible(False)
                if hasattr(self, 'spinner'):
                    self.spinner.stop()
            except Exception:
                traceback.print_exc()
        return False
