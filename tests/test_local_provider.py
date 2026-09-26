"""Tests for LocalProvider scanning filesystem images."""

from pathlib import Path
import shutil
import tempfile
import unittest

from PIL import Image

from wallpaper_engine.core.cache_manager import CacheManager
from wallpaper_engine.core.models import SearchFilter
from wallpaper_engine.providers.local_provider import LocalProvider


class TestLocalProvider(unittest.TestCase):
    def setUp(self):
        self.temp_dir = Path(tempfile.mkdtemp(prefix="wp_local_test_"))
        self.cache_dir = self.temp_dir / "cache"
        self.data_dir = self.temp_dir / "data"
        self.cm = CacheManager(
            base_cache_dir=self.cache_dir,
            base_data_dir=self.data_dir,
        )
        self.provider = LocalProvider(cache_manager=self.cm)

        # Create two test images in data_dir / wallpapers
        img1 = Image.new("RGB", (1920, 1080), color="blue")
        img1.save(self.cm.wallpapers_dir / "mountain_view.jpg")

        img2 = Image.new("RGB", (3840, 2160), color="red")
        img2.save(self.cm.wallpapers_dir / "sunset_glow.png")

    def tearDown(self):
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_scan_and_inspect_local_images(self):
        wallpapers = self.provider.get_featured(page=1)
        self.assertEqual(len(wallpapers), 2)

        titles = [wp.title for wp in wallpapers]
        self.assertIn("Mountain View", titles)
        self.assertIn("Sunset Glow", titles)

        sunset = next(wp for wp in wallpapers if wp.title == "Sunset Glow")
        self.assertEqual(sunset.width, 3840)
        self.assertEqual(sunset.height, 2160)
        self.assertEqual(sunset.aspect_ratio, "16:9")
        self.assertEqual(sunset.license, "Local User File")

    def test_search_local_images(self):
        results = self.provider.search(SearchFilter(query="mountain"))
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0].title, "Mountain View")


if __name__ == "__main__":
    unittest.main()
