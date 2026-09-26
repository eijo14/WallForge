"""Smoke and structure tests for GTK4/Libadwaita UI components."""

from pathlib import Path
import shutil
import tempfile
import unittest
from unittest.mock import MagicMock

import gi
gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Adw, Gtk

from wallpaper_engine.core.cache_manager import CacheManager
from wallpaper_engine.core.models import Wallpaper
from wallpaper_engine.core.rotation_service import RotationService
from wallpaper_engine.core.search_service import SearchAggregator
from wallpaper_engine.core.source_manager import SourceManager
from wallpaper_engine.setters.generic import GenericLinuxWallpaperSetter
from wallpaper_engine.ui.main_window import MainWindow
from wallpaper_engine.ui.settings_view import SettingsView
from wallpaper_engine.ui.sources_view import SourcesView
from wallpaper_engine.ui.wallpaper_card import WallpaperCard


class TestUIStructure(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from gi.repository import Gdk
        Gtk.init()
        if Gdk.Display.get_default() is None:
            raise unittest.SkipTest("No GDK display available in current environment")
        # Initialize Gtk/Adw app if not already active
        cls.app = Adw.Application(application_id="org.test.wallpaper_engine")

    def setUp(self):
        self.temp_dir = Path(tempfile.mkdtemp(prefix="wp_ui_test_"))
        self.cache_mgr = CacheManager(
            base_cache_dir=self.temp_dir / "cache",
            base_data_dir=self.temp_dir / "data",
        )
        self.src_mgr = SourceManager(config_dir=self.temp_dir / "config")
        self.aggregator = SearchAggregator(self.src_mgr)
        self.setter = GenericLinuxWallpaperSetter()
        self.rot_service = RotationService(
            source_manager=self.src_mgr,
            search_aggregator=self.aggregator,
            cache_manager=self.cache_mgr,
            wallpaper_setter=self.setter,
        )

    def tearDown(self):
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_sources_view_creation(self):
        view = SourcesView(self.src_mgr)
        self.assertIsNotNone(view)
        self.assertEqual(view.get_title(), "Wallpaper Sources")

    def test_settings_view_creation(self):
        view = SettingsView(
            self.cache_mgr,
            self.rot_service,
            self.src_mgr,
            self.setter,
        )
        self.assertIsNotNone(view)
        self.assertEqual(view.get_title(), "Settings")

    def test_wallpaper_card_creation(self):
        wp = Wallpaper(
            id="test-card-1",
            provider_id="test",
            provider_name="Test Prov",
            title="Card Title",
            width=3840,
            height=2160,
        )
        card = WallpaperCard(
            wp,
            self.cache_mgr,
            on_click=lambda x: None,
        )
        self.assertIsNotNone(card)
        self.assertEqual(card.wallpaper.id, "test-card-1")

    def test_wallpaper_card_thumbnail_loading(self):
        from PIL import Image
        import time
        from gi.repository import GLib

        # Create a dummy image
        img = Image.new("RGB", (320, 180), color="blue")
        dummy_url = "https://example.com/test_thumb.jpg"
        
        # Save directly to where the cache expects it
        thumb_path = self.cache_mgr.thumbs_dir / f"{self.cache_mgr.get_hash(dummy_url)}.webp"
        img.save(thumb_path, format="WEBP")

        wp = Wallpaper(
            id="test-card-2",
            provider_id="test",
            provider_name="Test Prov",
            title="Card Title 2",
            image_url=dummy_url,
            thumbnail_url=dummy_url,
        )

        card = WallpaperCard(
            wp,
            self.cache_mgr,
            on_click=lambda x: None,
        )

        # Card should detect local file and load it synchronously or quickly in idle
        self.assertIsNotNone(card.picture)
        self.assertIsNotNone(card.loading_box)
        
        # Run GTK main loop briefly to let idle callbacks (like apply_file) execute
        ctx = GLib.MainContext.default()
        while ctx.pending():
            ctx.iteration(False)

        # Texture should be loaded
        paintable = card.picture.get_paintable()
        self.assertIsNotNone(paintable, "Paintable (Texture) should not be None after loading cached thumbnail")
        self.assertEqual(paintable.get_intrinsic_width(), 320)
        self.assertEqual(paintable.get_intrinsic_height(), 180)
        
        # Loading box should be hidden
        self.assertFalse(card.loading_box.get_visible())

    def test_main_window_navigation(self):
        from gi.repository import GLib

        win = MainWindow(
            app=self.app,
            source_manager=self.src_mgr,
            search_aggregator=self.aggregator,
            cache_manager=self.cache_mgr,
            rotation_service=self.rot_service,
            wallpaper_setter=self.setter,
        )
        
        # Test search focus switches tab
        self.assertEqual(win.stack.get_visible_child_name(), "discover")
        
        # Trigger focus
        win.search_entry.grab_focus()
        ctx = GLib.MainContext.default()
        while ctx.pending():
            ctx.iteration(False)
            
        self.assertEqual(win.stack.get_visible_child_name(), "search")

    def test_main_window_infinite_scroll(self):
        win = MainWindow(
            app=self.app,
            source_manager=self.src_mgr,
            search_aggregator=self.aggregator,
            cache_manager=self.cache_mgr,
            rotation_service=self.rot_service,
            wallpaper_setter=self.setter,
        )
        
        # Manually trigger scroll
        win.discover_loading = False
        win.discover_page = 1
        win.discover_has_more = True
        
        # Mock vadj
        class MockAdj:
            def get_upper(self): return 2000
            def get_value(self): return 1500
            def get_page_size(self): return 100
            
        win._on_discover_scroll(MockAdj())
        
        # Loading should be True, page incremented to 2
        self.assertTrue(win.discover_loading)
        self.assertEqual(win.discover_page, 2)
        # Spinner visible
        self.assertTrue(win.discover_spinner.get_visible())

    def test_main_window_search_debounce_and_generation(self):
        from gi.repository import GLib

        win = MainWindow(
            app=self.app,
            source_manager=self.src_mgr,
            search_aggregator=self.aggregator,
            cache_manager=self.cache_mgr,
            rotation_service=self.rot_service,
            wallpaper_setter=self.setter,
        )

        # Initial state
        self.assertEqual(win._search_generation, 0)

        # Type 's'
        win.search_entry.set_text("s")
        self.assertIsNotNone(win._search_debounce_id)

        # Type 'sp' immediately before debounce expires
        win.search_entry.set_text("sp")
        self.assertIsNotNone(win._search_debounce_id)

        # Clear text: should immediately cancel active generation and clear grid
        win.search_entry.set_text("")
        self.assertIsNone(win._search_debounce_id)
        self.assertGreater(win._search_generation, 0)
        self.assertFalse(win.search_spinner.get_visible())

    def test_main_window_search_stale_batch_ignored(self):
        win = MainWindow(
            app=self.app,
            source_manager=self.src_mgr,
            search_aggregator=self.aggregator,
            cache_manager=self.cache_mgr,
            rotation_service=self.rot_service,
            wallpaper_setter=self.setter,
        )

        win._search_generation = 5
        wp_stale = Wallpaper(id="stale-1", provider_id="test", provider_name="Test", title="Stale WP")

        # Batch arrived from old generation 4
        result = win._on_search_batch_received(4, "test", [wp_stale])
        self.assertFalse(result)
        # Should NOT be added to loaded IDs
        self.assertNotIn("stale-1", win._search_loaded_ids)

        # Batch arrived from current generation 5
        wp_fresh = Wallpaper(id="fresh-1", provider_id="test", provider_name="Test", title="Fresh WP")
        win._on_search_batch_received(5, "test", [wp_fresh])
        self.assertIn("fresh-1", win._search_loaded_ids)

    def test_escape_key_navigation_and_priority(self):
        from gi.repository import Gdk, GLib

        win = MainWindow(
            app=self.app,
            source_manager=self.src_mgr,
            search_aggregator=self.aggregator,
            cache_manager=self.cache_mgr,
            rotation_service=self.rot_service,
            wallpaper_setter=self.setter,
        )

        # 1. Switch to Search and set a query
        win._navigate_to_search()
        win.search_entry.set_text("space")
        self.assertEqual(win.stack.get_visible_child_name(), "search")

        # 2. Press Escape when on Search: should navigate to Dashboard without deleting query
        handled = win._on_window_key_pressed(None, Gdk.KEY_Escape, 0, 0)
        self.assertTrue(handled)
        self.assertEqual(win.stack.get_visible_child_name(), "discover")
        self.assertEqual(win.search_entry.get_text(), "space")  # Query preserved!

        # 3. Press Escape again on Dashboard: should do nothing harmful (returns False)
        handled_second = win._on_window_key_pressed(None, Gdk.KEY_Escape, 0, 0)
        self.assertFalse(handled_second)
        self.assertEqual(win.stack.get_visible_child_name(), "discover")

        # 4. Priority 1: When PreviewDialog is open, Escape closes dialog first and does NOT navigate
        mock_dialog = MagicMock()
        mock_dialog.get_visible.return_value = True
        mock_dialog._is_destroyed = False
        win.current_preview_dialog = mock_dialog

        # Put user on search tab
        win.stack.set_visible_child_name("search")

        handled_preview = win._on_window_key_pressed(None, Gdk.KEY_Escape, 0, 0)
        self.assertTrue(handled_preview)
        # Mock dialog close must have been called
        mock_dialog.close.assert_called_once()
        # View must NOT have navigated away from search
        self.assertEqual(win.stack.get_visible_child_name(), "search")

    def test_ctrl_slash_navigation(self):
        from gi.repository import Gdk

        win = MainWindow(
            app=self.app,
            source_manager=self.src_mgr,
            search_aggregator=self.aggregator,
            cache_manager=self.cache_mgr,
            rotation_service=self.rot_service,
            wallpaper_setter=self.setter,
        )

        # Start on discover
        win.stack.set_visible_child_name("discover")

        # Press Ctrl + /
        handled = win._on_window_key_pressed(None, Gdk.KEY_slash, 0, Gdk.ModifierType.CONTROL_MASK)
        self.assertTrue(handled)
        self.assertEqual(win.stack.get_visible_child_name(), "search")


if __name__ == "__main__":
    unittest.main()
