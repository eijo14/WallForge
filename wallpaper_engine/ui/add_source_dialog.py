"""Dialog for adding and validating custom wallpaper sources."""

import concurrent.futures
from typing import Callable, Optional

import gi
gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Adw, GLib, Gtk

from wallpaper_engine.providers.custom import validate_custom_source


class AddSourceDialog(Adw.Window):
    """Modal dialog to configure and validate a new custom wallpaper source."""

    def __init__(self, parent: Gtk.Window, on_source_added: Callable[[dict], None]) -> None:
        super().__init__()
        self.set_transient_for(parent)
        self.set_modal(True)
        self.set_default_size(520, 560)
        self.set_title("Add Custom Wallpaper Source")

        self.on_source_added = on_source_added
        self._executor = concurrent.futures.ThreadPoolExecutor(max_workers=1)

        # Toolbar & Header
        toolbar = Adw.ToolbarView()
        header = Adw.HeaderBar()
        toolbar.add_top_bar(header)

        # Content Box
        scrolled = Gtk.ScrolledWindow()
        scrolled.set_vexpand(True)

        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=14)
        box.set_margin_start(24)
        box.set_margin_end(24)
        box.set_margin_top(16)
        box.set_margin_bottom(24)

        # Section: Source Details
        pref_group = Adw.PreferencesGroup()
        pref_group.set_title("Source Configuration")
        pref_group.set_description("Connect an external feed, API, image manifest, or local folder.")

        # Name
        self.name_row = Adw.EntryRow()
        self.name_row.set_title("Source Name")
        self.name_row.set_text("My Custom Wallpapers")
        pref_group.add(self.name_row)

        # Type Dropdown
        self.type_row = Adw.ComboRow()
        self.type_row.set_title("Source Type")
        type_model = Gtk.StringList.new([
            "JSON Feed (Array of images)",
            "REST API (Search & Pagination)",
            "Image Manifest (archimg-style text list)",
            "Local Folder (Local image directory)",
        ])
        self.type_row.set_model(type_model)
        pref_group.add(self.type_row)

        # URL / Path
        self.url_row = Adw.EntryRow()
        self.url_row.set_title("URL or Folder Path")
        self.url_row.set_text("https://example.com/wallpapers.json")
        pref_group.add(self.url_row)

        # API Key (Optional)
        self.key_row = Adw.PasswordEntryRow()
        self.key_row.set_title("API Key / Token (Optional)")
        pref_group.add(self.key_row)

        box.append(pref_group)

        # Section: Field Mappings (for JSON feeds)
        mapping_group = Adw.PreferencesGroup()
        mapping_group.set_title("JSON Field Mapping (Optional)")
        mapping_group.set_description("Specify keys in the response object (e.g. data.results).")

        self.img_field_row = Adw.EntryRow()
        self.img_field_row.set_title("Image URL Field")
        self.img_field_row.set_text("url")
        mapping_group.add(self.img_field_row)

        self.thumb_field_row = Adw.EntryRow()
        self.thumb_field_row.set_title("Thumbnail URL Field")
        self.thumb_field_row.set_text("thumbnail_url")
        mapping_group.add(self.thumb_field_row)

        self.title_field_row = Adw.EntryRow()
        self.title_field_row.set_title("Title Field")
        self.title_field_row.set_text("title")
        mapping_group.add(self.title_field_row)

        box.append(mapping_group)

        # Validation Status Box
        self.status_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
        self.status_box.set_margin_top(8)

        self.spinner = Gtk.Spinner()
        self.spinner.set_size_request(20, 20)
        self.spinner.set_halign(Gtk.Align.CENTER)
        self.spinner.set_visible(False)
        self.status_box.append(self.spinner)

        self.result_label = Gtk.Label()
        self.result_label.set_wrap(True)
        self.result_label.add_css_class("meta-mono")
        self.result_label.set_visible(False)
        self.status_box.append(self.result_label)

        box.append(self.status_box)

        # Action Buttons
        btn_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12)
        btn_box.set_halign(Gtk.Align.END)
        btn_box.set_margin_top(8)

        self.test_btn = Gtk.Button(label="Test Connection")
        self.test_btn.connect("clicked", self._on_test_clicked)
        btn_box.append(self.test_btn)

        self.add_btn = Gtk.Button(label="Add Source")
        self.add_btn.add_css_class("suggested-action")
        self.add_btn.connect("clicked", self._on_add_clicked)
        btn_box.append(self.add_btn)

        box.append(btn_box)

        scrolled.set_child(box)
        toolbar.set_content(scrolled)
        self.set_content(toolbar)

    def _get_config_dict(self) -> dict:
        type_idx = self.type_row.get_selected()
        type_map = {
            0: "json_feed",
            1: "rest_api",
            2: "image_manifest",
            3: "local_folder",
        }
        return {
            "name": self.name_row.get_text().strip(),
            "type": type_map.get(type_idx, "json_feed"),
            "url": self.url_row.get_text().strip(),
            "api_key": self.key_row.get_text().strip(),
            "image_field": self.img_field_row.get_text().strip() or "url",
            "thumbnail_field": self.thumb_field_row.get_text().strip(),
            "title_field": self.title_field_row.get_text().strip() or "title",
        }

    def _on_test_clicked(self, btn):
        cfg = self._get_config_dict()
        self.spinner.set_visible(True)
        self.spinner.start()
        self.result_label.set_visible(False)
        self.test_btn.set_sensitive(False)

        def worker():
            success, msg, details = validate_custom_source(cfg)
            GLib.idle_add(self._on_test_done, success, msg, details)

        self._executor.submit(worker)

    def _on_test_done(self, success: bool, msg: str, details: dict):
        self.spinner.stop()
        self.spinner.set_visible(False)
        self.test_btn.set_sensitive(True)

        lines = [msg]
        if details:
            lines.append("✓ Source reachable" if details.get("reachable") else "✕ Unreachable")
            lines.append("✓ Response format recognized" if details.get("format_recognized") else "✕ Format not recognized")
            lines.append("✓ Image field detected" if details.get("image_field_detected") else "✕ No image fields found")
            if details.get("pagination_detected"):
                lines.append("✓ Pagination detected")

        self.result_label.set_text("\n".join(lines))
        self.result_label.set_visible(True)
        return False

    def _on_add_clicked(self, btn):
        cfg = self._get_config_dict()
        if not cfg["name"] or not cfg["url"]:
            self.result_label.set_text("Please enter both a source name and URL/path.")
            self.result_label.set_visible(True)
            return

        self.on_source_added(cfg)
        self.close()
