"""Theme and design token manager for Modern Pixel / Retro-Future aesthetic."""

import json
import os
from pathlib import Path
from typing import Any, Dict, Optional

import gi
gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Adw, Gdk, Gtk


THEMES = {
    "system": {
        "name": "System",
        "bg": "@window_bg_color",
        "surface": "@view_bg_color",
        "surface_elevated": "@card_bg_color",
        "surface_hover": "@card_shade_color",
        "border": "alpha(@card_fg_color, 0.15)",
        "border_highlight": "@accent_color",
        "text_primary": "@window_fg_color",
        "text_secondary": "alpha(@window_fg_color, 0.65)",
        "accent": "#3584e4",
        "accent_hover": "#1d72d6",
        "font_mono": "'JetBrains Mono', 'Fira Code', 'DejaVu Sans Mono', monospace",
    },
    "dark": {
        "name": "Dark",
        "bg": "#121214",
        "surface": "#18181c",
        "surface_elevated": "#202026",
        "surface_hover": "#282830",
        "border": "#2f2f38",
        "border_highlight": "#3b82f6",
        "text_primary": "#f1f3f7",
        "text_secondary": "#949aa7",
        "accent": "#3b82f6",
        "accent_hover": "#2563eb",
        "font_mono": "'JetBrains Mono', 'Fira Code', 'DejaVu Sans Mono', monospace",
    },
    "light": {
        "name": "Light",
        "bg": "#f4f5f8",
        "surface": "#ffffff",
        "surface_elevated": "#eaedf2",
        "surface_hover": "#dee2e9",
        "border": "#d2d7e0",
        "border_highlight": "#2563eb",
        "text_primary": "#181b20",
        "text_secondary": "#586274",
        "accent": "#2563eb",
        "accent_hover": "#1d4ed8",
        "font_mono": "'JetBrains Mono', 'Fira Code', 'DejaVu Sans Mono', monospace",
    },
    "midnight": {
        "name": "Midnight",
        "bg": "#090d16",
        "surface": "#0f1624",
        "surface_elevated": "#172033",
        "surface_hover": "#1f2b44",
        "border": "#22314e",
        "border_highlight": "#6366f1",
        "text_primary": "#e2e8f5",
        "text_secondary": "#8292b0",
        "accent": "#6366f1",
        "accent_hover": "#4f46e5",
        "font_mono": "'JetBrains Mono', 'Fira Code', 'DejaVu Sans Mono', monospace",
    },
    "pixel_green": {
        "name": "Pixel Green",
        "bg": "#060e08",
        "surface": "#0c180f",
        "surface_elevated": "#122417",
        "surface_hover": "#1a3221",
        "border": "#1c3d24",
        "border_highlight": "#22c55e",
        "text_primary": "#4ade80",
        "text_secondary": "#22c55e",
        "accent": "#22c55e",
        "accent_hover": "#16a34a",
        "font_mono": "'JetBrains Mono', 'Fira Code', 'DejaVu Sans Mono', monospace",
    },
}

ACCENT_COLORS = {
    "default": None,
    "blue": "#3b82f6",
    "purple": "#a855f7",
    "green": "#10b981",
    "orange": "#f97316",
    "red": "#ef4444",
    "amber": "#f59e0b",
    "magenta": "#ec4899",
    "cyan": "#06b6d4",
}


