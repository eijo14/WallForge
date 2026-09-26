"""Main desktop window using GTK4 and Libadwaita with Modern Pixel layout and navigation."""

import concurrent.futures
import json
import logging
from pathlib import Path
from typing import Dict, List, Optional, Set

import gi
gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Adw, Gdk, GLib, Gtk

from wallpaper_engine.core.cache_manager import CacheManager
from wallpaper_engine.core.models import SearchFilter, Wallpaper
from wallpaper_engine.core.rotation_service import RotationService
from wallpaper_engine.core.search_service import SearchAggregator
from wallpaper_engine.core.source_manager import SourceManager
from wallpaper_engine.core.theme_manager import ThemeManager
from wallpaper_engine.setters.base import WallpaperSetter
from wallpaper_engine.setters.detector import detect_environment_name
from wallpaper_engine.ui.preview_dialog import WallpaperPreviewDialog
from wallpaper_engine.ui.settings_view import SettingsView
from wallpaper_engine.ui.sources_view import SourcesView
from wallpaper_engine.ui.wallpaper_card import WallpaperCard

logger = logging.getLogger(__name__)


class MainWindow(Adw.ApplicationWindow):
    """Primary application window for Personal Wallpaper Engine (UI/UX 2.0)."""

    def __init__(
        self,
        app: Adw.Application,
        source_manager: SourceManager,
        search_aggregator: SearchAggregator,
        cache_manager: CacheManager,
        rotation_service: RotationService,
        wallpaper_setter: WallpaperSetter,
        theme_manager: Optional[ThemeManager] = None,
    ) -> None:
        super().__init__(application=app)
        self.set_title("WallForge")
        self.set_default_size(1100, 720)
        self.add_css_class("main-window")
        print("[DISCOVER DEBUG] MainWindow created", flush=True)

        self.source_manager = source_manager
        self.search_aggregator = search_aggregator
        self.cache_manager = cache_manager
        self.rotation_service = rotation_service
        self.wallpaper_setter = wallpaper_setter
        self.theme_manager = theme_manager or ThemeManager()
        self.add_css_class(f"theme-{self.theme_manager.get_current_theme()}")
        self.theme_manager.register_callback(self._on_theme_updated)

        paths = getattr(self.cache_manager, "paths", None)
        self.favorites_file = paths.favorites_file if paths else (self.cache_manager.data_dir / "favorites.json")
        self._favorites: Dict[str, dict] = self._load_favorites()

        self._executor = concurrent.futures.ThreadPoolExecutor(max_workers=4)
        self._search_debounce_id: Optional[int] = None
        self._active_filter = SearchFilter()

        # Discover filtering & pagination state (Separated Initial Load vs Load More)
        self._selected_source_id: Optional[str] = None
        self._selected_res_filter: str = "all"
        self._selected_sort: str = "featured"
        self.discover_page = 1
        self.discover_initial_loading = False
        self.discover_loading_more = False
        self.discover_has_more = True
        self.discover_loaded_ids: Set[str] = set()
        self._discover_generation: int = 0
        self.discover_first_batch_received = False

        # Search progressive state
        self._search_generation: int = 0
        self._search_loaded_ids: Set[str] = set()
        self._search_first_result_received: bool = False

        # Preview dialog tracking
        self.current_preview_dialog: Optional[WallpaperPreviewDialog] = None

        # Root Toast Overlay
        self.toast_overlay = Adw.ToastOverlay()

        # Toolbar View
        toolbar_view = Adw.ToolbarView()
        self.header_bar = Adw.HeaderBar()
        self.header_bar.add_css_class("pixel-header")
        toolbar_view.add_top_bar(self.header_bar)

        # HeaderBar: Brand Widget (Retro-Tech pixel branding)
        brand_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        brand_box.set_margin_start(4)
        brand_box.set_margin_end(8)
        brand_icon = Gtk.Label(label="◈")
        brand_icon.add_css_class("pixel-brand-accent")
        brand_text = Gtk.Label(label="WALLFORGE")
        brand_text.add_css_class("pixel-brand")
        brand_box.append(brand_icon)
        brand_box.append(brand_text)
        self.header_bar.pack_start(brand_box)

        # HeaderBar: Search Entry
        self.search_entry = Gtk.SearchEntry()
        self.search_entry.set_placeholder_text("Search wallpapers... [Ctrl + /]")
        self.search_entry.set_size_request(340, -1)
        self.search_entry.connect("changed", self._on_search_text_changed)
        self.search_entry.connect("notify::has-focus", self._on_search_focus)
        self.connect("notify::focus-widget", self._on_window_focus_widget_changed)

        # Capture Escape on SearchEntry before Gtk.SearchEntry swallows it
        search_key_ctrl = Gtk.EventControllerKey.new()
        search_key_ctrl.set_propagation_phase(Gtk.PropagationPhase.CAPTURE)
        search_key_ctrl.connect("key-pressed", self._on_search_entry_key_pressed)
        self.search_entry.add_controller(search_key_ctrl)

        self.header_bar.set_title_widget(self.search_entry)

        # HeaderBar: Refresh button
        refresh_btn = Gtk.Button()
        refresh_btn.set_icon_name("view-refresh-symbolic")
        refresh_btn.set_tooltip_text("Refresh Current View")
        refresh_btn.connect("clicked", self._on_quick_refresh_clicked)
        self.header_bar.pack_end(refresh_btn)

        # HeaderBar: Random Wallpaper Button
        random_btn = Gtk.Button()
        random_btn.set_icon_name("media-playlist-shuffle-symbolic")
        random_btn.set_tooltip_text("Apply a Random Wallpaper")
        random_btn.connect("clicked", self._on_random_wallpaper_clicked)
        self.header_bar.pack_end(random_btn)

        # Body Layout: Left Sidebar + ViewStack
        body_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=0)

        # Sidebar navigation
        self.sidebar = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
        self.sidebar.add_css_class("pixel-sidebar")
        self.sidebar.set_size_request(200, -1)
        self.sidebar.set_hexpand(False)

        sidebar_title_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL)
        sidebar_title_box.set_margin_start(14)
        sidebar_title_box.set_margin_top(12)
        sidebar_title_box.set_margin_bottom(6)
        sidebar_lbl = Gtk.Label(label="NAVIGATION")
        sidebar_lbl.add_css_class("meta-mono")
        sidebar_title_box.append(sidebar_lbl)
        self.sidebar.append(sidebar_title_box)

        # Navigation items
        self._nav_buttons: Dict[str, Gtk.Button] = {}
        nav_items = [
            ("discover", "compass-symbolic", "Discover"),
            ("search", "system-search-symbolic", "Search"),
            ("favorites", "starred-symbolic", "Favorites"),
            ("downloaded", "folder-download-symbolic", "Downloaded"),
            ("sources", "network-server-symbolic", "Sources"),
            ("settings", "emblem-system-symbolic", "Settings"),
        ]

        for tab_id, icon_name, label_text in nav_items:
            btn = Gtk.Button()
            btn.add_css_class("pixel-nav-btn")
            btn_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
            icon_img = Gtk.Image.new_from_icon_name(icon_name)
            lbl = Gtk.Label(label=label_text)
            lbl.set_halign(Gtk.Align.START)
            btn_box.append(icon_img)
            btn_box.append(lbl)
            btn.set_child(btn_box)
            btn.connect("clicked", self._make_nav_callback(tab_id))
            self._nav_buttons[tab_id] = btn
            self.sidebar.append(btn)

        # Sidebar bottom system status
        spacer = Gtk.Box()
        spacer.set_vexpand(True)
        self.sidebar.append(spacer)

        bottom_info = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2)
        bottom_info.set_margin_start(14)
        bottom_info.set_margin_end(14)
        bottom_info.set_margin_bottom(12)

        de_name = detect_environment_name()
        de_lbl = Gtk.Label(label=f"DE: {de_name.upper()}")
        de_lbl.add_css_class("meta-mono")
        de_lbl.set_halign(Gtk.Align.START)
        bottom_info.append(de_lbl)

        status_lbl = Gtk.Label(label="STATUS: ONLINE")
        status_lbl.add_css_class("meta-mono")
        status_lbl.set_halign(Gtk.Align.START)
        bottom_info.append(status_lbl)

        self.sidebar.append(bottom_info)
        body_box.append(self.sidebar)

        # Vertical Divider
        sep = Gtk.Separator(orientation=Gtk.Orientation.VERTICAL)
        body_box.append(sep)

        # Content ViewStack
        self.stack = Adw.ViewStack()
        self.stack.set_hexpand(True)
        self.stack.set_vexpand(True)

        # Tab 1: Discover View (with filter bar)
        discover_wrapper, self.discover_box, self.discover_grid, self.discover_spinner, self.discover_end = (
            self._create_discover_view()
        )
        vadj = self.discover_box.get_vadjustment()
        vadj.connect("value-changed", self._on_discover_scroll)
        self.stack.add_titled(discover_wrapper, "discover", "Discover").set_icon_name("compass-symbolic")

        # Tab 2: Search View (with tag suggestions)
        search_wrapper, self.search_box, self.search_grid, self.search_spinner, self.search_end = (
            self._create_search_view()
        )
        self.stack.add_titled(search_wrapper, "search", "Search").set_icon_name("system-search-symbolic")

        # Tab 3: Favorites
        self.fav_box, self.fav_grid, self.fav_spinner, self.fav_empty_lbl = self._create_grid_view(
            empty_text="No favorites saved yet. Click ★ on any wallpaper to add it here."
        )
        self.stack.add_titled(self.fav_box, "favorites", "Favorites").set_icon_name("starred-symbolic")

        # Tab 4: Downloaded / Offline
        self.down_box, self.down_grid, self.down_spinner, self.down_empty_lbl = self._create_grid_view(
            empty_text="No downloaded wallpapers yet. Click Download in the preview to save offline."
        )
        self.stack.add_titled(self.down_box, "downloaded", "Downloaded").set_icon_name("folder-download-symbolic")

        # Tab 5: Sources Management
        self.sources_view = SourcesView(
            self.source_manager,
            on_toast=self.show_toast,
            on_sources_changed=self._on_sources_changed,
        )
        self.stack.add_titled(self.sources_view, "sources", "Sources").set_icon_name("network-server-symbolic")

        # Tab 6: Settings
        self.settings_view = SettingsView(
            self.cache_manager,
            self.rotation_service,
            self.source_manager,
            self.wallpaper_setter,
            theme_manager=self.theme_manager,
            on_toast=self.show_toast,
            on_setter_change=self._on_setter_changed,
        )
        self.stack.add_titled(self.settings_view, "settings", "Settings").set_icon_name("emblem-system-symbolic")

        body_box.append(self.stack)
        toolbar_view.set_content(body_box)
        self.toast_overlay.set_child(toolbar_view)
        self.set_content(self.toast_overlay)

        # Highlight default active tab in sidebar
        self._update_nav_selection("discover")

        # Stack change listener
        self.stack.connect("notify::visible-child-name", self._on_tab_changed)

        # Global Keyboard Shortcuts
        key_ctrl = Gtk.EventControllerKey.new()
        key_ctrl.set_propagation_phase(Gtk.PropagationPhase.CAPTURE)
        key_ctrl.connect("key-pressed", self._on_window_key_pressed)
        self.add_controller(key_ctrl)

        # Initial Discover Load
        self.refresh_discover()

    def _on_theme_updated(self, theme_key: str) -> None:
        """Update window-level theme classes when theme changes."""
        for t in ["system", "dark", "light", "midnight", "pixel_green"]:
            self.remove_css_class(f"theme-{t}")
        self.add_css_class(f"theme-{theme_key}")

    def _make_nav_callback(self, tab_id: str):
        return lambda _btn: self.switch_to_tab(tab_id)

    def switch_to_tab(self, tab_name: str) -> None:
        """Switch ViewStack to the specified tab and update sidebar selection."""
        if self.stack.get_visible_child_name() != tab_name:
            self.stack.set_visible_child_name(tab_name)
        self._update_nav_selection(tab_name)

    def _update_nav_selection(self, active_tab: str) -> None:
        for tab_id, btn in self._nav_buttons.items():
            if tab_id == active_tab:
                btn.add_css_class("active")
            else:
                btn.remove_css_class("active")

    @property
    def discover_loading(self) -> bool:
        return self.discover_initial_loading or self.discover_loading_more

    @discover_loading.setter
    def discover_loading(self, value: bool) -> None:
        if not value:
            self.discover_initial_loading = False
            self.discover_loading_more = False
        else:
            self.discover_loading_more = True

    @property
    def is_preview_open(self) -> bool:
        """Check if PreviewDialog is currently open and visible."""
        if getattr(self, "current_preview_dialog", None) is not None:
            try:
                return (
                    self.current_preview_dialog.get_visible()
                    and not getattr(self.current_preview_dialog, "_is_destroyed", False)
                )
            except Exception:
                return False
        return False

    def _navigate_to_search(self):
        """Centralized navigation to Search view and focusing SearchEntry."""
        self.switch_to_tab("search")
        if not self.search_entry.has_focus():
            self.search_entry.grab_focus()
        self.search_entry.set_position(-1)

    def _navigate_to_dashboard(self):
        """Centralized navigation to Dashboard: removes SearchEntry focus and switches view."""
        self.switch_to_tab("discover")
        self.set_focus(None)
        self.discover_box.grab_focus()

    def _handle_escape(self) -> bool:
        """Centralized Escape handler following strict priority."""
        is_preview = self.is_preview_open
        current_view = self.stack.get_visible_child_name()
        fw = self.get_focus()
        delg = self.search_entry.get_delegate()
        search_focused = self.search_entry.has_focus() or (fw is not None and (fw is self.search_entry or fw is delg))

        print("[KEY DEBUG] key pressed: Escape", flush=True)
        print(f"[KEY DEBUG] current view: {current_view}", flush=True)
        print(f"[KEY DEBUG] search entry focused: {search_focused}", flush=True)
        print(f"[KEY DEBUG] preview dialog open: {is_preview}", flush=True)

        # Priority 1: If PreviewDialog is open, close it first. STOP.
        if is_preview:
            print("[KEY DEBUG] handling Escape → closing PreviewDialog", flush=True)
            try:
                self.current_preview_dialog.close()
            except Exception:
                pass
            self.current_preview_dialog = None
            return True

        # Priority 2: Else if Search is active (view is 'search' or search_entry is focused)
        if current_view == "search" or search_focused:
            print("[KEY DEBUG] handling Escape → Dashboard", flush=True)
            self._navigate_to_dashboard()
            return True

        # Priority 3: Otherwise do nothing
        return False

    def _on_search_entry_key_pressed(self, controller, keyval, keycode, state):
        if keyval == Gdk.KEY_Escape:
            return self._handle_escape()
        return False

    def _on_window_key_pressed(self, controller, keyval, keycode, state):
        is_ctrl = (state & Gdk.ModifierType.CONTROL_MASK) != 0
        if keyval == Gdk.KEY_Escape:
            return self._handle_escape()
        elif keyval == Gdk.KEY_slash and is_ctrl:
            self._navigate_to_search()
            return True
        return False

    # -------------------------------------------------------------
    # Discover View with Filter Chips / Dropdowns
    # -------------------------------------------------------------
    def _create_discover_view(self):
        wrapper = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        wrapper.set_vexpand(True)
        wrapper.set_hexpand(True)

        # Filter bar
        filter_bar = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        filter_bar.set_margin_start(16)
        filter_bar.set_margin_end(16)
        filter_bar.set_margin_top(12)
        filter_bar.set_margin_bottom(8)

        # Filter: Source Selector
        source_lbl = Gtk.Label(label="SOURCE:")
        source_lbl.add_css_class("meta-mono")
        filter_bar.append(source_lbl)

        self._source_dropdown_model = ["All Sources"]
        self._source_dropdown_ids = [None]
        for p in self.source_manager.get_enabled_providers():
            self._source_dropdown_model.append(p.provider_name)
            self._source_dropdown_ids.append(p.provider_id)

        self.source_dropdown = Gtk.DropDown.new_from_strings(self._source_dropdown_model)
        self.source_dropdown.connect("notify::selected", self._on_source_filter_changed)
        filter_bar.append(self.source_dropdown)

        # Filter: Resolution Selector
        res_lbl = Gtk.Label(label="RESOLUTION:")
        res_lbl.add_css_class("meta-mono")
        res_lbl.set_margin_start(8)
        filter_bar.append(res_lbl)

        res_options = ["All", "4K (3840×2160)", "1080p (1920×1080)", "Ultrawide"]
        self.res_dropdown = Gtk.DropDown.new_from_strings(res_options)
        self.res_dropdown.connect("notify::selected", self._on_res_filter_changed)
        filter_bar.append(self.res_dropdown)

        # Filter: Sort Selector
        sort_lbl = Gtk.Label(label="SORT:")
        sort_lbl.add_css_class("meta-mono")
        sort_lbl.set_margin_start(8)
        filter_bar.append(sort_lbl)

        sort_options = ["Featured", "Newest", "Top Resolution"]
        self.sort_dropdown = Gtk.DropDown.new_from_strings(sort_options)
        self.sort_dropdown.connect("notify::selected", self._on_sort_filter_changed)
        filter_bar.append(self.sort_dropdown)

        spacer = Gtk.Box()
        spacer.set_hexpand(True)
        filter_bar.append(spacer)

        refresh_chip = Gtk.Button(label="⟳ Refresh")
        refresh_chip.add_css_class("filter-chip")
        refresh_chip.connect("clicked", lambda _b: self.refresh_discover())
        filter_bar.append(refresh_chip)

        wrapper.append(filter_bar)
        wrapper.append(Gtk.Separator(orientation=Gtk.Orientation.HORIZONTAL))

        scrolled, flowbox, spinner, end_label = self._create_grid_view()
        wrapper.append(scrolled)

        print("[DISCOVER DEBUG] Discover view created", flush=True)
        return wrapper, scrolled, flowbox, spinner, end_label

    def _on_source_filter_changed(self, dropdown, param):
        idx = dropdown.get_selected()
        if 0 <= idx < len(self._source_dropdown_ids):
            self._selected_source_id = self._source_dropdown_ids[idx]
            self.refresh_discover()

    def _on_res_filter_changed(self, dropdown, param):
        idx = dropdown.get_selected()
        mapping = {0: "all", 1: "4k", 2: "1080p", 3: "ultrawide"}
        self._selected_res_filter = mapping.get(idx, "all")
        self.refresh_discover()

    def _on_sort_filter_changed(self, dropdown, param):
        idx = dropdown.get_selected()
        mapping = {0: "featured", 1: "newest", 2: "resolution"}
        self._selected_sort = mapping.get(idx, "featured")
        self.refresh_discover()

    def _update_source_filter_dropdown(self):
        self._source_dropdown_model = ["All Sources"]
        self._source_dropdown_ids = [None]
        for p in self.source_manager.get_enabled_providers():
            self._source_dropdown_model.append(p.provider_name)
            self._source_dropdown_ids.append(p.provider_id)
        # Note: Gtk.DropDown model update via new_from_strings
        new_model = Gtk.StringList.new(self._source_dropdown_model)
        self.source_dropdown.set_model(new_model)

    # -------------------------------------------------------------
    # Search View with Tag Suggestion Chips
    # -------------------------------------------------------------
    def _create_search_view(self):
        wrapper = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        wrapper.set_vexpand(True)
        wrapper.set_hexpand(True)

        # Suggestions chip bar
        tag_bar = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        tag_bar.set_margin_start(16)
        tag_bar.set_margin_end(16)
        tag_bar.set_margin_top(12)
        tag_bar.set_margin_bottom(8)

        tag_title = Gtk.Label(label="SUGGESTIONS:")
        tag_title.add_css_class("meta-mono")
        tag_bar.append(tag_title)

        sample_tags = ["Space", "Anime", "Cyberpunk", "Minimal", "Nature", "Pixel Art", "Linux", "City"]
        for tag in sample_tags:
            chip = Gtk.Button(label=tag)
            chip.add_css_class("filter-chip")
            chip.connect("clicked", self._make_tag_chip_callback(tag))
            tag_bar.append(chip)

        wrapper.append(tag_bar)
        wrapper.append(Gtk.Separator(orientation=Gtk.Orientation.HORIZONTAL))

        scrolled, flowbox, spinner, end_label = self._create_grid_view()
        wrapper.append(scrolled)

        return wrapper, scrolled, flowbox, spinner, end_label

    def _make_tag_chip_callback(self, tag: str):
        def _callback(_btn):
            self.search_entry.set_text(tag)
            self._trigger_search(tag)
        return _callback

    # -------------------------------------------------------------
    # Reusable Scrolled Grid View
    # -------------------------------------------------------------
    def _create_grid_view(self, empty_text: str = "No wallpapers found."):
        scrolled = Gtk.ScrolledWindow()
        scrolled.set_vexpand(True)
        scrolled.set_hexpand(True)

        scroll_content = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        scroll_content.set_vexpand(True)
        scroll_content.set_hexpand(True)

        flowbox = Gtk.FlowBox()
        flowbox.set_vexpand(True)
        flowbox.set_hexpand(True)
        flowbox.set_valign(Gtk.Align.START)
        flowbox.set_max_children_per_line(8)
        flowbox.set_selection_mode(Gtk.SelectionMode.NONE)
        flowbox.set_row_spacing(12)
        flowbox.set_column_spacing(12)
        flowbox.set_margin_start(16)
        flowbox.set_margin_end(16)
        flowbox.set_margin_top(16)
        flowbox.set_margin_bottom(16)

        scroll_content.append(flowbox)

        # Spinner at bottom
        spinner = Gtk.Spinner()
        spinner.set_size_request(36, 36)
        spinner.set_halign(Gtk.Align.CENTER)
        spinner.set_margin_top(24)
        spinner.set_margin_bottom(24)
        spinner.set_visible(False)
        scroll_content.append(spinner)

        # End of content / empty label
        end_label = Gtk.Label(label=empty_text)
        end_label.add_css_class("dim-label")
        end_label.set_margin_top(16)
        end_label.set_margin_bottom(32)
        end_label.set_visible(False)
        scroll_content.append(end_label)

        scrolled.set_child(scroll_content)
        return scrolled, flowbox, spinner, end_label

    def show_toast(self, message: str):
        toast = Adw.Toast.new(message)
        self.toast_overlay.add_toast(toast)

    def _on_setter_changed(self, new_setter: WallpaperSetter):
        self.wallpaper_setter = new_setter
        self.rotation_service.wallpaper_setter = new_setter

    def _on_sources_changed(self):
        self._update_source_filter_dropdown()
        self.refresh_discover()

    def _on_tab_changed(self, stack, param):
        current_tab = self.stack.get_visible_child_name()
        self._update_nav_selection(current_tab)
        if current_tab == "search":
            self._navigate_to_search()
        elif current_tab == "favorites":
            self.refresh_favorites()
        elif current_tab == "downloaded":
            self.refresh_downloaded()
        elif current_tab == "sources":
            self.sources_view.refresh()

    def _on_search_focus(self, entry, param):
        fw = self.get_focus()
        delg = self.search_entry.get_delegate()
        if entry.has_focus() or (fw is not None and (fw is entry or fw is delg)):
            self._navigate_to_search()

    def _on_window_focus_widget_changed(self, win, param):
        fw = self.get_focus()
        delg = self.search_entry.get_delegate()
        if fw is not None and (fw is self.search_entry or fw is delg):
            self._navigate_to_search()

    def _on_quick_refresh_clicked(self, _btn):
        current_tab = self.stack.get_visible_child_name()
        if current_tab == "discover":
            self.refresh_discover()
            self.show_toast("Refreshing Discover feed...")
        elif current_tab == "search":
            q = self.search_entry.get_text().strip()
            if q:
                self._trigger_search(q)
                self.show_toast(f"Refreshing search for '{q}'...")
        elif current_tab == "favorites":
            self.refresh_favorites()
            self.show_toast("Refreshed Favorites.")
        elif current_tab == "downloaded":
            self.refresh_downloaded()
            self.show_toast("Refreshed Downloaded wallpapers.")
        elif current_tab == "sources":
            self.sources_view.refresh()
            self.show_toast("Refreshed Sources.")

    # -------------------------------------------------------------
    # Discover Feed (Progressive Streaming + Infinite Scroll + Filtering)
    # -------------------------------------------------------------
    def refresh_discover(self):
        print("[DISCOVER DEBUG] initial Discover load requested", flush=True)
        self._discover_generation += 1
        generation = self._discover_generation
        self.discover_initial_loading = True
        self.discover_loading_more = False
        self.discover_has_more = True
        self.discover_page = 1
        self.discover_first_batch_received = False

        self.discover_end.set_visible(False)
        self.discover_spinner.set_visible(True)
        self.discover_spinner.start()

        self._clear_grid(self.discover_grid)
        self.discover_loaded_ids.clear()

        self._executor.submit(self._fetch_discover_progressive_task, self.discover_page, generation, False)

    def _on_discover_scroll(self, vadj):
        if self.discover_initial_loading or self.discover_loading_more or not self.discover_has_more:
            return

        dist = vadj.get_upper() - vadj.get_value() - vadj.get_page_size()
        if dist < 800:
            self.discover_loading_more = True
            self.discover_page += 1
            generation = self._discover_generation
            self.discover_spinner.set_visible(True)
            self.discover_spinner.start()
            self._executor.submit(self._fetch_discover_progressive_task, self.discover_page, generation, True)

    def _fetch_discover_progressive_task(self, page: int, generation: int, append: bool):
        target_providers = None
        if self._selected_source_id:
            p = self.source_manager.get_provider(self._selected_source_id)
            if p:
                target_providers = [p]

        def on_results(provider_id: str, new_wallpapers: List[Wallpaper]):
            if generation != self._discover_generation:
                return

            filtered = new_wallpapers
            if self._selected_res_filter == "4k":
                filtered = [w for w in filtered if w.is_4k_or_more]
            elif self._selected_res_filter == "1080p":
                filtered = [w for w in filtered if w.is_1080p_or_more]
            elif self._selected_res_filter == "ultrawide":
                filtered = [w for w in filtered if w.is_ultrawide]

            if self._selected_sort == "newest":
                filtered = self.search_aggregator.sort_results(filtered, "newest")
            elif self._selected_sort == "resolution":
                filtered = self.search_aggregator.sort_results(filtered, "resolution")

            if filtered:
                print("[DISCOVER DEBUG] scheduling GTK main thread update", flush=True)
                GLib.idle_add(self._on_discover_batch_received, filtered, generation)

        def on_complete():
            if generation != self._discover_generation:
                return
            GLib.idle_add(self._on_discover_complete, generation)

        self.search_aggregator.get_featured_progressive(
            page=page,
            providers=target_providers,
            on_results=on_results,
            on_complete=on_complete,
            is_cancelled=lambda: generation != self._discover_generation,
        )

    def _on_discover_batch_received(self, wallpapers: List[Wallpaper], generation: int):
        if generation != self._discover_generation:
            return False

        print("[DISCOVER DEBUG] GTK callback executed", flush=True)

        if not self.discover_first_batch_received:
            self.discover_first_batch_received = True
            print(f"[DISCOVER DEBUG] first Discover results received: {len(wallpapers)} wallpapers", flush=True)
            print("[DISCOVER DEBUG] hiding initial loading state", flush=True)
            self.discover_spinner.stop()
            self.discover_spinner.set_visible(False)

        for wp in wallpapers:
            if wp.id in self.discover_loaded_ids:
                continue
            self.discover_loaded_ids.add(wp.id)

            print(
                f"[DISCOVER DEBUG] result: id={wp.id} provider={wp.provider_id} "
                f"title={wp.title} image_url={wp.image_url} thumbnail_url={wp.thumbnail_url}",
                flush=True,
            )
            print(f"[DISCOVER DEBUG] adding wallpaper to Discover grid: {wp.id}", flush=True)
            print(f"[DISCOVER DEBUG] creating WallpaperCard: {wp.id}", flush=True)

            card = WallpaperCard(
                wp,
                self.cache_manager,
                on_click=self._open_preview,
                on_favorite_toggle=self.on_favorite_toggle,
                is_favorite=(wp.id in self._favorites),
                executor=self._executor,
            )
            self.discover_grid.append(card)

        return False

    def _on_discover_complete(self, generation: int):
        if generation != self._discover_generation:
            return False

        self.discover_initial_loading = False
        self.discover_loading_more = False
        self.discover_spinner.stop()
        self.discover_spinner.set_visible(False)

        if not self.discover_loaded_ids:
            self.discover_has_more = False
            self.discover_end.set_visible(True)
        else:
            self.discover_end.set_visible(False)

        print("[DISCOVER DEBUG] Discover initial load complete", flush=True)
        return False

    # -------------------------------------------------------------
    # Search (Progressive, Debounced, Stale-Generation-Safe)
    # -------------------------------------------------------------
    def _clear_grid(self, grid: Gtk.FlowBox):
        child = grid.get_first_child()
        while child:
            next_child = child.get_next_sibling()
            grid.remove(child)
            child = next_child

    def _on_search_text_changed(self, entry):
        query = entry.get_text().strip()
        if self._search_debounce_id:
            GLib.source_remove(self._search_debounce_id)
            self._search_debounce_id = None

        if not query:
            self._search_generation += 1
            self.search_spinner.stop()
            self.search_spinner.set_visible(False)
            self._clear_grid(self.search_grid)
            self._search_loaded_ids.clear()
            self._search_first_result_received = False
            return

        self._search_debounce_id = GLib.timeout_add(180, self._trigger_search, query)

    def _trigger_search(self, query: str):
        self._search_debounce_id = None
        self.switch_to_tab("search")

        self._search_generation += 1
        generation = self._search_generation
        self._search_first_result_received = False

        self.search_spinner.set_visible(True)
        self.search_spinner.start()
        self._active_filter.query = query

        self._executor.submit(self._search_coordinator_task, query, generation)
        return False

    def _search_coordinator_task(self, query: str, generation: int):
        if generation != self._search_generation:
            return

        def on_results(provider_id: str, wallpapers: List[Wallpaper]):
            if generation == self._search_generation:
                GLib.idle_add(self._on_search_batch_received, generation, provider_id, wallpapers)

        def on_complete():
            if generation == self._search_generation:
                GLib.idle_add(self._on_search_complete, generation)

        filters = SearchFilter(query=query, page=1)
        self.search_aggregator.search_progressive(
            filters,
            on_results=on_results,
            on_complete=on_complete,
            is_cancelled=lambda: generation != self._search_generation,
        )

    def _on_search_batch_received(self, generation: int, provider_id: str, wallpapers: List[Wallpaper]):
        if generation != self._search_generation:
            return False

        if not wallpapers:
            return False

        if not self._search_first_result_received:
            self._search_first_result_received = True
            self._clear_grid(self.search_grid)
            self._search_loaded_ids.clear()
            self.search_spinner.stop()
            self.search_spinner.set_visible(False)

        for wp in wallpapers:
            if wp.id in self._search_loaded_ids:
                continue
            self._search_loaded_ids.add(wp.id)
            card = WallpaperCard(
                wp,
                self.cache_manager,
                on_click=self._open_preview,
                on_favorite_toggle=self.on_favorite_toggle,
                is_favorite=(wp.id in self._favorites),
                executor=self._executor,
            )
            self.search_grid.append(card)

        return False

    def _on_search_complete(self, generation: int):
        if generation != self._search_generation:
            return False
        self.search_spinner.stop()
        self.search_spinner.set_visible(False)
        if not self._search_first_result_received:
            self._clear_grid(self.search_grid)
            self._search_loaded_ids.clear()
        return False

    # -------------------------------------------------------------
    # Favorites
    # -------------------------------------------------------------
    def _load_favorites(self) -> Dict[str, dict]:
        if not self.favorites_file.is_file():
            return {}
        try:
            with open(self.favorites_file, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return {}

    def _save_favorites(self):
        try:
            with open(self.favorites_file, "w", encoding="utf-8") as f:
                json.dump(self._favorites, f, indent=2)
        except Exception as e:
            logger.warning("Could not save favorites: %s", e)

    def on_favorite_toggle(self, wallpaper: Wallpaper, is_fav: bool):
        if is_fav:
            self._favorites[wallpaper.id] = {
                "id": wallpaper.id,
                "provider_id": wallpaper.provider_id,
                "provider_name": wallpaper.provider_name,
                "title": wallpaper.title,
                "thumbnail_url": wallpaper.thumbnail_url,
                "image_url": wallpaper.image_url,
                "source_url": wallpaper.source_url,
                "width": wallpaper.width,
                "height": wallpaper.height,
                "aspect_ratio": wallpaper.aspect_ratio,
                "license": wallpaper.license,
            }
            self.show_toast(f"Added '{wallpaper.title}' to Favorites.")
        else:
            self._favorites.pop(wallpaper.id, None)
            self.show_toast(f"Removed '{wallpaper.title}' from Favorites.")
        self._save_favorites()

    def refresh_favorites(self):
        wallpapers = []
        for d in self._favorites.values():
            wp = Wallpaper(
                id=d["id"],
                provider_id=d.get("provider_id", "local"),
                provider_name=d.get("provider_name", "Favorite"),
                title=d.get("title", "Wallpaper"),
                thumbnail_url=d.get("thumbnail_url", ""),
                image_url=d.get("image_url", ""),
                source_url=d.get("source_url", ""),
                width=d.get("width", 0),
                height=d.get("height", 0),
                aspect_ratio=d.get("aspect_ratio", "Unknown"),
                license=d.get("license", "Unknown"),
            )
            wallpapers.append(wp)
        self._populate_grid(self.fav_grid, self.fav_spinner, wallpapers)
        if hasattr(self, "fav_empty_lbl"):
            self.fav_empty_lbl.set_visible(len(wallpapers) == 0)

    # -------------------------------------------------------------
    # Downloaded / Offline Wallpapers
    # -------------------------------------------------------------
    def refresh_downloaded(self):
        local_prov = self.source_manager.get_provider("local")
        if local_prov:
            wallpapers = local_prov.get_featured(page=1)
            self._populate_grid(self.down_grid, self.down_spinner, wallpapers)
            if hasattr(self, "down_empty_lbl"):
                self.down_empty_lbl.set_visible(len(wallpapers) == 0)

    # -------------------------------------------------------------
    # Grid Population
    # -------------------------------------------------------------
    def _populate_grid(
        self,
        grid: Gtk.FlowBox,
        spinner: Gtk.Spinner,
        wallpapers: List[Wallpaper],
        append: bool = False,
        loaded_set: Optional[Set[str]] = None,
    ):
        spinner.stop()
        spinner.set_visible(False)

        if not append:
            self._clear_grid(grid)
            if loaded_set is not None:
                loaded_set.clear()

        for wp in wallpapers:
            if loaded_set is not None:
                if wp.id in loaded_set:
                    continue
                loaded_set.add(wp.id)

            card = WallpaperCard(
                wp,
                self.cache_manager,
                on_click=self._open_preview,
                on_favorite_toggle=self.on_favorite_toggle,
                is_favorite=(wp.id in self._favorites),
                executor=self._executor,
            )
            grid.append(card)
        return False

    def _open_preview(self, wallpaper: Wallpaper):
        self.current_preview_dialog = WallpaperPreviewDialog(
            self,
            wallpaper,
            self.cache_manager,
            self.wallpaper_setter,
            on_favorite_toggle=self.on_favorite_toggle,
            is_favorite=(wallpaper.id in self._favorites),
            on_status_msg=self.show_toast,
        )

        def on_dialog_destroyed(dialog):
            if getattr(self, "current_preview_dialog", None) == dialog:
                self.current_preview_dialog = None

        self.current_preview_dialog.connect("destroy", on_dialog_destroyed)
        self.current_preview_dialog.present()

    def _on_random_wallpaper_clicked(self, _btn):
        if not self.wallpaper_setter.is_available():
            self.show_toast("Wallpaper setting is unavailable on this system.")
            return
        self.show_toast("Applying a random wallpaper...")
        self._executor.submit(self._apply_random_task)

    def _apply_random_task(self):
        success = self.rotation_service.rotate_now()
        msg = "Random wallpaper applied!" if success else "Failed to apply random wallpaper."
        GLib.idle_add(self.show_toast, msg)
