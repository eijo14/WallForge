"""Tests for CacheManager: metadata caching, thumbnailing, and LRU eviction."""

from pathlib import Path
import shutil
import tempfile
import time
import unittest

from PIL import Image

from wallpaper_engine.core.cache_manager import CacheManager


class TestCacheManager(unittest.TestCase):
    def setUp(self):
        self.temp_dir = Path(tempfile.mkdtemp(prefix="wp_cache_test_"))
        self.cache_dir = self.temp_dir / "cache"
        self.data_dir = self.temp_dir / "data"
        self.manager = CacheManager(
            base_cache_dir=self.cache_dir,
            base_data_dir=self.data_dir,
            max_cache_mb=1,  # 1MB limit for quick testing of LRU
        )

    def tearDown(self):
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_meta_cache_and_expiration(self):
        self.manager.set_meta("test_key", {"items": [1, 2, 3]})
        cached = self.manager.get_meta("test_key", max_age_seconds=60)
        self.assertIsNotNone(cached)
        self.assertEqual(cached["items"], [1, 2, 3])

        # Test expiration
        cached_expired = self.manager.get_meta("test_key", max_age_seconds=0)
        self.assertIsNone(cached_expired)

    def test_create_thumbnail(self):
        # Create a test dummy image
        img_path = self.data_dir / "test_orig.png"
        img = Image.new("RGB", (1920, 1080), color=(73, 109, 137))
        img.save(img_path)

        url = "http://example.com/test_orig.png"
        thumb_path = self.manager.create_thumbnail(img_path, url, max_size=320)
        self.assertTrue(thumb_path.is_file())

        # Verify thumbnail dimensions
        with Image.open(thumb_path) as timg:
            self.assertLessEqual(max(timg.size), 320)
            self.assertEqual(timg.format, "WEBP")

        # Verify get_thumbnail_path finds it
        found = self.manager.get_thumbnail_path(url)
        self.assertEqual(found, thumb_path)

    def test_preview_cache(self):
        # Create a large source image (e.g. 2560x1440)
        img_path = self.temp_dir / "large_source.png"
        img = Image.new("RGB", (2560, 1440), color=(120, 80, 200))
        img.save(img_path)

        # Use file:// URL to simulate local preview fetching
        url = f"file://{img_path}"
        ok, preview_path, msg = self.manager.fetch_and_cache_preview(url)
        self.assertTrue(ok)
        self.assertEqual(preview_path, img_path)

        # Test with a mock remote URL using urllib.request mock
        from unittest.mock import MagicMock, patch
        import io
        buf = io.BytesIO()
        img.save(buf, format="JPEG")
        buf.seek(0)

        mock_resp = MagicMock()
        mock_resp.read = buf.read
        mock_resp.__enter__.return_value = mock_resp

        remote_url = "https://example.com/test_wallpaper.jpg"
        with patch("urllib.request.urlopen", return_value=mock_resp):
            ok, preview_path, msg = self.manager.fetch_and_cache_preview(remote_url, max_size=1280)
            self.assertTrue(ok)
            self.assertIsNotNone(preview_path)
            self.assertTrue(preview_path.is_file())
            self.assertEqual(preview_path.parent, self.manager.previews_dir)
            # Verify wallpaper cache remains empty!
            self.assertEqual(len(list(self.manager.wallpapers_dir.glob("*"))), 0)

            # Check dimensions are capped to 1280
            with Image.open(preview_path) as pimg:
                self.assertLessEqual(max(pimg.size), 1280)
                self.assertEqual(pimg.format, "WEBP")

            # Verify get_preview_path finds it
            found = self.manager.get_preview_path(remote_url)
            self.assertEqual(found, preview_path)

        # Clear cache should remove the preview
        cleared = self.manager.clear_cache()
        self.assertGreaterEqual(cleared, 1)
        self.assertIsNone(self.manager.get_preview_path(remote_url))

    def test_clear_cache(self):
        self.manager.set_meta("key1", "data1")
        self.manager.set_meta("key2", "data2")
        self.assertGreater(self.manager.get_cache_size(), 0)

        cleared = self.manager.clear_cache()
        self.assertEqual(cleared, 2)
        self.assertEqual(self.manager.get_cache_size(), 0)


if __name__ == "__main__":
    unittest.main()
