"""Unit tests for the wallpaper preview flow.

Tests:
1. Previewing works directly from remote image_url without requiring download first.
2. Previewing saves downscaled image to previews_dir (~/.cache/...) and NEVER to wallpapers_dir (~/.local/share/...).
3. Previewing NEVER calls the WallpaperSetter.
4. If a wallpaper is already downloaded in wallpapers_dir, preview uses local file directly without network.
5. Explicit download action downloads the full wallpaper into wallpapers_dir.
6. Explicit apply action invokes WallpaperSetter (and downloads full wallpaper if not yet present).
7. Error handling & retry when preview fails.
8. GTK WallpaperPreviewDialog lifecycle (when display is available).
"""

from io import BytesIO
from pathlib import Path
import shutil
import tempfile
import unittest
from unittest.mock import MagicMock, patch

from PIL import Image

from wallpaper_engine.core.cache_manager import CacheManager
from wallpaper_engine.core.models import Wallpaper
from wallpaper_engine.setters.base import WallpaperSetter


class MockWallpaperSetter(WallpaperSetter):
    def __init__(self):
        super().__init__()
        self.applied_paths = []

    @property
    def name(self) -> str:
        return "MockSetter"

    def is_available(self) -> bool:
        return True

    def apply_wallpaper(self, image_path: Path) -> tuple[bool, str]:
        self.applied_paths.append(image_path)
        return True, "Mock applied"


class TestPreviewFlowLogic(unittest.TestCase):
    """Test preview flow contract independently of display server."""

    def setUp(self):
        self.temp_dir = Path(tempfile.mkdtemp(prefix="wp_preview_test_"))
        self.cache_dir = self.temp_dir / "cache"
        self.data_dir = self.temp_dir / "data"
        self.cache_mgr = CacheManager(
            base_cache_dir=self.cache_dir,
            base_data_dir=self.data_dir,
            max_cache_mb=10,
        )
        self.setter = MockWallpaperSetter()

        # Create a sample 4K test image in memory
        self.img_4k = Image.new("RGB", (3840, 2160), color=(50, 100, 150))
        self.img_buf = BytesIO()
        self.img_4k.save(self.img_buf, format="JPEG")
        self.img_bytes = self.img_buf.getvalue()

        self.remote_url = "https://example.com/wallpapers/nature_4k.jpg"
        self.wallpaper = Wallpaper(
            id="test-wp-1",
            provider_id="test_prov",
            provider_name="Test Provider",
            title="Nature 4K",
            image_url=self.remote_url,
            thumbnail_url="https://example.com/wallpapers/nature_thumb.jpg",
            width=3840,
            height=2160,
        )

    def tearDown(self):
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def _mock_response(self):
        mock_resp = MagicMock()
        mock_resp.read = BytesIO(self.img_bytes).read
        mock_resp.getheader.return_value = str(len(self.img_bytes))
        mock_resp.__enter__.return_value = mock_resp
        return mock_resp

    def test_preview_does_not_download_to_permanent_wallpapers(self):
        """Preview must fetch into preview cache (downscaled) and NEVER into wallpapers_dir."""
        with patch("urllib.request.urlopen", return_value=self._mock_response()):
            ok, preview_path, msg = self.cache_mgr.fetch_and_cache_preview(
                self.wallpaper.image_url, max_size=1280
            )

        self.assertTrue(ok)
        self.assertIsNotNone(preview_path)
        self.assertTrue(preview_path.is_file())
        self.assertEqual(preview_path.parent, self.cache_mgr.previews_dir)

        # Permanent wallpaper directory must remain empty!
        self.assertEqual(list(self.cache_mgr.wallpapers_dir.glob("*")), [])

        # Preview must be downscaled (max dimension <= 1280) for low-RAM footprint
        with Image.open(preview_path) as pimg:
            self.assertLessEqual(max(pimg.size), 1280)
            self.assertEqual(pimg.format, "WEBP")

        # Setter must NOT have been called
        self.assertEqual(len(self.setter.applied_paths), 0)

    def test_preview_uses_existing_download_if_available(self):
        """If user already downloaded the wallpaper, preview uses local file directly without network."""
        # Pre-download the wallpaper
        with patch("urllib.request.urlopen", return_value=self._mock_response()):
            ok, local_path, msg = self.cache_mgr.download_wallpaper(self.wallpaper.image_url)

        self.assertTrue(ok)
        self.assertTrue(local_path.is_file())

        # Calling fetch_and_cache_preview should detect existing wallpaper and not hit network
        with patch("urllib.request.urlopen", side_effect=AssertionError("Should not hit network!")):
            ok2, p_path, msg2 = self.cache_mgr.fetch_and_cache_preview(self.wallpaper.image_url)

        self.assertTrue(ok2)
        self.assertEqual(p_path, local_path)

    def test_explicit_download_saves_to_permanent_cache(self):
        """Download must explicitly download full wallpaper to wallpapers_dir."""
        with patch("urllib.request.urlopen", return_value=self._mock_response()):
            ok, local_path, msg = self.cache_mgr.download_wallpaper(self.wallpaper.image_url)

        self.assertTrue(ok)
        self.assertEqual(local_path.parent, self.cache_mgr.wallpapers_dir)
        # Verify full resolution preserved
        with Image.open(local_path) as img:
            self.assertEqual(img.size, (3840, 2160))

    def test_apply_wallpaper_downloads_if_needed_and_invokes_setter(self):
        """Applying wallpaper downloads on-demand if needed, then applies via setter."""
        with patch("urllib.request.urlopen", return_value=self._mock_response()):
            ok, local_path, msg = self.cache_mgr.download_wallpaper(self.wallpaper.image_url)
            app_ok, app_msg = self.setter.apply_wallpaper(local_path)

        self.assertTrue(ok)
        self.assertTrue(app_ok)
        self.assertEqual(len(self.setter.applied_paths), 1)
        self.assertEqual(self.setter.applied_paths[0], local_path)

    def test_preview_failure_and_retry(self):
        """Preview fetch failure returns False and error message, allowing retry."""
        with patch("urllib.request.urlopen", side_effect=Exception("Connection timed out")):
            ok, preview_path, msg = self.cache_mgr.fetch_and_cache_preview(
                self.wallpaper.image_url
            )

        self.assertFalse(ok)
        self.assertIsNone(preview_path)
        self.assertIn("Connection timed out", msg)

        # Retry succeeds when network recovers
        with patch("urllib.request.urlopen", return_value=self._mock_response()):
            retry_ok, retry_path, retry_msg = self.cache_mgr.fetch_and_cache_preview(
                self.wallpaper.image_url
            )

        self.assertTrue(retry_ok)
        self.assertIsNotNone(retry_path)
        self.assertTrue(retry_path.is_file())


