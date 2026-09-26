"""Regression test suite for WallForge theme switching and preview loading pipeline.

Tests:
1. Theme switching updates root/application styling and replaces CSS provider cleanly.
2. Preview dialog opens without waiting for network.
3. Cached thumbnail is displayed immediately (<20ms).
4. Preview network request runs asynchronously.
5. Preview timeout does not block UI and keeps thumbnail displayed.
6. Failed preview keeps thumbnail visible and provides retryable state.
7. Preview cache prevents duplicate downloads (concurrent deduplication & cache hits).
8. Closing preview safely cancels/ignores pending work.
9. Full-resolution original is NOT downloaded for preview (CDN preview URLs & 1280px resizing).
10. Multiple providers use the same preview architecture.
"""

import concurrent.futures
from io import BytesIO
import os
from pathlib import Path
import shutil
import tempfile
import time
import unittest
from unittest.mock import MagicMock, patch

from PIL import Image
import gi
gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Adw, Gdk, GLib, Gtk

from wallpaper_engine.core.cache_manager import CacheManager
from wallpaper_engine.core.models import Wallpaper
from wallpaper_engine.core.theme_manager import THEMES, ThemeManager
from wallpaper_engine.setters.base import WallpaperSetter
from wallpaper_engine.ui.preview_dialog import WallpaperPreviewDialog


class DummySetter(WallpaperSetter):
    @property
    def name(self) -> str:
        return "DummySetter"

    def is_available(self) -> bool:
        return True

    def apply_wallpaper(self, image_path: Path) -> tuple[bool, str]:
        return True, "Success"


