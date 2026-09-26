"""First-class Sources Management view."""

from typing import Callable, Optional

import gi
gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Adw, Gtk

from wallpaper_engine.core.models import SourceStatus
from wallpaper_engine.core.source_manager import SourceManager
from wallpaper_engine.ui.add_source_dialog import AddSourceDialog


class SourcesView(Gtk.Box):
    """First-class Sources Management interface for enabled, available, and custom sources."""

    def __init__(
        self,
        source_manager: SourceManager,
        on_toast: Optional[Callable[[str], None]] = None,
        on_sources_changed: Optional[Callable[[], None]] = None,
    ) -> None:
        super().__init__(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        self.source_manager = source_manager
        self.on_toast = on_toast
        self.on_sources_changed = on_sources_changed

        self.scrolled = Gtk.ScrolledWindow()
        self.scrolled.set_vexpand(True)
        self.scrolled.set_hexpand(True)

        self.content_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=16)
        self.content_box.set_margin_start(28)
        self.content_box.set_margin_end(28)
        self.content_box.set_margin_top(20)
        self.content_box.set_margin_bottom(32)

        # Header Title & Add Button
        top_bar = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL)
        
        title_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
        title_lbl = Gtk.Label(label="WALLPAPER SOURCES")
        title_lbl.add_css_class("pixel-brand")
        title_lbl.set_halign(Gtk.Align.START)
        title_box.append(title_lbl)

        sub_lbl = Gtk.Label(label="Manage wallpaper providers, authentication tokens, and custom feeds.")
        sub_lbl.add_css_class("meta-mono")
        sub_lbl.set_halign(Gtk.Align.START)
        title_box.append(sub_lbl)
        top_bar.append(title_box)

        spacer = Gtk.Box()
        spacer.set_hexpand(True)
        top_bar.append(spacer)

        add_btn = Gtk.Button(label="+ Add Custom Source")
        add_btn.add_css_class("suggested-action")
        add_btn.connect("clicked", self._on_add_source_clicked)
        top_bar.append(add_btn)

        self.content_box.append(top_bar)

        # Sources List Container
        self.sources_list_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)
        self.content_box.append(self.sources_list_box)

        self.scrolled.set_child(self.content_box)
        self.append(self.scrolled)

        self.refresh()

    def refresh(self) -> None:
        """Re-render the list of all providers with status indicators and controls."""
        child = self.sources_list_box.get_first_child()
        while child:
            next_child = child.get_next_sibling()
            self.sources_list_box.remove(child)
            child = next_child

        providers = self.source_manager.get_all_providers()
        group = Adw.PreferencesGroup()
        group.set_title("Registered Providers")

        for provider in providers:
            pid = provider.provider_id
            row = Adw.ActionRow()
            row.set_title(provider.provider_name)

            # Subtitle with status indicator
            status_text = provider.status.value
            status_dot = "●"
            if provider.status == SourceStatus.ONLINE:
                status_class = "online"
            elif provider.status == SourceStatus.DEGRADED:
                status_class = "degraded"
            elif provider.status == SourceStatus.NOT_CONFIGURED:
                status_class = "not-configured"
            else:
                status_class = "offline"

            desc = f"{status_dot} {status_text} • {provider.homepage_url}"
            row.set_subtitle(desc)

            # Enable/Disable Switch
            switch = Gtk.Switch()
            switch.set_active(self.source_manager.is_enabled(pid))
            switch.set_valign(Gtk.Align.CENTER)
            switch.connect("state-set", self._create_toggle_handler(pid))
            row.add_suffix(switch)

            # Configure button if settings exist
            if provider.get_settings_schema():
                cfg_btn = Gtk.Button()
                cfg_btn.set_icon_name("emblem-system-symbolic")
                cfg_btn.set_tooltip_text(f"Configure {provider.provider_name}")
                cfg_btn.set_valign(Gtk.Align.CENTER)
                cfg_btn.connect("clicked", self._create_config_handler(provider))
                row.add_suffix(cfg_btn)

            # Delete button if custom source
            if pid.startswith("custom_"):
                del_btn = Gtk.Button()
                del_btn.set_icon_name("user-trash-symbolic")
                del_btn.set_tooltip_text("Delete Custom Source")
                del_btn.add_css_class("destructive-action")
                del_btn.set_valign(Gtk.Align.CENTER)
                del_btn.connect("clicked", self._create_delete_handler(pid))
                row.add_suffix(del_btn)

            group.add(row)

        self.sources_list_box.append(group)

    def _create_toggle_handler(self, pid: str):
        def on_toggle(switch, state):
            self.source_manager.set_enabled(pid, state)
            status_str = "enabled" if state else "disabled"
            if self.on_toast:
                self.on_toast(f"Source '{pid}' {status_str}.")
            if self.on_sources_changed:
                self.on_sources_changed()
            return False
        return on_toggle

    def _create_delete_handler(self, pid: str):
        def on_delete(btn):
            self.source_manager.remove_custom_source(pid)
            if self.on_toast:
                self.on_toast(f"Removed custom source '{pid}'.")
            self.refresh()
            if self.on_sources_changed:
                self.on_sources_changed()
        return on_delete

    def _create_config_handler(self, provider):
        def on_configure(btn):
            # Show configuration dialog
            dialog = Adw.Window()
            root = self.get_root()
            if isinstance(root, Gtk.Window):
                dialog.set_transient_for(root)
            dialog.set_modal(True)
            dialog.set_title(f"Configure {provider.provider_name}")
            dialog.set_default_size(440, 360)

            toolbar = Adw.ToolbarView()
            toolbar.add_top_bar(Adw.HeaderBar())

            pref_group = Adw.PreferencesGroup()
            pref_group.set_title(provider.provider_name)
            pref_group.set_description(f"Settings and credentials for {provider.provider_name}")

            entries = {}
            current_cfg = self.source_manager.get_provider_config(provider.provider_id)
            for f in provider.get_settings_schema():
                val = str(current_cfg.get(f.key, f.default))
                if f.field_type == "password":
                    row = Adw.PasswordEntryRow()
                    row.set_title(f.label)
                    row.set_text(val)
                else:
                    row = Adw.EntryRow()
                    row.set_title(f.label)
                    row.set_text(val)
                entries[f.key] = row
                pref_group.add(row)

            box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=16)
            box.set_margin_start(20)
            box.set_margin_end(20)
            box.set_margin_top(16)
            box.set_margin_bottom(20)
            box.append(pref_group)

            save_btn = Gtk.Button(label="Save Configuration")
            save_btn.add_css_class("suggested-action")
            def on_save(b):
                new_cfg = {k: row.get_text().strip() for k, row in entries.items()}
                self.source_manager.save_provider_config(provider.provider_id, new_cfg)
                if self.on_toast:
                    self.on_toast(f"Saved configuration for {provider.provider_name}.")
                dialog.close()
                self.refresh()

            save_btn.connect("clicked", on_save)
            box.append(save_btn)

            toolbar.set_content(box)
            dialog.set_content(toolbar)
            dialog.present()
        return on_configure

    def _on_add_source_clicked(self, btn):
        root = self.get_root()
        win = root if isinstance(root, Gtk.Window) else None
        def on_added(cfg):
            p = self.source_manager.add_custom_source(cfg)
            if self.on_toast:
                self.on_toast(f"Added custom source: {p.provider_name}")
            self.refresh()
            if self.on_sources_changed:
                self.on_sources_changed()

        dlg = AddSourceDialog(win, on_source_added=on_added)
        dlg.present()

    def get_title(self) -> str:
        return "Wallpaper Sources"
