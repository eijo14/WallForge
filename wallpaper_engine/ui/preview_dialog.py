"""Detailed wallpaper preview dialog with metadata, direct remote preview, and action buttons."""

import concurrent.futures
from pathlib import Path
import time
import traceback
from typing import Callable, Optional

import gi
gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Adw, Gdk, GLib, Gtk

from wallpaper_engine.core.cache_manager import CacheManager
from wallpaper_engine.core.models import Wallpaper
from wallpaper_engine.setters.base import WallpaperSetter


class WallpaperPreviewDialog(Adw.Window):
    """Modal dialog displaying wallpaper details, metadata, direct preview, and action controls."""

    def __init__(
        self,
        parent: Gtk.Window,
        wallpaper: Wallpaper,
        cache_manager: CacheManager,
        wallpaper_setter: WallpaperSetter,
        on_favorite_toggle: Optional[Callable[[Wallpaper, bool], None]] = None,
        is_favorite: bool = False,
        on_status_msg: Optional[Callable[[str], None]] = None,
    ) -> None:
        self._t_dialog_open = time.perf_counter()
        print(f"[PREVIEW] dialog opened: {wallpaper.id}", flush=True)
        print("[PREVIEW DEBUG] PreviewDialog created", flush=True)
        super().__init__()
        self.set_transient_for(parent)
        self.set_modal(True)
        self.set_default_size(760, 680)
        self.set_title(wallpaper.title)

        self.wallpaper = wallpaper
        self.cache_manager = cache_manager
        self.wallpaper_setter = wallpaper_setter
        self.on_favorite_toggle = on_favorite_toggle
        self.is_favorite = is_favorite
        self.on_status_msg = on_status_msg

        self._is_destroyed = False
        self._is_fetching_preview = False
        self._executor = concurrent.futures.ThreadPoolExecutor(max_workers=2)

        # Hook close-request for memory cleanup and task cancellation
        self.connect("close-request", self._on_close_request)

        # Handle Escape key to close PreviewDialog without bubbling to parent window
        key_ctrl = Gtk.EventControllerKey.new()
        key_ctrl.set_propagation_phase(Gtk.PropagationPhase.CAPTURE)
        key_ctrl.connect("key-pressed", self._on_key_pressed)
        self.add_controller(key_ctrl)

        # Main Layout
        toolbar_view = Adw.ToolbarView()
        header = Adw.HeaderBar()
        toolbar_view.add_top_bar(header)

        # Scrolled content
        scrolled = Gtk.ScrolledWindow()
        scrolled.set_vexpand(True)

        content_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=16)
        content_box.set_margin_start(24)
        content_box.set_margin_end(24)
        content_box.set_margin_top(16)
        content_box.set_margin_bottom(24)

        # Large Image Preview
        self.picture = Gtk.Picture()
        self.picture.set_hexpand(True)
        self.picture.set_vexpand(True)
        self.picture.set_content_fit(Gtk.ContentFit.CONTAIN)
        self.picture.set_size_request(680, 380)
        self.picture.add_css_class("card")
        content_box.append(self.picture)

        # Loading Box (Spinner + Text)
        self.loading_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        self.loading_box.set_halign(Gtk.Align.CENTER)
        self.spinner = Gtk.Spinner()
        self.spinner.set_size_request(24, 24)
        self.loading_box.append(self.spinner)
        self.status_label = Gtk.Label(label="Loading preview...")
        self.status_label.add_css_class("dim-label")
        self.loading_box.append(self.status_label)
        self.loading_box.set_visible(False)
        content_box.append(self.loading_box)

        # Error Box (Error Message + Retry Button)
        self.error_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12)
        self.error_box.set_halign(Gtk.Align.CENTER)
        self.error_label = Gtk.Label(label="")
        self.error_label.add_css_class("error")
        self.error_label.set_wrap(True)
        self.retry_btn = Gtk.Button(label="Retry Preview")
        self.retry_btn.add_css_class("pill")
        self.retry_btn.connect("clicked", self._on_retry_clicked)
        self.error_box.append(self.error_label)
        self.error_box.append(self.retry_btn)
        self.error_box.set_visible(False)
        content_box.append(self.error_box)

        # Title & Author
        title_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
        title_label = Gtk.Label(label=wallpaper.title)
        title_label.add_css_class("title-1")
        title_label.set_halign(Gtk.Align.START)
        title_label.set_wrap(True)
        title_box.append(title_label)

        author_text = f"By: {wallpaper.author}" if wallpaper.author != "Unknown" else f"Source: {wallpaper.provider_name}"
        author_label = Gtk.Label(label=author_text)
        author_label.add_css_class("dim-label")
        author_label.set_halign(Gtk.Align.START)
        title_box.append(author_label)
        content_box.append(title_box)

        # Action Buttons Row: Apply, Download, Favorite, Close
        actions_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12)
        actions_box.set_halign(Gtk.Align.START)

        # Apply button
        self.apply_btn = Gtk.Button(label="Set as Wallpaper")
        self.apply_btn.add_css_class("suggested-action")
        self.apply_btn.add_css_class("pill")
        self.apply_btn.set_accessible_role(Gtk.AccessibleRole.BUTTON)
        if not self.wallpaper_setter.is_available():
            self.apply_btn.set_sensitive(False)
            self.apply_btn.set_tooltip_text("Wallpaper setting is unavailable on this system")
        else:
            self.apply_btn.set_tooltip_text("Apply this wallpaper to your desktop")
        self.apply_btn.connect("clicked", self._on_apply_clicked)
        actions_box.append(self.apply_btn)

        # Download button
        self.download_btn = Gtk.Button(label="Download")
        self.download_btn.add_css_class("pill")
        self.download_btn.set_tooltip_text("Download full-resolution wallpaper")
        self.download_btn.set_accessible_role(Gtk.AccessibleRole.BUTTON)
        self.download_btn.connect("clicked", self._on_download_clicked)
        actions_box.append(self.download_btn)

        # Favorite button
        self.fav_btn = Gtk.Button()
        self.fav_btn.set_icon_name("starred-symbolic" if self.is_favorite else "non-starred-symbolic")
        self.fav_btn.add_css_class("circular")
        self.fav_btn.set_tooltip_text("Toggle favorite")
        self.fav_btn.set_accessible_role(Gtk.AccessibleRole.BUTTON)
        self.fav_btn.connect("clicked", self._on_fav_clicked)
        actions_box.append(self.fav_btn)

        # Close button
        self.close_btn = Gtk.Button(label="Close")
        self.close_btn.add_css_class("pill")
        self.close_btn.set_tooltip_text("Close preview dialog (Esc)")
        self.close_btn.set_accessible_role(Gtk.AccessibleRole.BUTTON)
        self.close_btn.connect("clicked", lambda *a: self.close())
        actions_box.append(self.close_btn)

        # Open in Browser button
        if wallpaper.source_url:
            open_url_btn = Gtk.Button(label="Open Source Webpage")
            open_url_btn.add_css_class("flat")
            open_url_btn.connect("clicked", lambda *a: Gtk.show_uri(self, wallpaper.source_url, Gdk.CURRENT_TIME))
            actions_box.append(open_url_btn)

        content_box.append(actions_box)

        # Metadata Card (Adw.PreferencesGroup)
        pref_group = Adw.PreferencesGroup()
        pref_group.set_title("Wallpaper Details")

        # Provider
        row_prov = Adw.ActionRow(title="Provider", subtitle=wallpaper.provider_name)
        pref_group.add(row_prov)

        # Resolution & Ratio
        res_str = wallpaper.resolution_str
        if wallpaper.aspect_ratio != "Unknown":
            res_str += f" ({wallpaper.aspect_ratio})"
        row_res = Adw.ActionRow(title="Resolution", subtitle=res_str)
        pref_group.add(row_res)

        # License
        license_str = wallpaper.license
        if wallpaper.attribution_required:
            license_str += " (Attribution Required)"
        row_lic = Adw.ActionRow(title="License", subtitle=license_str)
        pref_group.add(row_lic)

        # Tags
        if wallpaper.tags:
            row_tags = Adw.ActionRow(title="Tags", subtitle=", ".join(wallpaper.tags[:8]))
            pref_group.add(row_tags)

        # Description if present
        if wallpaper.description:
            row_desc = Adw.ActionRow(title="Description", subtitle=wallpaper.description)
            pref_group.add(row_desc)

        content_box.append(pref_group)

        scrolled.set_child(content_box)
        toolbar_view.set_content(scrolled)
        self.set_content(toolbar_view)

        # Load preview directly without requiring prior download
        self._load_preview()

    def _on_key_pressed(self, controller, keyval, keycode, state):
        if keyval == Gdk.KEY_Escape:
            print("[KEY DEBUG] key pressed: Escape", flush=True)
            print("[KEY DEBUG] preview dialog open: True", flush=True)
            print("[KEY DEBUG] handling Escape → closing PreviewDialog", flush=True)
            self.close()
            return True
        return False

    def _set_picture_file(self, path: Path):
        """Safely set picture file if not destroyed. Never synchronously decode large originals."""
        if not self._is_destroyed and path and path.is_file():
            try:
                # If file is unusually large (> 2MB), avoid freezing UI thread and downscale off-thread
                if path.stat().st_size > 2_000_000:
                    self._executor.submit(self._generate_local_preview_task, path, self._resolve_preview_url())
                    return

                print(f"[PREVIEW RENDER DEBUG] preview path = {path}", flush=True)
                print(f"[PREVIEW RENDER DEBUG] file exists = {path.is_file()}", flush=True)
                print(f"[PREVIEW RENDER DEBUG] file size = {path.stat().st_size}", flush=True)
                print(f"[PREVIEW RENDER DEBUG] GTK picture widget = {self.picture}", flush=True)
                print(f"[PREVIEW RENDER DEBUG] GTK picture visible = {self.picture.get_visible()}", flush=True)
                print(f"[PREVIEW RENDER DEBUG] GTK picture mapped = {self.picture.get_mapped()}", flush=True)

                try:
                    texture = Gdk.Texture.new_from_filename(str(path))
                except Exception:
                    from gi.repository import GdkPixbuf
                    pixbuf = GdkPixbuf.Pixbuf.new_from_file(str(path))
                    texture = Gdk.Texture.new_for_pixbuf(pixbuf)
                self.picture.set_paintable(texture)

                print(f"[PREVIEW RENDER DEBUG] texture created = {texture}", flush=True)
                if texture:
                    print(f"[PREVIEW RENDER DEBUG] texture dimensions = {texture.get_width()} x {texture.get_height()}", flush=True)
            except Exception:
                traceback.print_exc()

    def _show_loading(self, text: str):
        self.status_label.set_text(text)
        self.loading_box.set_visible(True)
        self.spinner.start()

    def _hide_loading(self):
        self.spinner.stop()
        self.loading_box.set_visible(False)

    def _show_error(self, message: str):
        self.error_label.set_text(message)
        self.error_box.set_visible(True)

    def _hide_error(self):
        self.error_box.set_visible(False)

    @staticmethod
    def resolve_preview_url(wallpaper: Wallpaper) -> str:
        # Prefer fast high-quality CDN previews when provider provides one
        if wallpaper.provider_id == "wallhaven" and wallpaper.thumbnail_url:
            return wallpaper.thumbnail_url.replace("/small/", "/lg/")
        if wallpaper.provider_id == "nasa_apod" and wallpaper.thumbnail_url:
            return wallpaper.thumbnail_url
        if wallpaper.provider_id == "wikimedia" and wallpaper.thumbnail_url:
            return wallpaper.thumbnail_url
        return wallpaper.image_url or wallpaper.thumbnail_url

    def _resolve_preview_url(self) -> str:
        return self.resolve_preview_url(self.wallpaper)

    def _load_preview(self):
        """Load preview directly from remote image_url or local cache without requiring full download."""
        if self._is_destroyed:
            return

        preview_url = self._resolve_preview_url()
        if not preview_url:
            self._show_error("No image URL provided for this wallpaper.")
            return

        # 1. As an immediate progressive placeholder (<10ms), show 320px thumbnail
        thumb_url = self.wallpaper.thumbnail_url or preview_url
        thumb_path = self.cache_manager.get_thumbnail_path(thumb_url)
        self._thumbnail_displayed = False
        if thumb_path and thumb_path.is_file():
            print("[PREVIEW] thumbnail cache hit", flush=True)
            self._set_picture_file(thumb_path)
            self._thumbnail_displayed = True
        else:
            print("[PREVIEW] thumbnail cache miss", flush=True)

        # 2. Check if high-quality 1280px cached preview exists
        local_preview = self.cache_manager.get_preview_path(preview_url)
        if local_preview and local_preview.is_file():
            print("[PREVIEW] preview cache hit", flush=True)
            self._set_picture_file(local_preview)
            self._hide_loading()
            self._hide_error()
            t_total = (time.perf_counter() - self._t_dialog_open) * 1000
            print("[PREVIEW] GTK image update", flush=True)
            print(f"[PREVIEW] total preview time: {t_total:.1f} ms", flush=True)
            return

        # 3. Check if already downloaded as full wallpaper or file:// URL
        local_wp = self.cache_manager.get_wallpaper_path(self.wallpaper.image_url) if self.wallpaper.image_url else None
        local_source: Optional[Path] = None
        if local_wp and local_wp.is_file():
            local_source = local_wp
        elif preview_url.startswith("file://"):
            local_p = Path(preview_url[7:])
            if local_p.is_file():
                local_source = local_p
            else:
                self._show_error(f"Local file not found: {local_p}")
                return

        if local_source:
            # Full original exists locally. NEVER decode huge original synchronously into GTK!
            # Generate the 1280px preview off-thread using Pillow.
            self._show_loading("Preparing HD preview...")
            self._executor.submit(self._generate_local_preview_task, local_source, preview_url)
            return

        # 4. Fetch high-quality 1280px preview image asynchronously from remote CDN
        self._start_preview_fetch(preview_url, self._thumbnail_displayed)

    def _generate_local_preview_task(self, source_path: Path, url: str):
        if self._is_destroyed:
            return
        try:
            preview_path = self.cache_manager.create_preview_from_file(source_path, url, max_size=1280)
            if preview_path and preview_path.is_file():
                GLib.idle_add(self._on_preview_fetched, True, preview_path, "OK")
            else:
                GLib.idle_add(self._on_preview_fetched, False, None, "Failed to generate preview from local file")
        except Exception as exc:
            GLib.idle_add(self._on_preview_fetched, False, None, str(exc))

    def _start_preview_fetch(self, url: str, has_placeholder: bool):
        if self._is_fetching_preview:
            return
        self._is_fetching_preview = True
        self._hide_error()

        # Show small "Loading preview..." indicator while 1280px preview arrives
        self._show_loading("Loading high-quality preview...")

        try:
            self._executor.submit(self._fetch_preview_task, url)
        except Exception:
            traceback.print_exc()
            self._is_fetching_preview = False
            self._hide_loading()
            self._show_error("Failed to start preview worker")

    def _fetch_preview_task(self, url: str):
        try:
            ok, preview_path, msg = self.cache_manager.fetch_and_cache_preview(url)
            GLib.idle_add(self._on_preview_fetched, ok, preview_path, msg)
        except Exception as exc:
            GLib.idle_add(self._on_preview_fetched, False, None, str(exc))

    def _on_preview_fetched(self, ok: bool, preview_path: Optional[Path], msg: str):
        self._is_fetching_preview = False
        self._hide_loading()
        if self._is_destroyed:
            return False

        if ok and preview_path and preview_path.is_file():
            self._set_picture_file(preview_path)
            self._hide_error()
            t_total = (time.perf_counter() - self._t_dialog_open) * 1000
            print("[PREVIEW] GTK image update", flush=True)
            print(f"[PREVIEW] total preview time: {t_total:.1f} ms", flush=True)
        else:
            # If preview failed or timed out:
            # Keep thumbnail displayed if we have one!
            if self.picture.get_paintable() is not None:
                self._show_error("HD preview unavailable (using thumbnail). Click Retry to try again.")
            else:
                self._show_error(f"Preview unavailable: {msg}")
        return False

    def _on_retry_clicked(self, btn):
        print("[PREVIEW DEBUG] retry button clicked", flush=True)
        self._load_preview()

    def _on_fav_clicked(self, btn):
        self.is_favorite = not self.is_favorite
        self.fav_btn.set_icon_name("starred-symbolic" if self.is_favorite else "non-starred-symbolic")
        if self.on_favorite_toggle:
            self.on_favorite_toggle(self.wallpaper, self.is_favorite)

    def _on_download_clicked(self, btn):
        self.download_btn.set_sensitive(False)
        self._show_loading("Downloading full wallpaper...")
        self._executor.submit(self._download_task, False)

    def _on_apply_clicked(self, btn):
        self.apply_btn.set_sensitive(False)
        self._show_loading("Setting desktop wallpaper...")
        self._executor.submit(self._download_task, True)

    def _download_task(self, apply_after: bool):
        url = self.wallpaper.image_url
        if not url:
            GLib.idle_add(self._on_action_finished, "No image URL available.", None)
            return

        if url.startswith("file://"):
            local_path = Path(url[7:])
            ok, msg = True, "Local file ready"
        else:
            ext = "png" if url.lower().endswith(".png") else "jpg"
            ok, local_path, msg = self.cache_manager.download_wallpaper(url, extension=ext)

        if ok and local_path and local_path.is_file():
            # Trigger download tracking if required by provider terms (e.g. Unsplash)
            if getattr(self.wallpaper, "download_location", None):
                try:
                    from wallpaper_engine.providers.unsplash import report_unsplash_download
                    report_unsplash_download(self.wallpaper.download_location)
                except Exception:
                    pass

            if apply_after:
                app_ok, app_msg = self.wallpaper_setter.apply_wallpaper(local_path)
                status = "Wallpaper applied successfully!" if app_ok else f"Failed to apply: {app_msg}"
            else:
                status = f"Saved to {local_path.name}"
        else:
            status = f"Download failed: {msg}"

        GLib.idle_add(self._on_action_finished, status, local_path)

    def _on_action_finished(self, status: str, local_path: Optional[Path]):
        self._hide_loading()
        self.apply_btn.set_sensitive(self.wallpaper_setter.is_available())
        self.download_btn.set_sensitive(True)

        if local_path and local_path.is_file() and self.picture.get_paintable() is None:
            self._executor.submit(self._generate_local_preview_task, local_path, self._resolve_preview_url())

        if self.on_status_msg:
            self.on_status_msg(status)
        return False

    def _on_close_request(self, *args) -> bool:
        """Clean up memory and cancel background executor on window close."""
        print("[PREVIEW DEBUG] close-request received", flush=True)
        self._is_destroyed = True
        try:
            self.picture.set_paintable(None)
            self.picture.set_filename(None)
        except Exception:
            traceback.print_exc()
        self._executor.shutdown(wait=False, cancel_futures=True)
        return False
