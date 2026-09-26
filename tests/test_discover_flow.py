"""Tests for Discover view initial load, progressive delivery, empty cache, failure isolation, and infinite scroll separation."""

from pathlib import Path
import shutil
import tempfile
import time
import unittest
from unittest.mock import MagicMock

import gi
gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Adw, Gtk, GLib

from wallpaper_engine.core.cache_manager import CacheManager
from wallpaper_engine.core.models import Capability, Wallpaper
from wallpaper_engine.core.provider_base import WallpaperProvider
from wallpaper_engine.core.rotation_service import RotationService
from wallpaper_engine.core.search_service import SearchAggregator
from wallpaper_engine.core.source_manager import SourceManager
from wallpaper_engine.setters.generic import GenericLinuxWallpaperSetter
from wallpaper_engine.ui.main_window import MainWindow
from wallpaper_engine.ui.wallpaper_card import WallpaperCard


class MockFastProvider(WallpaperProvider):
    def __init__(self, provider_id="fast_p", count=6):
        super().__init__()
        self._pid = provider_id
        self.count = count

    @property
    def provider_id(self) -> str:
        return self._pid

    @property
    def provider_name(self) -> str:
        return "Fast Provider"

    @property
    def homepage_url(self) -> str:
        return "https://example.com"

    @property
    def capabilities(self) -> Capability:
        return Capability.FEATURED | Capability.SEARCH

    def get_featured(self, page=1):
        return [
            Wallpaper(
                id=f"{self.provider_id}-{page}-{i}",
                provider_id=self.provider_id,
                provider_name=self.provider_name,
                title=f"Fast Wallpaper {i}",
                image_url=f"https://example.com/{self.provider_id}/{page}/{i}.jpg",
                thumbnail_url=f"https://example.com/{self.provider_id}/{page}/{i}_thumb.jpg",
                width=1920,
                height=1080,
            )
            for i in range(self.count)
        ]

    def search(self, filters):
        return self.get_featured(filters.page)


class MockFailingProvider(WallpaperProvider):
    def __init__(self, provider_id="openverse_mock"):
        super().__init__()
        self._pid = provider_id

    @property
    def provider_id(self) -> str:
        return self._pid

    @property
    def provider_name(self) -> str:
        return "Failing Provider"

    @property
    def homepage_url(self) -> str:
        return "https://example.com"

    @property
    def capabilities(self) -> Capability:
        return Capability.FEATURED

    def get_featured(self, page=1):
        raise ConnectionError("HTTP 401 Unauthorized: token expired or forbidden")

    def search(self, filters):
        raise ConnectionError("HTTP 401 Unauthorized")