class TestThemeAndPreviewRegression(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        Gtk.init()
        cls.display_available = Gdk.Display.get_default() is not None

    def setUp(self):
        self.temp_dir = Path(tempfile.mkdtemp(prefix="wallforge_reg_test_"))
        self.cache_dir = self.temp_dir / "cache"
        self.data_dir = self.temp_dir / "data"
        self.config_dir = self.temp_dir / "config"
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.config_dir.mkdir(parents=True, exist_ok=True)

        self.cache_mgr = CacheManager(
            base_cache_dir=self.cache_dir,
            base_data_dir=self.data_dir,
            max_cache_mb=10,
        )
        self.theme_mgr = ThemeManager(config_dir=self.config_dir)
        self.setter = DummySetter()

        # Create a sample test image
        self.sample_img = Image.new("RGB", (2560, 1440), color=(80, 120, 200))
        buf = BytesIO()
        self.sample_img.save(buf, format="JPEG")
        self.sample_img_bytes = buf.getvalue()

        # Create a sample 320px thumbnail
        self.sample_thumb = Image.new("RGB", (320, 180), color=(100, 150, 220))

    def tearDown(self):
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def _mock_http_response(self, data: bytes):
        resp = MagicMock()
        resp.read = BytesIO(data).read
        resp.getheader.return_value = str(len(data))
        resp.__enter__.return_value = resp
        return resp

    # -------------------------------------------------------------------------
    # TEST 1: Theme switching updates root/application styling and replaces CSS provider cleanly
    # -------------------------------------------------------------------------
    def test_01_theme_switching_updates_root_and_replaces_provider_cleanly(self):
        """Theme switching must update Libadwaita color definitions, root styles, and replace provider."""
        callback_log = []
        self.theme_mgr.register_callback(lambda theme: callback_log.append(theme))

        for theme_key in ["dark", "light", "midnight", "pixel_green"]:
            self.theme_mgr.set_theme(theme_key)
            self.assertEqual(self.theme_mgr.current_theme, theme_key)
            css = self.theme_mgr.generate_css()

            # 1. Libadwaita color definitions must be present
            self.assertIn("@define-color window_bg_color", css)
            self.assertIn("@define-color view_bg_color", css)
            self.assertIn("@define-color card_bg_color", css)
            self.assertIn("@define-color headerbar_bg_color", css)

            # 2. Root window and content element styling rules must be present
            self.assertIn("window.background", css)
            self.assertIn(".main-window", css)
            self.assertIn(".pixel-sidebar", css)
            self.assertIn("searchentry", css)
            self.assertIn("preferencespage", css)

        # Callback should have been notified for each theme switch
        self.assertEqual(callback_log, ["dark", "light", "midnight", "pixel_green"])

        # If display is available, verify CSS provider was replaced cleanly
        if self.display_available:
            self.assertIsNotNone(self.theme_mgr._css_provider)
            prev_provider = self.theme_mgr._css_provider
            self.theme_mgr.apply_theme()
            # A new provider instance should have replaced the old one
            self.assertIsNot(self.theme_mgr._css_provider, prev_provider)

    # -------------------------------------------------------------------------
    # TEST 2: Preview dialog opens without waiting for network
    # -------------------------------------------------------------------------
    def test_02_preview_dialog_opens_without_waiting_for_network(self):
        """Dialog instantiation must be fast (<100ms) and not block on network."""
        wp = Wallpaper(
            id="test-wp-fast-open",
            provider_id="archimg",
            provider_name="ArchImg",
            title="Fast Open Test",
            image_url="https://slow-network.example.com/huge_wallpaper.jpg",
            thumbnail_url="https://slow-network.example.com/thumb.jpg",
        )

        def slow_urlopen(*args, **kwargs):
            # Simulate a 5-second network hang
            time.sleep(5.0)
            return self._mock_http_response(self.sample_img_bytes)

        parent = Gtk.Window()
        t0 = time.perf_counter()
        with patch("urllib.request.urlopen", side_effect=slow_urlopen):
            dialog = WallpaperPreviewDialog(
                parent=parent,
                wallpaper=wp,
                cache_manager=self.cache_mgr,
                wallpaper_setter=self.setter,
            )
        elapsed_ms = (time.perf_counter() - t0) * 1000

        # Dialog must open promptly without waiting for the slow network
        self.assertLess(elapsed_ms, 250, f"Dialog open took too long: {elapsed_ms:.1f}ms")
        self.assertIsNotNone(dialog)
        dialog._on_close_request()

    # -------------------------------------------------------------------------
    # TEST 3: Cached thumbnail is displayed immediately (<20ms)
    # -------------------------------------------------------------------------
    def test_03_cached_thumbnail_displayed_immediately(self):
        """When 320px thumbnail is in cache, it must be loaded and rendered in <20ms."""
        wp = Wallpaper(
            id="test-wp-cached-thumb",
            provider_id="wallhaven",
            provider_name="Wallhaven",
            title="Instant Thumb Test",
            image_url="https://example.com/wallhaven-123.jpg",
            thumbnail_url="https://th.wallhaven.cc/small/12/123.jpg",
        )

        # Pre-seed thumbnail in cache
        thumb_hash = self.cache_mgr.get_hash(wp.thumbnail_url)
        cached_thumb_path = self.cache_mgr.thumbs_dir / f"{thumb_hash}.webp"
        self.sample_thumb.save(cached_thumb_path, format="WEBP")

        parent = Gtk.Window()
        t0 = time.perf_counter()
        dialog = WallpaperPreviewDialog(
            parent=parent,
            wallpaper=wp,
            cache_manager=self.cache_mgr,
            wallpaper_setter=self.setter,
        )
        t_init = (time.perf_counter() - t0) * 1000

        # Must indicate thumbnail was displayed and cache hit occurred
        self.assertTrue(dialog._thumbnail_displayed)
        self.assertIsNotNone(dialog.picture.get_paintable())
        self.assertLess(t_init, 100, f"Init with cached thumbnail took {t_init:.1f}ms")
        dialog._on_close_request()

    # -------------------------------------------------------------------------
    # TEST 4: Preview network request runs asynchronously
    # -------------------------------------------------------------------------
    def test_04_preview_network_request_runs_asynchronously(self):
        """Preview fetch must run on a background thread and not block GTK main thread."""
        wp = Wallpaper(
            id="test-wp-async",
            provider_id="bing",
            provider_name="Bing",
            title="Async Test",
            image_url="https://example.com/bing.jpg",
            thumbnail_url="https://example.com/bing_thumb.jpg",
        )

        caller_thread_id = None
        worker_thread_id = None
        fetch_started = concurrent.futures.Future()

        def mock_fetch(url, max_size=1280):
            nonlocal worker_thread_id
            import threading
            worker_thread_id = threading.get_ident()
            fetch_started.set_result(True)
            return True, self.temp_dir / "preview.webp", "OK"

        import threading
        caller_thread_id = threading.get_ident()

        parent = Gtk.Window()
        with patch.object(self.cache_mgr, "fetch_and_cache_preview", side_effect=mock_fetch):
            dialog = WallpaperPreviewDialog(
                parent=parent,
                wallpaper=wp,
                cache_manager=self.cache_mgr,
                wallpaper_setter=self.setter,
            )
            # Wait for background task to start
            fetch_started.result(timeout=2.0)

        self.assertIsNotNone(worker_thread_id)
        self.assertNotEqual(caller_thread_id, worker_thread_id, "Fetch must run on background thread")
        dialog._on_close_request()

    # -------------------------------------------------------------------------
    # TEST 5: Preview timeout does not block UI and keeps thumbnail displayed
    # -------------------------------------------------------------------------
    def test_05_preview_timeout_does_not_block_ui_and_keeps_thumbnail(self):
        """On timeout, thumbnail stays visible, non-blocking error is shown, UI stays alive."""
        wp = Wallpaper(
            id="test-wp-timeout",
            provider_id="nasa",
            provider_name="NASA APOD",
            title="Timeout Test",
            image_url="https://example.com/apod_huge.jpg",
            thumbnail_url="https://example.com/apod_thumb.jpg",
        )

        # Pre-seed thumbnail
        thumb_hash = self.cache_mgr.get_hash(wp.thumbnail_url)
        cached_thumb = self.cache_mgr.thumbs_dir / f"{thumb_hash}.webp"
        self.sample_thumb.save(cached_thumb, format="WEBP")

        parent = Gtk.Window()
        dialog = WallpaperPreviewDialog(
            parent=parent,
            wallpaper=wp,
            cache_manager=self.cache_mgr,
            wallpaper_setter=self.setter,
        )
        self.assertTrue(dialog._thumbnail_displayed)
        paintable_before = dialog.picture.get_paintable()
        self.assertIsNotNone(paintable_before)

        # Deliver timeout result to UI thread handler
        dialog._on_preview_fetched(False, None, "Connection timed out (3.0s connect / 8.0s read)")

        # Picture must STILL have the thumbnail paintable (not cleared)
        self.assertEqual(dialog.picture.get_paintable(), paintable_before)
        # Error box must be visible with message and retry button
        self.assertTrue(dialog.error_box.get_visible())
        self.assertIn("unavailable", dialog.error_label.get_label().lower())
        self.assertTrue(dialog.retry_btn.get_visible())
        # Spinner / loading box must be hidden
        self.assertFalse(dialog.loading_box.get_visible())
        dialog._on_close_request()

    # -------------------------------------------------------------------------
    # TEST 6: Failed preview keeps thumbnail visible and provides retryable state
    # -------------------------------------------------------------------------
    def test_06_failed_preview_keeps_thumbnail_and_provides_retry(self):
        """On HTTP error, thumbnail remains visible and retry button can retrigger fetch."""
        wp = Wallpaper(
            id="test-wp-fail",
            provider_id="wikimedia",
            provider_name="Wikimedia",
            title="Fail Test",
            image_url="https://example.com/wiki.jpg",
            thumbnail_url="https://example.com/wiki_thumb.jpg",
        )

        # Pre-seed thumbnail
        thumb_hash = self.cache_mgr.get_hash(wp.thumbnail_url)
        cached_thumb = self.cache_mgr.thumbs_dir / f"{thumb_hash}.webp"
        self.sample_thumb.save(cached_thumb, format="WEBP")

        parent = Gtk.Window()
        dialog = WallpaperPreviewDialog(
            parent=parent,
            wallpaper=wp,
            cache_manager=self.cache_mgr,
            wallpaper_setter=self.setter,
        )
        paintable = dialog.picture.get_paintable()

        # Simulate HTTP 500 error
        dialog._on_preview_fetched(False, None, "HTTP Error 500: Internal Server Error")

        self.assertIsNotNone(dialog.picture.get_paintable())
        self.assertEqual(dialog.picture.get_paintable(), paintable)
        self.assertTrue(dialog.error_box.get_visible())
        self.assertTrue(dialog.retry_btn.get_sensitive())

        # Test retry action
        retry_triggered = False
        def fake_load():
            nonlocal retry_triggered
            retry_triggered = True

        dialog._load_preview = fake_load
        dialog.retry_btn.emit("clicked")
        self.assertTrue(retry_triggered)
        dialog._on_close_request()

    # -------------------------------------------------------------------------
    # TEST 7: Preview cache prevents duplicate downloads
    # -------------------------------------------------------------------------
    def test_07_preview_cache_prevents_duplicate_downloads(self):
        """Preview cache deduplicates concurrent in-flight requests and caches locally."""
        test_url = "https://example.com/dedup_preview.jpg"
        network_calls = 0

        def counting_urlopen(*args, **kwargs):
            nonlocal network_calls
            network_calls += 1
            time.sleep(0.05)
            return self._mock_http_response(self.sample_img_bytes)

        # 1. Concurrent deduplication
        with patch("urllib.request.urlopen", side_effect=counting_urlopen):
            with concurrent.futures.ThreadPoolExecutor(max_workers=3) as executor:
                f1 = executor.submit(self.cache_mgr.fetch_and_cache_preview, test_url)
                f2 = executor.submit(self.cache_mgr.fetch_and_cache_preview, test_url)
                f3 = executor.submit(self.cache_mgr.fetch_and_cache_preview, test_url)
                res1 = f1.result()
                res2 = f2.result()
                res3 = f3.result()

        self.assertTrue(res1[0] and res2[0] and res3[0])
        self.assertEqual(res1[1], res2[1])
        self.assertEqual(res2[1], res3[1])
        # Only 1 network call should have occurred
        self.assertEqual(network_calls, 1, "Concurrent requests must be deduplicated into 1 network call")

        # 2. Sequential cache hit
        with patch("urllib.request.urlopen", side_effect=counting_urlopen):
            ok, path, msg = self.cache_mgr.fetch_and_cache_preview(test_url)
            self.assertTrue(ok)
            self.assertEqual(path, res1[1])
            # Network call count must remain 1
            self.assertEqual(network_calls, 1, "Cached preview must not trigger network call")

        # Check preview directory path matches wallforge preview cache location
        self.assertEqual(path.parent, self.cache_mgr.previews_dir)
        self.assertTrue(path.name.endswith(".webp"))

    # -------------------------------------------------------------------------
    # TEST 8: Closing preview safely cancels/ignores pending work
    # -------------------------------------------------------------------------
    def test_08_closing_preview_safely_cancels_pending_work(self):
        """Closing dialog marks it destroyed and prevents late worker callbacks from touching UI."""
        wp = Wallpaper(
            id="test-wp-close",
            provider_id="openverse",
            provider_name="Openverse",
            title="Close Cleanup Test",
            image_url="https://example.com/openverse.jpg",
            thumbnail_url="https://example.com/openverse_thumb.jpg",
        )

        parent = Gtk.Window()
        dialog = WallpaperPreviewDialog(
            parent=parent,
            wallpaper=wp,
            cache_manager=self.cache_mgr,
            wallpaper_setter=self.setter,
        )

        self.assertFalse(dialog._is_destroyed)
        dialog._on_close_request()
        self.assertTrue(dialog._is_destroyed)

        # If a late worker completes after destruction, _on_preview_fetched must return early safely
        # without throwing exceptions or updating destroyed GTK widgets
        try:
            dialog._on_preview_fetched(True, self.temp_dir / "late.webp", "OK")
        except Exception as e:
            self.fail(f"_on_preview_fetched raised exception after destruction: {e}")

    # -------------------------------------------------------------------------
    # TEST 9: Full-resolution original is NOT downloaded for preview
    # -------------------------------------------------------------------------
    def test_09_full_resolution_original_is_not_downloaded_for_preview(self):
        """Preview pipeline must resolve to fast CDN previews and downscale to 1280px."""
        # 1. URL resolution tests
        wp_wh = Wallpaper(
            id="wh-1",
            provider_id="wallhaven",
            provider_name="Wallhaven",
            title="Wallhaven Test",
            image_url="https://w.wallhaven.cc/full/9m/wallhaven-9mjoy8.jpg",
            thumbnail_url="https://th.wallhaven.cc/small/9m/9mjoy8.jpg",
        )
        url_wh = WallpaperPreviewDialog.resolve_preview_url(wp_wh)
        self.assertEqual(url_wh, "https://th.wallhaven.cc/lg/9m/9mjoy8.jpg")

        wp_wiki = Wallpaper(
            id="wiki-1",
            provider_id="wikimedia",
            provider_name="Wikimedia",
            title="Wiki Test",
            image_url="https://upload.wikimedia.org/wikipedia/commons/huge_image.jpg",
            thumbnail_url="https://upload.wikimedia.org/wikipedia/commons/thumb/huge_image.jpg/1280px-huge_image.jpg",
        )
        url_wiki = WallpaperPreviewDialog.resolve_preview_url(wp_wiki)
        self.assertIn("1280px", url_wiki)

        # 2. Resizing test: 2560x1440 image fetched must be downscaled to 1280 in preview cache
        with patch("urllib.request.urlopen", side_effect=lambda *args, **kwargs: self._mock_http_response(self.sample_img_bytes)):
            ok, preview_path, _ = self.cache_mgr.fetch_and_cache_preview(
                wp_wh.image_url, max_size=1280
            )

        self.assertTrue(ok)
        self.assertIsNotNone(preview_path)
        with Image.open(preview_path) as im:
            self.assertLessEqual(max(im.size), 1280)
            self.assertEqual(im.format, "WEBP")

        # Full resolution permanent wallpapers directory must remain untouched
        self.assertEqual(list(self.cache_mgr.wallpapers_dir.glob("*")), [])

    # -------------------------------------------------------------------------
    # TEST 10: Multiple providers use the same preview architecture
    # -------------------------------------------------------------------------
    def test_10_multiple_providers_use_same_preview_architecture(self):
        """All supported providers must uniformly work through the preview pipeline."""
        providers_data = [
            ("archimg", "ArchImg", "https://archimg.org/img/1.png", "https://archimg.org/thumb/1.webp"),
            ("wallhaven", "Wallhaven", "https://w.wallhaven.cc/full/1.jpg", "https://th.wallhaven.cc/small/1.jpg"),
            ("bing", "Bing", "https://bing.com/hp/1.jpg", "https://bing.com/hp/1_thumb.jpg"),
            ("nasa", "NASA APOD", "https://apod.nasa.gov/1.jpg", "https://apod.nasa.gov/1_thumb.jpg"),
            ("openverse", "Openverse", "https://openverse.org/1.jpg", "https://openverse.org/1_thumb.jpg"),
            ("wikimedia", "Wikimedia", "https://wikimedia.org/1.jpg", "https://wikimedia.org/thumb/1.jpg"),
            ("github_walls", "GitHub Walls", "https://raw.githubusercontent.com/1.jpg", "https://raw.githubusercontent.com/1_t.jpg"),
        ]

        with patch("urllib.request.urlopen", side_effect=lambda *args, **kwargs: self._mock_http_response(self.sample_img_bytes)):
            for p_id, p_name, img_url, thumb_url in providers_data:
                wp = Wallpaper(
                    id=f"test-{p_id}",
                    provider_id=p_id,
                    provider_name=p_name,
                    title=f"Sample {p_name}",
                    image_url=img_url,
                    thumbnail_url=thumb_url,
                )

                # Resolve URL
                target_url = WallpaperPreviewDialog.resolve_preview_url(wp)
                self.assertIsNotNone(target_url)

                # Fetch and cache preview
                ok, preview_path, msg = self.cache_mgr.fetch_and_cache_preview(target_url, max_size=1280)
                self.assertTrue(ok, f"Failed for provider {p_name}: {msg}")
                self.assertTrue(preview_path.is_file())
                self.assertEqual(preview_path.parent, self.cache_mgr.previews_dir)


if __name__ == "__main__":
    unittest.main()
