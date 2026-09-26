"""Unit tests for CustomWallpaperProvider and custom source management."""

import json
from pathlib import Path
import shutil
import tempfile
import unittest
from unittest.mock import MagicMock, patch

from wallpaper_engine.core.cache_manager import CacheManager
from wallpaper_engine.core.models import SearchFilter
from wallpaper_engine.core.source_manager import SourceManager
from wallpaper_engine.providers.custom import CustomWallpaperProvider, validate_custom_source


class TestCustomProvider(unittest.TestCase):
    def setUp(self):
        self.temp_dir = Path(tempfile.mkdtemp(prefix="wp_custom_test_"))
        self.cache_mgr = CacheManager(
            base_cache_dir=self.temp_dir / "cache",
            base_data_dir=self.temp_dir / "data",
        )
        self.src_mgr = SourceManager(config_dir=self.temp_dir / "config")

    def tearDown(self):
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_local_folder_custom_provider(self):
        folder = self.temp_dir / "my_wallpapers"
        folder.mkdir()
        # Create a mock image
        img1 = folder / "mountain.jpg"
        img1.write_bytes(b"dummy image data")

        cfg = {
            "id": "my_folder",
            "name": "My Mountain Folder",
            "feed_type": "local_folder",
            "url_or_path": str(folder),
        }

        provider = CustomWallpaperProvider(cfg, cache_manager=self.cache_mgr)
        self.assertEqual(provider.provider_id, "my_folder")
        self.assertEqual(provider.provider_name, "My Mountain Folder")

        wallpapers = provider.get_featured()
        self.assertEqual(len(wallpapers), 1)
        self.assertEqual(wallpapers[0].title, "Mountain")

    def test_json_feed_provider(self):
        feed_data = [
            {
                "id": "json_wp_1",
                "title": "Neon Grid",
                "image_url": "https://example.com/neon.png",
                "thumbnail_url": "https://example.com/neon_thumb.png",
                "width": 3840,
                "height": 2160,
                "author": "PixelArtist",
            }
        ]

        cfg = {
            "id": "neon_feed",
            "name": "Neon Feed",
            "feed_type": "json_feed",
            "url_or_path": "https://example.com/feed.json",
        }

        provider = CustomWallpaperProvider(cfg, cache_manager=self.cache_mgr)

        with patch("urllib.request.urlopen") as mock_url:
            mock_resp = MagicMock()
            mock_resp.read.return_value = json.dumps(feed_data).encode("utf-8")
            mock_url.return_value.__enter__.return_value = mock_resp

            wallpapers = provider.get_featured()
            self.assertEqual(len(wallpapers), 1)
            self.assertEqual(wallpapers[0].title, "Neon Grid")
            self.assertEqual(wallpapers[0].width, 3840)

            # Search within feed
            filtered = provider.search(SearchFilter(query="neon"))
            self.assertEqual(len(filtered), 1)

            filtered_empty = provider.search(SearchFilter(query="forest"))
            self.assertEqual(len(filtered_empty), 0)

    def test_source_manager_custom_sources(self):
        cfg = {
            "id": "nature_feed",
            "name": "Nature Feed",
            "feed_type": "local_folder",
            "url_or_path": str(self.temp_dir),
        }

        provider = self.src_mgr.add_custom_source(cfg)
        self.assertIsNotNone(provider)
        self.assertIsNotNone(self.src_mgr.get_provider("custom_nature_feed"))

        # Ensure persistence
        src_mgr_reloaded = SourceManager(config_dir=self.temp_dir / "config")
        custom_list = src_mgr_reloaded.get_custom_sources()
        self.assertEqual(len(custom_list), 1)
        self.assertEqual(custom_list[0]["id"], "custom_nature_feed")

        # Remove
        removed = self.src_mgr.remove_custom_source("custom_nature_feed")
        self.assertTrue(removed)
        self.assertIsNone(self.src_mgr.get_provider("custom_nature_feed"))


if __name__ == "__main__":
    unittest.main()