class TestDiscoverFlow(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from gi.repository import Gdk
        Gtk.init()
        if Gdk.Display.get_default() is None:
            raise unittest.SkipTest("No GDK display available in current environment")
        cls.app = Adw.Application(application_id="org.test.discover_flow")

    def setUp(self):
        self.temp_dir = Path(tempfile.mkdtemp(prefix="wp_discover_test_"))
        self.cache_mgr = CacheManager(
            base_cache_dir=self.temp_dir / "cache",
            base_data_dir=self.temp_dir / "data",
        )
        self.src_mgr = SourceManager(config_dir=self.temp_dir / "config")
        self.src_mgr._providers.clear()

        self.fast_prov = MockFastProvider("fast_p", count=8)
        self.src_mgr.register_provider(self.fast_prov)

        self.aggregator = SearchAggregator(self.src_mgr, cache_manager=self.cache_mgr)
        self.setter = GenericLinuxWallpaperSetter()
        self.rot_service = RotationService(
            source_manager=self.src_mgr,
            search_aggregator=self.aggregator,
            cache_manager=self.cache_mgr,
            wallpaper_setter=self.setter,
        )

    def tearDown(self):
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def _drain_glib_events(self, max_iterations=200):
        ctx = GLib.MainContext.default()
        iterations = 0
        while ctx.pending() and iterations < max_iterations:
            ctx.iteration(False)
            iterations += 1

    def test_discover_initial_load(self):
        """Verify Discover initial load populates the grid automatically."""
        win = MainWindow(
            app=self.app,
            source_manager=self.src_mgr,
            search_aggregator=self.aggregator,
            cache_manager=self.cache_mgr,
            rotation_service=self.rot_service,
            wallpaper_setter=self.setter,
        )

        # Allow executor threads and GLib idle tasks to complete
        time.sleep(0.15)
        self._drain_glib_events()

        # Grid should now contain cards
        first_child = win.discover_grid.get_first_child()
        self.assertIsNotNone(first_child, "Discover grid must not be empty after initial load")

        # Verify loaded IDs tracking
        self.assertGreater(len(win.discover_loaded_ids), 0)
        self.assertEqual(len(win.discover_loaded_ids), 8)
        self.assertFalse(win.discover_initial_loading)

    def test_discover_initial_load_with_empty_cache(self):
        """Verify Discover initial load works with zero existing cache or metadata."""
        # Ensure all cache subdirs exist but are completely empty
        shutil.rmtree(self.cache_mgr.thumbs_dir, ignore_errors=True)
        shutil.rmtree(self.cache_mgr.meta_dir, ignore_errors=True)
        self.cache_mgr.thumbs_dir.mkdir(parents=True, exist_ok=True)
        self.cache_mgr.meta_dir.mkdir(parents=True, exist_ok=True)

        self.assertEqual(len(list(self.cache_mgr.thumbs_dir.iterdir())), 0)
        self.assertEqual(len(list(self.cache_mgr.meta_dir.iterdir())), 0)

        win = MainWindow(
            app=self.app,
            source_manager=self.src_mgr,
            search_aggregator=self.aggregator,
            cache_manager=self.cache_mgr,
            rotation_service=self.rot_service,
            wallpaper_setter=self.setter,
        )

        time.sleep(0.15)
        self._drain_glib_events()

        self.assertGreater(len(win.discover_loaded_ids), 0)
        first_child = win.discover_grid.get_first_child()
        self.assertIsNotNone(first_child, "Discover grid must populate even with an empty cache")

    def test_discover_provider_failure_isolation(self):
        """Verify that when one provider fails (e.g. 401 Unauthorized), other providers load smoothly."""
        failing_prov = MockFailingProvider("openverse_broken")
        self.src_mgr.register_provider(failing_prov)

        win = MainWindow(
            app=self.app,
            source_manager=self.src_mgr,
            search_aggregator=self.aggregator,
            cache_manager=self.cache_mgr,
            rotation_service=self.rot_service,
            wallpaper_setter=self.setter,
        )

        time.sleep(0.2)
        self._drain_glib_events()

        # Fast provider's wallpapers should still be loaded
        self.assertEqual(len(win.discover_loaded_ids), 8)
        self.assertFalse(win.discover_initial_loading)

    def test_discover_infinite_scroll_state_separation(self):
        """Verify infinite scroll does not fire during initial load and triggers cleanly when completed."""
        win = MainWindow(
            app=self.app,
            source_manager=self.src_mgr,
            search_aggregator=self.aggregator,
            cache_manager=self.cache_mgr,
            rotation_service=self.rot_service,
            wallpaper_setter=self.setter,
        )

        # While initial load is in progress, simulate scroll event
        win.discover_initial_loading = True
        mock_vadj = MagicMock()
        mock_vadj.get_upper.return_value = 1000
        mock_vadj.get_value.return_value = 500
        mock_vadj.get_page_size.return_value = 400  # dist = 1000 - 500 - 400 = 100 < 800

        page_before = win.discover_page
        win._on_discover_scroll(mock_vadj)
        # Should NOT trigger load more because initial loading is True
        self.assertFalse(win.discover_loading_more)
        self.assertEqual(win.discover_page, page_before)

        # Now simulate initial load complete
        win.discover_initial_loading = False
        win.discover_loading_more = False
        win.discover_has_more = True

        win._on_discover_scroll(mock_vadj)
        # Should now trigger load more
        self.assertTrue(win.discover_loading_more)
        self.assertEqual(win.discover_page, page_before + 1)

    def test_thumbnail_generation_does_not_block_main_thread(self):
        """Verify WallpaperCard thumbnail generation runs asynchronously without blocking."""
        wp = Wallpaper(
            id="nonblock-wp-1",
            provider_id="test",
            provider_name="Test",
            title="Non-blocking Test",
            thumbnail_url="https://example.com/nonblock.jpg",
        )

        # Mock cache fetch to record call without blocking
        self.cache_mgr.fetch_and_cache_thumbnail = MagicMock(return_value=None)

        import concurrent.futures
        pool = concurrent.futures.ThreadPoolExecutor(max_workers=2)
        try:
            t_start = time.perf_counter()
            card = WallpaperCard(
                wp,
                self.cache_mgr,
                on_click=lambda wp: None,
                executor=pool,
            )
            t_elapsed = (time.perf_counter() - t_start) * 1000

            # Creation and initial load scheduling should return immediately (< 30ms)
            self.assertLess(t_elapsed, 50.0)
            self.assertIsNotNone(card)
        finally:
            pool.shutdown(wait=False)


if __name__ == "__main__":
    unittest.main()
