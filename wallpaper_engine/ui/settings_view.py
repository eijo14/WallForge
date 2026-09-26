"""Modern Pixel Settings View with Appearance, Desktop, Performance, and Rotation controls."""

from pathlib import Path
from typing import Callable, Optional

import gi
gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Adw, Gtk

from wallpaper_engine.core.cache_manager import CacheManager
from wallpaper_engine.core.rotation_service import RotationService
from wallpaper_engine.core.source_manager import SourceManager
from wallpaper_engine.core.theme_manager import THEMES, ACCENT_COLORS, ThemeManager
from wallpaper_engine.setters.base import WallpaperSetter
from wallpaper_engine.setters.detector import (
    detect_environment_name,
    get_available_setters,
    get_best_setter,
)


class SettingsView(Adw.PreferencesPage):
    """Full Settings page containing Appearance, Desktop, Performance, Rotation, and Shortcuts."""

    def __init__(
        self,
        cache_manager: CacheManager,
        rotation_service: RotationService,
        source_manager: SourceManager,
        wallpaper_setter: WallpaperSetter,
        theme_manager: Optional[ThemeManager] = None,
        on_toast: Optional[Callable[[str], None]] = None,
        on_setter_change: Optional[Callable[[WallpaperSetter], None]] = None,
    ):
        super().__init__()
        self.set_title("Settings")
        self.set_icon_name("emblem-system-symbolic")

        self.cache_manager = cache_manager
        self.rotation_service = rotation_service
        self.source_manager = source_manager
        self.wallpaper_setter = wallpaper_setter
        self.theme_manager = theme_manager or ThemeManager()
        self.on_toast = on_toast
        self.on_setter_change = on_setter_change

        # =============================================================
        # Section 1: Appearance (Modern Pixel / Retro-Tech)
        # =============================================================
        group_appearance = Adw.PreferencesGroup()
        group_appearance.set_title("Appearance")
        group_appearance.set_description("Customize visual theme, accent colors, and animation policy.")
        self.add(group_appearance)

        # Theme Selector
        self.theme_row = Adw.ComboRow()
        self.theme_row.set_title("Theme")
        self.theme_keys = ["system", "dark", "light", "midnight", "pixel_green"]
        theme_labels = ["System", "Dark", "Light", "Midnight (Cosmic Blue)", "Pixel Green (Phosphor Terminal)"]
        self.theme_row.set_model(Gtk.StringList.new(theme_labels))
        if self.theme_manager.current_theme in self.theme_keys:
            self.theme_row.set_selected(self.theme_keys.index(self.theme_manager.current_theme))
        self.theme_row.connect("notify::selected", self._on_theme_selected)
        group_appearance.add(self.theme_row)

        # Accent Color Selector
        self.accent_row = Adw.ComboRow()
        self.accent_row.set_title("Accent Color")
        self.accent_keys = list(ACCENT_COLORS.keys())
        accent_labels = [k.capitalize() for k in self.accent_keys]
        self.accent_row.set_model(Gtk.StringList.new(accent_labels))
        if self.theme_manager.current_accent in self.accent_keys:
            self.accent_row.set_selected(self.accent_keys.index(self.theme_manager.current_accent))
        self.accent_row.connect("notify::selected", self._on_accent_selected)
        group_appearance.add(self.accent_row)

        # Animations
        self.anim_row = Adw.ComboRow()
        self.anim_row.set_title("Animations")
        self.anim_keys = ["off", "minimal", "full"]
        anim_labels = ["Off (Instant / Low RAM)", "Minimal (120ms)", "Full (180ms)"]
        self.anim_row.set_model(Gtk.StringList.new(anim_labels))
        if self.theme_manager.animation_mode in self.anim_keys:
            self.anim_row.set_selected(self.anim_keys.index(self.theme_manager.animation_mode))
        self.anim_row.connect("notify::selected", self._on_anim_selected)
        group_appearance.add(self.anim_row)

        # =============================================================
        # Section 2: Desktop Integration
        # =============================================================
        group_desktop = Adw.PreferencesGroup()
        group_desktop.set_title("Desktop Integration")
        detected_env = detect_environment_name()
        group_desktop.set_description(f"Detected Platform: {detected_env}")
        self.add(group_desktop)

        self.available_setters = get_available_setters()
        if not self.available_setters:
            from wallpaper_engine.setters.unavailable import UnavailableWallpaperSetter
            self.available_setters = [UnavailableWallpaperSetter()]
        backend_names = [s.name for s in self.available_setters]

        self.setter_row = Adw.ComboRow()
        self.setter_row.set_title("Wallpaper Setter Backend")
        self.setter_row.set_model(Gtk.StringList.new(backend_names))
        # Select current setter if present
        cur_name = self.wallpaper_setter.name
        for idx, s in enumerate(self.available_setters):
            if s.name == cur_name:
                self.setter_row.set_selected(idx)
                break
        self.setter_row.connect("notify::selected", self._on_setter_selected)
        group_desktop.add(self.setter_row)

        # Monitor Behavior
        self.monitor_row = Adw.ComboRow()
        self.monitor_row.set_title("Monitor Targeting")
        self.monitor_row.set_model(Gtk.StringList.new(["All Monitors", "Primary Monitor"]))
        group_desktop.add(self.monitor_row)

        # Test Current Setter
        test_row = Adw.ActionRow()
        test_row.set_title("Test Wallpaper Backend")
        test_row.set_subtitle("Verify that the backend can communicate with your compositor")
        test_btn = Gtk.Button(label="Test")
        test_btn.set_valign(Gtk.Align.CENTER)
        test_btn.connect("clicked", self._on_test_backend_clicked)
        test_row.add_suffix(test_btn)
        group_desktop.add(test_row)

        # =============================================================
        # Section 3: Performance & Low-RAM Controls
        # =============================================================
        group_perf = Adw.PreferencesGroup()
        group_perf.set_title("Performance and Memory")
        group_perf.set_description("Optimized for ~4 GB RAM hardware.")
        self.add(group_perf)

        self.thumb_size_row = Adw.ComboRow()
        self.thumb_size_row.set_title("Grid Thumbnail Size")
        self.thumb_size_row.set_model(Gtk.StringList.new(["240px (Low RAM)", "320px (Default / Balanced)", "480px (High DPI)"]))
        self.thumb_size_row.set_selected(1)
        group_perf.add(self.thumb_size_row)

        self.preview_quality_row = Adw.ComboRow()
        self.preview_quality_row.set_title("Preview Dialog Resolution")
        self.preview_quality_row.set_model(Gtk.StringList.new(["720p (Fastest)", "1280px (Crisp / Default)", "1920px (1080p)"]))
        self.preview_quality_row.set_selected(1)
        group_perf.add(self.preview_quality_row)

        # Disk Storage / Cache Cleanup
        self.cache_size_row = Adw.ActionRow()
        self.cache_size_row.set_title("Disk Cache Usage")
        self._update_cache_display()

        clear_btn = Gtk.Button(label="Clear Cache")
        clear_btn.set_valign(Gtk.Align.CENTER)
        clear_btn.add_css_class("destructive-action")
        clear_btn.connect("clicked", self._on_clear_cache_clicked)
        self.cache_size_row.add_suffix(clear_btn)
        group_perf.add(self.cache_size_row)

        # =============================================================
        # Section 4: Automatic Rotation
        # =============================================================
        group_rotation = Adw.PreferencesGroup()
        group_rotation.set_title("Wallpaper Rotation")
        group_rotation.set_description("Periodically rotate wallpapers in the background.")
        self.add(group_rotation)

        self.rot_switch = Adw.SwitchRow()
        self.rot_switch.set_title("Enable Automatic Rotation")
        self.rot_switch.set_active(self.rotation_service.is_running())
        self.rot_switch.connect("notify::active", self._on_rotation_toggled)
        group_rotation.add(self.rot_switch)

        self.interval_row = Adw.ComboRow()
        self.interval_row.set_title("Rotation Interval")
        intervals = ["5 minutes", "15 minutes", "30 minutes", "1 hour", "6 hours", "Daily"]
        self.interval_keys = ["5m", "15m", "30m", "1h", "6h", "daily"]
        self.interval_row.set_model(Gtk.StringList.new(intervals))
        self.interval_row.set_selected(2)
        self.interval_row.connect("notify::selected", self._on_interval_selected)
        group_rotation.add(self.interval_row)

        # =============================================================
        # Section 5: Keyboard Shortcuts Reference
        # =============================================================
        group_keys = Adw.PreferencesGroup()
        group_keys.set_title("Keyboard Shortcuts")
        group_keys.set_description("Fast navigation keybindings.")
        self.add(group_keys)

        key_search = Adw.ActionRow()
        key_search.set_title("Focus Search")
        lbl_s = Gtk.Label(label="Ctrl + /")
        lbl_s.add_css_class("meta-mono")
        key_search.add_suffix(lbl_s)
        group_keys.add(key_search)

        key_esc = Adw.ActionRow()
        key_esc.set_title("Return to Dashboard / Close Dialog")
        lbl_e = Gtk.Label(label="ESC")
        lbl_e.add_css_class("meta-mono")
        key_esc.add_suffix(lbl_e)
        group_keys.add(key_esc)

    def _on_theme_selected(self, combo, param):
        idx = combo.get_selected()
        if 0 <= idx < len(self.theme_keys):
            self.theme_manager.set_theme(self.theme_keys[idx])
            if self.on_toast:
                self.on_toast(f"Applied theme: {self.theme_keys[idx].capitalize()}")

    def _on_accent_selected(self, combo, param):
        idx = combo.get_selected()
        if 0 <= idx < len(self.accent_keys):
            self.theme_manager.set_accent(self.accent_keys[idx])
            if self.on_toast:
                self.on_toast(f"Accent set to: {self.accent_keys[idx].capitalize()}")

    def _on_anim_selected(self, combo, param):
        idx = combo.get_selected()
        if 0 <= idx < len(self.anim_keys):
            self.theme_manager.set_animation_mode(self.anim_keys[idx])

    def _on_setter_selected(self, combo, param):
        idx = combo.get_selected()
        if 0 <= idx < len(self.available_setters):
            new_setter = self.available_setters[idx]
            self.wallpaper_setter = new_setter
            if self.on_setter_change:
                self.on_setter_change(new_setter)
            if self.on_toast:
                self.on_toast(f"Switched backend to: {new_setter.name}")

    def _on_test_backend_clicked(self, btn):
        if self.wallpaper_setter.is_available():
            if self.on_toast:
                self.on_toast(f"✓ {self.wallpaper_setter.name} is available and ready.")
        else:
            if self.on_toast:
                self.on_toast(f"✕ {self.wallpaper_setter.name} is not available on this session.")

    def _on_rotation_toggled(self, switch, param):
        active = switch.get_active()
        if active:
            idx = self.interval_row.get_selected()
            key = self.interval_keys[idx] if idx < len(self.interval_keys) else "30m"
            self.rotation_service.start(interval_key=key)
            if self.on_toast:
                self.on_toast(f"Rotation enabled ({key}).")
        else:
            self.rotation_service.stop()
            if self.on_toast:
                self.on_toast("Rotation disabled.")

    def _on_interval_selected(self, combo, param):
        if self.rot_switch.get_active():
            idx = combo.get_selected()
            if idx < len(self.interval_keys):
                key = self.interval_keys[idx]
                self.rotation_service.set_interval(key)
                if self.on_toast:
                    self.on_toast(f"Rotation interval updated to {key}.")

    def _update_cache_display(self):
        try:
            stats = self.cache_manager.get_cache_stats()
            total_mb = stats.get("total_bytes", 0) / (1024 * 1024)
            count = stats.get("total_files", 0)
            self.cache_size_row.set_subtitle(f"{total_mb:.1f} MB in cache ({count} cached files)")
        except Exception:
            self.cache_size_row.set_subtitle(f"Cache directory: {self.cache_manager.cache_dir}")

    def _on_clear_cache_clicked(self, btn):
        self.cache_manager.clear_cache(clear_wallpapers=False, clear_previews=True, clear_thumbnails=True)
        self._update_cache_display()
        if self.on_toast:
            self.on_toast("Cleared temporary preview and thumbnail cache.")