class ThemeManager:
    """Manages application themes, CSS generation, and dynamic live updates."""

    def __init__(self, config_dir: Optional[Path] = None) -> None:
        from wallpaper_engine.core.paths import PathManager
        self.paths = PathManager(override_config_dir=config_dir)
        self.config_dir = self.paths.config_dir
        self.theme_config_file = self.paths.theme_file
        
        self.current_theme = "dark"
        self.current_accent = "default"
        self.animation_mode = "minimal"  # 'off', 'minimal', 'full'
        self.ui_density = "compact"      # 'compact', 'comfortable'
        
        self._css_provider: Optional[Gtk.CssProvider] = None
        self._callbacks: list = []
        self.load_config()

    def register_callback(self, cb) -> None:
        if cb not in self._callbacks:
            self._callbacks.append(cb)

    def unregister_callback(self, cb) -> None:
        if cb in self._callbacks:
            self._callbacks.remove(cb)

    def get_current_theme(self) -> str:
        return self.current_theme

    def load_config(self) -> None:
        if not self.theme_config_file.is_file():
            return
        try:
            with open(self.theme_config_file, "r", encoding="utf-8") as f:
                data = json.load(f)
                self.current_theme = data.get("theme", "dark")
                self.current_accent = data.get("accent", "default")
                self.animation_mode = data.get("animations", "minimal")
                self.ui_density = data.get("density", "compact")
        except Exception:
            pass

    def save_config(self) -> None:
        try:
            self.config_dir.mkdir(parents=True, exist_ok=True)
            with open(self.theme_config_file, "w", encoding="utf-8") as f:
                json.dump({
                    "theme": self.current_theme,
                    "accent": self.current_accent,
                    "animations": self.animation_mode,
                    "density": self.ui_density,
                }, f, indent=2)
        except Exception:
            pass

    def get_transition_speed_ms(self) -> int:
        if self.animation_mode == "off":
            return 0
        elif self.animation_mode == "minimal":
            return 120
        return 180

    def generate_css(self) -> str:
        tokens = dict(THEMES.get(self.current_theme, THEMES["dark"]))
        
        # Override accent if custom accent selected
        if self.current_accent != "default" and self.current_accent in ACCENT_COLORS:
            custom_acc = ACCENT_COLORS[self.current_accent]
            if custom_acc:
                tokens["accent"] = custom_acc
                tokens["border_highlight"] = custom_acc

        speed = self.get_transition_speed_ms()
        if speed > 0:
            btn_trans = f"transition: background-color {speed}ms ease, border-color {speed}ms ease, color {speed}ms ease;"
            card_trans = f"transition: border-color {speed}ms ease, box-shadow {speed}ms ease;"
            chip_trans = f"transition: border-color {speed}ms ease, color {speed}ms ease;"
            entry_trans = f"transition: border-color {speed}ms ease;"
        else:
            btn_trans = "transition: none;"
            card_trans = "transition: none;"
            chip_trans = "transition: none;"
            entry_trans = "transition: none;"

        define_colors = ""
        if self.current_theme != "system":
            define_colors = f"""
@define-color window_bg_color {tokens['bg']};
@define-color window_fg_color {tokens['text_primary']};
@define-color view_bg_color {tokens['bg']};
@define-color view_fg_color {tokens['text_primary']};
@define-color headerbar_bg_color {tokens['surface']};
@define-color headerbar_fg_color {tokens['text_primary']};
@define-color headerbar_border_color {tokens['border']};
@define-color headerbar_backdrop_color {tokens['surface']};
@define-color card_bg_color {tokens['surface_elevated']};
@define-color card_fg_color {tokens['text_primary']};
@define-color card_border_color {tokens['border']};
@define-color card_shade_color {tokens['surface_hover']};
@define-color popover_bg_color {tokens['surface_elevated']};
@define-color popover_fg_color {tokens['text_primary']};
@define-color dialog_bg_color {tokens['bg']};
@define-color dialog_fg_color {tokens['text_primary']};
@define-color accent_color {tokens['accent']};
@define-color accent_bg_color {tokens['accent']};
@define-color accent_fg_color #ffffff;
"""

        css = f"""{define_colors}
/* ====================================================================
   WALLFORGE MODERN PIXEL DESIGN SYSTEM TOKENS
   ==================================================================== */
:root {{
    --pe-bg: {tokens['bg']};
    --pe-surface: {tokens['surface']};
    --pe-surface-elevated: {tokens['surface_elevated']};
    --pe-surface-hover: {tokens['surface_hover']};
    --pe-border: {tokens['border']};
    --pe-border-highlight: {tokens['border_highlight']};
    --pe-text-primary: {tokens['text_primary']};
    --pe-text-secondary: {tokens['text_secondary']};
    --pe-accent: {tokens['accent']};
    --pe-accent-hover: {tokens['accent_hover']};
    --pe-font-mono: {tokens['font_mono']};
}}

/* Application Window & Main Content Root */
window,
window.background,
.main-window,
toolbarview,
viewstack,
scrolledwindow,
scrolledwindow > viewport,
viewport,
preferencespage,
preferencesgroup {{
    background-color: {tokens['bg']};
    color: {tokens['text_primary']};
}}

/* Pixel Navigation Sidebar */
.pixel-sidebar {{
    background-color: {tokens['surface']};
    color: {tokens['text_primary']};
    border-right: 1px solid {tokens['border']};
}}

.pixel-nav-btn {{
    padding: 8px 14px;
    margin: 2px 8px;
    border-radius: 4px;
    border: 1px solid transparent;
    font-weight: 600;
    font-size: 13px;
    color: {tokens['text_secondary']};
    {btn_trans}
}}

.pixel-nav-btn:hover {{
    background-color: {tokens['surface_hover']};
    color: {tokens['text_primary']};
    border-color: {tokens['border']};
}}

.pixel-nav-btn.active {{
    background-color: {tokens['surface_elevated']};
    color: {tokens['accent']};
    border-color: {tokens['border_highlight']};
    font-weight: bold;
}}

/* Pixel Header Bar */
headerbar,
.pixel-header {{
    background-color: {tokens['surface']};
    color: {tokens['text_primary']};
    border-bottom: 1px solid {tokens['border']};
}}

.pixel-brand {{
    font-family: {tokens['font_mono']};
    font-weight: 800;
    letter-spacing: 0.5px;
    font-size: 13px;
    color: {tokens['text_primary']};
}}

.pixel-brand-accent {{
    color: {tokens['accent']};
    font-weight: bold;
}}

/* Wallpaper Card (Subtle Squared Retro-Tech) */
.wallpaper-card {{
    background-color: {tokens['surface_elevated']};
    color: {tokens['text_primary']};
    border-radius: 6px;
    border: 1px solid {tokens['border']};
    padding: 0px;
    {card_trans}
}}

.wallpaper-card:hover {{
    border-color: {tokens['border_highlight']};
    box-shadow: 0 4px 14px rgba(0, 0, 0, 0.35);
}}

/* Monospace / Pixel Badges */
.provider-badge {{
    background-color: rgba(10, 12, 16, 0.88);
    color: #e2e8f0;
    font-family: {tokens['font_mono']};
    font-size: 10px;
    font-weight: 700;
    padding: 2px 6px;
    border-radius: 3px;
    border: 1px solid rgba(255, 255, 255, 0.12);
    letter-spacing: 0.2px;
}}

.res-badge {{
    background-color: rgba(37, 99, 235, 0.9);
    color: #ffffff;
    font-family: {tokens['font_mono']};
    font-size: 10px;
    font-weight: 700;
    padding: 2px 5px;
    border-radius: 3px;
    letter-spacing: 0.2px;
}}

.res-badge-4k {{
    background-color: rgba(234, 88, 12, 0.92);
    color: #ffffff;
    font-family: {tokens['font_mono']};
    font-size: 10px;
    font-weight: 700;
    padding: 2px 5px;
    border-radius: 3px;
    letter-spacing: 0.2px;
}}

/* Filter Bar Chips */
.filter-chip {{
    font-family: {tokens['font_mono']};
    font-size: 11px;
    border-radius: 4px;
    padding: 4px 10px;
    border: 1px solid {tokens['border']};
    background-color: {tokens['surface']};
    color: {tokens['text_secondary']};
    {chip_trans}
}}

.filter-chip:hover {{
    border-color: {tokens['border_highlight']};
    color: {tokens['text_primary']};
}}

.filter-chip.active {{
    border-color: {tokens['border_highlight']};
    background-color: {tokens['surface_elevated']};
    color: {tokens['accent']};
    font-weight: bold;
}}

/* Search Big Input */
searchentry,
entry,
.pixel-search-entry {{
    font-size: 14px;
    border-radius: 6px;
    border: 1px solid {tokens['border']};
    background-color: {tokens['surface_elevated']};
    color: {tokens['text_primary']};
    padding: 8px 12px;
    {entry_trans}
}}

searchentry:focus-within,
entry:focus-within,
.pixel-search-entry:focus-within {{
    border-color: {tokens['border_highlight']};
}}

/* Settings and Sources Boxed Lists & Rows */
list.boxed-list,
list.content {{
    background-color: {tokens['surface']};
    border: 1px solid {tokens['border']};
    color: {tokens['text_primary']};
}}

list.boxed-list > row,
list.content > row,
row.activatable {{
    background-color: {tokens['surface_elevated']};
    color: {tokens['text_primary']};
    border-bottom: 1px solid {tokens['border']};
}}

row.activatable:hover {{
    background-color: {tokens['surface_hover']};
}}

/* ====================================================================
   POPOVERS, DROPDOWNS & MENUS (100% OPAQUE SOLID SURFACE)
   ==================================================================== */
popover {{
    background-color: transparent;
    padding: 0;
}}

popover > arrow {{
    background-color: {tokens['surface_elevated']};
    border-color: {tokens['border']};
}}

popover > contents,
popover.menu > contents,
popover.background > contents,
dropdown > popover > contents,
combobox > popover > contents,
.combo-popover > contents,
popover contents {{
    background: {tokens['surface_elevated']};
    background-color: {tokens['surface_elevated']};
    color: {tokens['text_primary']};
    border: 1px solid {tokens['border']};
    border-radius: 8px;
    box-shadow: 0 8px 24px rgba(0, 0, 0, 0.45);
    opacity: 1;
    padding: 4px;
}}

/* Interior components inside popovers must be fully opaque */
popover scrolledwindow,
popover scrolledwindow > viewport,
popover listview,
popover listview.view,
popover list,
popover .view {{
    background: {tokens['surface_elevated']};
    background-color: {tokens['surface_elevated']};
    color: {tokens['text_primary']};
    border: none;
}}

/* Rows inside popovers / dropdowns */
popover listview row,
popover list row,
popover row {{
    background-color: transparent;
    color: {tokens['text_primary']};
    padding: 8px 12px;
    margin: 1px 2px;
    border-radius: 6px;
    min-height: 32px;
}}

popover listview row:hover,
popover list row:hover,
popover row:hover,
popover listview row:focus,
popover row:focus {{
    background: {tokens['surface_hover']};
    background-color: {tokens['surface_hover']};
    color: {tokens['text_primary']};
}}

popover listview row:selected,
popover list row:selected,
popover row:selected {{
    background: {tokens['surface_hover']};
    background-color: {tokens['surface_hover']};
    color: {tokens['text_primary']};
    font-weight: 500;
}}

/* Search entry inside ComboRow popover */
popover entry.combo-searchbar,
popover entry {{
    background: {tokens['surface']};
    background-color: {tokens['surface']};
    color: {tokens['text_primary']};
    border: 1px solid {tokens['border']};
    border-radius: 6px;
    margin: 4px;
    padding: 6px 10px;
}}

popover entry:focus-within {{
    border-color: {tokens['accent']};
}}

/* Dialogs */
dialog,
window.dialog {{
    background-color: {tokens['bg']};
    color: {tokens['text_primary']};
}}

/* Buttons */
button {{
    color: {tokens['text_primary']};
}}

button:hover {{
    background-color: {tokens['surface_hover']};
}}

/* Monospace Info Metadata */
.meta-mono {{
    font-family: {tokens['font_mono']};
    font-size: 11px;
    color: {tokens['text_secondary']};
}}

.dim-label {{
    color: {tokens['text_secondary']};
}}

separator {{
    background-color: {tokens['border']};
}}

/* Scrollbars */
scrollbar trough {{
    background-color: transparent;
}}
scrollbar slider {{
    background-color: {tokens['border']};
    min-width: 6px;
    min-height: 6px;
    border-radius: 3px;
}}
scrollbar slider:hover {{
    background-color: {tokens['border_highlight']};
}}

/* Source Status Indicators */
.status-indicator {{
    font-family: {tokens['font_mono']};
    font-size: 11px;
    font-weight: bold;
}}
.status-indicator.online {{
    color: #22c55e;
}}
.status-indicator.offline {{
    color: #ef4444;
}}
.status-indicator.degraded {{
    color: #f59e0b;
}}
.status-indicator.not-configured {{
    color: #94a3b8;
}}
"""
        return css

    def apply_theme(self) -> None:
        """Apply CSS dynamically to the GDK default display and notify subscribers."""
        css_data = self.generate_css()
        display = Gdk.Display.get_default()
        if display:
            # 1. Cleanly remove previous provider to ensure no stale rules remain active
            if self._css_provider is not None:
                try:
                    Gtk.StyleContext.remove_provider_for_display(display, self._css_provider)
                except Exception:
                    pass

            # 2. Add fresh provider with high priority
            self._css_provider = Gtk.CssProvider()
            if hasattr(self._css_provider, "load_from_string"):
                self._css_provider.load_from_string(css_data)
            else:
                self._css_provider.load_from_data(css_data.encode("utf-8"))
            Gtk.StyleContext.add_provider_for_display(
                display,
                self._css_provider,
                Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION + 20,
            )

            # 3. Synchronize Adw.StyleManager color scheme
            style_mgr = Adw.StyleManager.get_default()
            if self.current_theme == "light":
                style_mgr.set_color_scheme(Adw.ColorScheme.FORCE_LIGHT)
            elif self.current_theme in ("dark", "midnight", "pixel_green"):
                style_mgr.set_color_scheme(Adw.ColorScheme.FORCE_DARK)
            else:
                style_mgr.set_color_scheme(Adw.ColorScheme.DEFAULT)

        # 4. Notify all registered windows/components
        for cb in list(self._callbacks):
            try:
                cb(self.current_theme)
            except Exception:
                pass

    def set_theme(self, theme_key: str) -> None:
        if theme_key in THEMES:
            self.current_theme = theme_key
            self.save_config()
            self.apply_theme()

    def set_accent(self, accent_key: str) -> None:
        if accent_key in ACCENT_COLORS:
            self.current_accent = accent_key
            self.save_config()
            self.apply_theme()

    def set_animation_mode(self, mode: str) -> None:
        if mode in ("off", "minimal", "full"):
            self.animation_mode = mode
            self.save_config()
            self.apply_theme()

    def set_ui_density(self, density: str) -> None:
        if density in ("compact", "comfortable"):
            self.ui_density = density
            self.save_config()
            self.apply_theme()
