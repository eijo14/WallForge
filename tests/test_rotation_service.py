"""Tests for RotationService: history tracking, source selection, and offline fallback."""

from pathlib import Path
import shutil
import tempfile
import unittest
from unittest.mock import MagicMock

from PIL import Image

from wallpaper_engine.core.cache_manager import CacheManager
from wallpaper_engine.core.models import Wallpaper
from wallpaper_engine.core.rotation_service import RotationService
from wallpaper_engine.core.search_service import SearchAggregator
from wallpaper_engine.core.source_manager import SourceManager
from wallpaper_engine.setters.base import WallpaperSetter


class DummySetter(WallpaperSetter):
    @property
    def name(self) -> str:
        return "Dummy Setter"

    def is_available(self) -> bool:
        return True

    def apply_wallpaper(self, image_path: Path, mode: str = "fill"):
        self.active_wallpaper = image_path
        return True, "Success"


class TestRotationService(unittest.TestCase):
    def setUp(self):
        self.temp_dir = Path(tempfile.mkdtemp(prefix="wp_rot_test_"))
        self.cache_mgr = CacheManager(
            base_cache_dir=self.temp_dir / "cache",
            base_data_dir=self.temp_dir / "data",
        )
        self.src_mgr = MagicMock(spec=SourceManager)
        self.aggregator = MagicMock(spec=SearchAggregator)
        self.setter = DummySetter()

        self.service = RotationService(
            source_manager=self.src_mgr,
            search_aggregator=self.aggregator,
            cache_manager=self.cache_mgr,
            wallpaper_setter=self.setter,
        )

    def tearDown(self):
        self.service.stop()
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_interval_mapping(self):
        self.service.set_interval("5m")
        self.assertEqual(self.service.interval_seconds, 300)
        self.service.set_interval("1h")
        self.assertEqual(self.service.interval_seconds, 3600)
        self.service.set_interval("daily")
        self.assertEqual(self.service.interval_seconds, 86400)

    def test_offline_fallback(self):
        """When online search returns empty, rotation falls back to local downloaded pool."""
        # Create a local offline wallpaper
        offline_img = self.cache_mgr.wallpapers_dir / "saved_offline.jpg"
        img = Image.new("RGB", (1920, 1080), color="green")
        img.save(offline_img)

        # Aggregator returns empty (network down)
        self.aggregator.get_featured.return_value = []

        success = self.service.rotate_now()
        self.assertTrue(success)
        self.assertEqual(self.setter.active_wallpaper, offline_img)

    def test_rotation_history_avoid_immediate_repeat(self):
        wp1 = Wallpaper(id="wp-1", provider_id="p", provider_name="P", title="W1", image_url="file:///tmp/w1.jpg")
        wp2 = Wallpaper(id="wp-2", provider_id="p", provider_name="P", title="W2", image_url="file:///tmp/w2.jpg")
        self.aggregator.get_featured.return_value = [wp1, wp2]

        # Add wp1 to history
        self.service.history.append("wp-1")

        # Next pick must be wp2
        picked = self.service._pick_next_wallpaper()
        self.assertEqual(picked.id, "wp-2")

    def test_start_and_stop_lifecycle(self):
        self.assertFalse(self.service.is_running())
        self.service.start()
        self.assertTrue(self.service.is_running())
        self.service.stop()
        self.assertFalse(self.service.is_running())


if __name__ == "__main__":
    unittest.main()