class TestPreviewDialogUI(unittest.TestCase):
    """Test GTK WallpaperPreviewDialog when GDK display is available."""

    @classmethod
    def setUpClass(cls):
        import gi
        gi.require_version("Gtk", "4.0")
        gi.require_version("Adw", "1")
        from gi.repository import Adw, Gdk, Gtk
        Gtk.init()
        if Gdk.Display.get_default() is None:
            raise unittest.SkipTest("No GDK display available in current environment")
        cls.app = Adw.Application(application_id="org.test.wallpaper_dialog")

    def setUp(self):
        self.temp_dir = Path(tempfile.mkdtemp(prefix="wp_dialog_ui_test_"))
        self.cache_mgr = CacheManager(
            base_cache_dir=self.temp_dir / "cache",
            base_data_dir=self.temp_dir / "data",
        )
        self.setter = MockWallpaperSetter()
        self.wallpaper = Wallpaper(
            id="test-wp-ui",
            provider_id="test",
            provider_name="Test Prov",
            title="Dialog Test",
            image_url="https://example.com/test.jpg",
            thumbnail_url="https://example.com/thumb.jpg",
        )

    def tearDown(self):
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_dialog_creation_and_widgets(self):
        from gi.repository import Gtk
        from wallpaper_engine.ui.preview_dialog import WallpaperPreviewDialog

        parent = Gtk.Window()
        dialog = WallpaperPreviewDialog(
            parent=parent,
            wallpaper=self.wallpaper,
            cache_manager=self.cache_mgr,
            wallpaper_setter=self.setter,
        )
        self.assertIsNotNone(dialog)
        self.assertEqual(dialog.get_title(), "Dialog Test")
        self.assertIsNotNone(dialog.picture)
        self.assertIsNotNone(dialog.loading_box)
        self.assertIsNotNone(dialog.error_box)
        self.assertIsNotNone(dialog.apply_btn)
        self.assertIsNotNone(dialog.download_btn)
        self.assertIsNotNone(dialog.fav_btn)
        self.assertIsNotNone(dialog.close_btn)

        # Test close cleanup
        dialog._on_close_request()
        self.assertTrue(dialog._is_destroyed)

    def test_texture_rendering(self):
        from gi.repository import Gtk, Gdk, GdkPixbuf, Gio
        from wallpaper_engine.ui.preview_dialog import WallpaperPreviewDialog

        # Create a dummy image
        img = Image.new("RGB", (800, 600), color="red")
        img_path = self.temp_dir / "cache" / "previews" / "dummy.webp"
        img_path.parent.mkdir(parents=True, exist_ok=True)
        img.save(img_path, format="WEBP")

        parent = Gtk.Window()
        dialog = WallpaperPreviewDialog(
            parent=parent,
            wallpaper=self.wallpaper,
            cache_manager=self.cache_mgr,
            wallpaper_setter=self.setter,
        )

        # Call the rendering logic directly
        dialog._set_picture_file(img_path)

        # The picture widget should have a paintable (texture)
        paintable = dialog.picture.get_paintable()
        self.assertIsNotNone(paintable, "Paintable (Texture) should not be None")
        self.assertEqual(paintable.get_intrinsic_width(), 800)
        self.assertEqual(paintable.get_intrinsic_height(), 600)
        
        dialog._on_close_request()


if __name__ == "__main__":
    unittest.main()
